#!/usr/bin/env python3
"""
generate_prefix_sharing_trace.py - Prefix-Sharing Multi-Tenant Trace Generator

Generates memory traces for the prefix-sharing scenario where multiple concurrent
users share a common system prompt (e.g., 8K tokens) while each carrying their
own private user context (~1K tokens).

This scenario directly demonstrates the advantage of CXL memory pooling:
- Shared KV-Cache prefix is stored ONCE in a shared memory region
- All concurrent users READ from the same shared region
- Each user's private KV is stored in isolated regions
- Write-once-read-many pattern maximizes CXL bandwidth utilization

Key Insight for Paper:
  Without sharing: 50 users × 8K prefix = 400K tokens of KV storage
  With sharing:    1 × 8K prefix + 50 × 1K user = 58K tokens
  Storage saving:  85.5%

Extended Trace Format:
  <OP> <addr> <ch,pc,bg,ba,row,col> <timestamp_ns> <req_id> [<node_id>]

Usage:
  python scripts/generate_prefix_sharing_trace.py \\
    --num_users 50 \\
    --shared_prefix_len 8192 \\
    --user_context_len 1024 \\
    --decode_steps 50 \\
    --output traces/multitenant/prefix_sharing_50u_8k.trace

Author: LKC-CXL-PIM Project (Phase 5.1)
"""

import os
import sys
import argparse
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional
from collections import defaultdict
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import HBM3Config, addr_to_hbm_vector
from workload_distributions import (
    ArrivalConfig, ContextConfig,
    poisson_arrivals, validate_poisson,
    plot_arrival_distribution
)


# ==============================================================================
# Model Configuration
# ==============================================================================

@dataclass
class Qwen25_7B_Config:
    """Qwen2.5-7B model parameters."""
    num_layers: int = 28
    num_kv_heads: int = 4
    head_dim: int = 128
    
    @property
    def bytes_per_kv_token(self) -> int:
        return self.num_kv_heads * self.head_dim * 2  # FP16


# ==============================================================================
# Address Space Layout for Prefix Sharing
# ==============================================================================

@dataclass
class PrefixSharingLayout:
    """
    Memory address layout for prefix-sharing scenario.
    
    Layout:
      ┌─────────────────────────────────────────────┐
      │  SHARED K Region                             │  0x1000_0000
      │  (System Prompt KV, read by all users)       │
      ├─────────────────────────────────────────────┤
      │  USER 0 Private K Region                     │  PRIVATE_K_BASE + 0 * REGION
      │  USER 1 Private K Region                     │  PRIVATE_K_BASE + 1 * REGION
      │  ...                                         │
      ├─────────────────────────────────────────────┤
      │  SHARED V Region                             │  0x4000_0000
      │  (System Prompt KV, read by all users)       │
      ├─────────────────────────────────────────────┤
      │  USER 0 Private V Region                     │  PRIVATE_V_BASE + 0 * REGION
      │  USER 1 Private V Region                     │  PRIVATE_V_BASE + 1 * REGION
      │  ...                                         │
      └─────────────────────────────────────────────┘
    """
    SHARED_K_BASE: int = 0x10000000     # 256 MB
    PRIVATE_K_BASE: int = 0x20000000    # 512 MB
    SHARED_V_BASE: int = 0x40000000     # 1 GB
    PRIVATE_V_BASE: int = 0x50000000    # 1.25 GB
    
    def __init__(self, model: Qwen25_7B_Config, max_users: int = 128):
        # Per-user private region: enough for 32K private tokens
        self.private_region_size = (
            32768 * model.bytes_per_kv_token * model.num_layers
        )
    
    def shared_k_addr(self, layer: int, pos: int, bytes_per_token: int) -> int:
        """Address for shared prefix Key at (layer, position)."""
        offset = (layer * 131072 + pos) * bytes_per_token  # 131072 = max prefix
        return self.SHARED_K_BASE + offset
    
    def shared_v_addr(self, layer: int, pos: int, bytes_per_token: int) -> int:
        """Address for shared prefix Value at (layer, position)."""
        offset = (layer * 131072 + pos) * bytes_per_token
        return self.SHARED_V_BASE + offset
    
    def private_k_addr(self, user_id: int, layer: int, pos: int, 
                       bytes_per_token: int, max_seq: int) -> int:
        """Address for user's private Key at (layer, position)."""
        base = self.PRIVATE_K_BASE + user_id * self.private_region_size
        offset = (layer * max_seq + pos) * bytes_per_token
        return base + offset
    
    def private_v_addr(self, user_id: int, layer: int, pos: int,
                       bytes_per_token: int, max_seq: int) -> int:
        """Address for user's private Value at (layer, position)."""
        base = self.PRIVATE_V_BASE + user_id * self.private_region_size
        offset = (layer * max_seq + pos) * bytes_per_token
        return base + offset


# ==============================================================================
# Prefix Sharing Trace Engine
# ==============================================================================

class PrefixSharingTraceEngine:
    """
    Generates traces for the prefix-sharing multi-tenant scenario.
    
    Core pattern per decode step per user:
      1. READ shared prefix K/V (same addresses for all users)
      2. READ private context K/V (unique per user)
      3. WRITE new K/V to private region (triggers PIM)
    
    The key observation: shared K/V reads create MASSIVE row-buffer hits
    in HBM because all users access the same rows. This is ideal for PIM.
    """
    
    def __init__(
        self,
        model: Qwen25_7B_Config,
        hbm: HBM3Config,
        shared_prefix_len: int,
        num_users: int,
        sample_rate: float = 0.01
    ):
        self.model = model
        self.hbm = hbm
        self.shared_prefix_len = shared_prefix_len
        self.num_users = num_users
        self.sample_rate = sample_rate
        self.layout = PrefixSharingLayout(model, num_users)
        
        self.stats = defaultdict(int)
        self.stats_per_region = defaultdict(int)  # shared vs private
    
    def generate_decode_step(
        self,
        user_id: int,
        user_context_len: int,
        step: int,
        timestamp_ns: int
    ) -> List[str]:
        """
        Generate trace for one decode step of one user.
        
        Read pattern: shared_prefix + private_context (all historical)
        Write pattern: new K/V to private region
        """
        traces = []
        bpt = self.model.bytes_per_kv_token
        current_private_len = user_context_len + step
        total_seq = self.shared_prefix_len + current_private_len
        
        layer_time_step = 500  # ns per layer
        sample_step = max(1, int(1 / self.sample_rate)) if self.sample_rate < 1 else 1
        
        for layer in range(self.model.num_layers):
            layer_ts = timestamp_ns + layer * layer_time_step
            
            # --- 1. READ shared prefix K/V (same for all users) ---
            for pos in range(0, self.shared_prefix_len, sample_step):
                k_addr = self.layout.shared_k_addr(layer, pos, bpt)
                traces.append(
                    f"RK {k_addr} {addr_to_hbm_vector(k_addr, self.hbm)} "
                    f"{layer_ts} {user_id}"
                )
                self.stats['RK_shared'] += 1
                
                v_addr = self.layout.shared_v_addr(layer, pos, bpt)
                traces.append(
                    f"RV {v_addr} {addr_to_hbm_vector(v_addr, self.hbm)} "
                    f"{layer_ts} {user_id}"
                )
                self.stats['RV_shared'] += 1
            
            # --- 2. READ private context K/V ---
            for pos in range(0, current_private_len - 1, sample_step):
                k_addr = self.layout.private_k_addr(
                    user_id, layer, pos, bpt, current_private_len
                )
                traces.append(
                    f"RK {k_addr} {addr_to_hbm_vector(k_addr, self.hbm)} "
                    f"{layer_ts} {user_id}"
                )
                self.stats['RK_private'] += 1
                
                v_addr = self.layout.private_v_addr(
                    user_id, layer, pos, bpt, current_private_len
                )
                traces.append(
                    f"RV {v_addr} {addr_to_hbm_vector(v_addr, self.hbm)} "
                    f"{layer_ts} {user_id}"
                )
                self.stats['RV_private'] += 1
            
            # --- 3. WRITE new K/V to private region ---
            new_pos = current_private_len - 1
            write_ts = layer_ts + (total_seq // sample_step) * 10
            
            k_addr = self.layout.private_k_addr(
                user_id, layer, new_pos, bpt, current_private_len
            )
            traces.append(
                f"K {k_addr} {addr_to_hbm_vector(k_addr, self.hbm)} "
                f"{write_ts} {user_id}"
            )
            self.stats['WK'] += 1
            
            v_addr = self.layout.private_v_addr(
                user_id, layer, new_pos, bpt, current_private_len
            )
            traces.append(
                f"V {v_addr} {addr_to_hbm_vector(v_addr, self.hbm)} "
                f"{write_ts} {user_id}"
            )
            self.stats['WV'] += 1
        
        return traces
    
    def generate_full_trace(
        self,
        arrivals_ns: np.ndarray,
        user_context_len: int,
        decode_steps: int
    ) -> List[str]:
        """
        Generate complete interleaved trace for all users with prefix sharing.
        """
        num_users = len(arrivals_ns)
        decode_step_time_ns = 30_000_000  # 30 ms per step
        
        print(f"\n  Generating prefix-sharing traces...")
        print(f"  Users: {num_users}")
        print(f"  Shared prefix: {self.shared_prefix_len} tokens")
        print(f"  Private context: {user_context_len} tokens per user")
        print(f"  Decode steps: {decode_steps}")
        print(f"  Sample rate: {self.sample_rate * 100:.1f}%")
        
        all_traces = []
        
        for user_id in tqdm(range(num_users), desc="  Users", unit="user"):
            arrival = arrivals_ns[user_id]
            for step in range(decode_steps):
                step_ts = arrival + step * decode_step_time_ns
                step_traces = self.generate_decode_step(
                    user_id=user_id,
                    user_context_len=user_context_len,
                    step=step,
                    timestamp_ns=step_ts
                )
                all_traces.extend(step_traces)
        
        # Sort by timestamp
        print(f"\n  Sorting {len(all_traces):,} trace entries by timestamp...")
        all_traces.sort(key=lambda line: int(line.rsplit(' ', 2)[-2]))
        
        return all_traces
    
    def get_stats(self) -> Dict:
        """Return detailed statistics with shared vs private breakdown."""
        total = sum(v for k, v in self.stats.items())
        self.stats['total'] = total
        
        shared_reads = self.stats.get('RK_shared', 0) + self.stats.get('RV_shared', 0)
        private_reads = self.stats.get('RK_private', 0) + self.stats.get('RV_private', 0)
        writes = self.stats.get('WK', 0) + self.stats.get('WV', 0)
        
        self.stats['shared_read_ratio'] = shared_reads / max(total, 1) * 100
        self.stats['private_read_ratio'] = private_reads / max(total, 1) * 100
        self.stats['write_ratio'] = writes / max(total, 1) * 100
        
        return dict(self.stats)
    
    def compute_savings(
        self,
        num_users: int,
        user_context_len: int
    ) -> Dict:
        """
        Compute memory and bandwidth savings from prefix sharing.
        
        Returns:
            Dictionary with saving metrics for paper.
        """
        bpt = self.model.bytes_per_kv_token
        layers = self.model.num_layers
        
        # Without sharing: each user stores full KV (prefix + private)
        total_no_share = (
            num_users * (self.shared_prefix_len + user_context_len)
            * bpt * layers * 2  # K + V
        )
        
        # With sharing: 1 shared prefix + N private regions
        total_with_share = (
            self.shared_prefix_len * bpt * layers * 2  # shared (once)
            + num_users * user_context_len * bpt * layers * 2  # private
        )
        
        savings = {
            'no_share_bytes': total_no_share,
            'no_share_mb': total_no_share / 1024 / 1024,
            'with_share_bytes': total_with_share,
            'with_share_mb': total_with_share / 1024 / 1024,
            'saving_percent': (1 - total_with_share / total_no_share) * 100,
            'saving_factor': total_no_share / total_with_share,
        }
        
        # Bandwidth savings per decode step
        # Without sharing: each user reads full prefix
        bw_no_share = num_users * self.shared_prefix_len * bpt * layers * 2
        # With sharing: shared reads can hit row buffer (effectively 1x read)
        # In practice, ~1x for first user, row-hit for subsequent users
        bw_with_share = (
            self.shared_prefix_len * bpt * layers * 2  # effectively 1x shared read
            + num_users * user_context_len * bpt * layers * 2  # private reads
        )
        savings['bw_no_share_gb_per_step'] = bw_no_share / 1e9
        savings['bw_with_share_gb_per_step'] = bw_with_share / 1e9
        savings['bw_saving_percent'] = (1 - bw_with_share / bw_no_share) * 100
        
        return savings


# ==============================================================================
# Main
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate prefix-sharing multi-tenant traces for CXL-PIM"
    )
    parser.add_argument(
        "--num_users", type=int, default=50,
        help="Number of concurrent users"
    )
    parser.add_argument(
        "--shared_prefix_len", type=int, default=8192,
        help="Length of shared system prompt in tokens"
    )
    parser.add_argument(
        "--user_context_len", type=int, default=1024,
        help="Length of each user's private context in tokens"
    )
    parser.add_argument(
        "--decode_steps", type=int, default=50,
        help="Number of decode steps per user"
    )
    parser.add_argument(
        "--arrival_rate", type=float, default=20.0,
        help="User arrival rate (users/second)"
    )
    parser.add_argument(
        "--sample_rate", type=float, default=0.01,
        help="KV-Cache read sampling rate"
    )
    parser.add_argument(
        "--output", type=str, required=True,
        help="Output trace file path"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed"
    )
    parser.add_argument(
        "--save_plots", action="store_true",
        help="Save plots alongside trace"
    )
    
    args = parser.parse_args()
    
    model = Qwen25_7B_Config()
    hbm = HBM3Config()
    
    # --- Banner ---
    print("=" * 70)
    print(" DisaggKV Prefix-Sharing Trace Generator")
    print(" Phase 5.1 - LKC-CXL-PIM Project")
    print("=" * 70)
    print(f"  Users:           {args.num_users}")
    print(f"  Shared prefix:   {args.shared_prefix_len} tokens "
          f"({args.shared_prefix_len // 1024}K)")
    print(f"  User context:    {args.user_context_len} tokens "
          f"({args.user_context_len / 1024:.1f}K)")
    print(f"  Decode steps:    {args.decode_steps}")
    print(f"  Arrival rate:    {args.arrival_rate} users/s")
    print(f"  Sample rate:     {args.sample_rate * 100:.1f}%")
    
    # --- Generate Arrivals ---
    print("\n[1/5] Generating user arrivals...")
    arr_cfg = ArrivalConfig(
        rate=args.arrival_rate,
        duration_s=args.num_users / args.arrival_rate * 1.5,
        seed=args.seed
    )
    arrivals = poisson_arrivals(arr_cfg)
    arrivals = arrivals[:args.num_users]
    
    # If not enough arrivals, extend
    if len(arrivals) < args.num_users:
        extra = np.arange(len(arrivals), args.num_users) * int(1e9 / args.arrival_rate)
        if len(arrivals) > 0:
            extra += arrivals[-1]
        arrivals = np.concatenate([arrivals, extra])
    
    print(f"  Generated {len(arrivals)} user arrivals")
    print(f"  Time span: {arrivals[0]/1e9:.2f}s - {arrivals[-1]/1e9:.2f}s")
    
    # --- Compute Savings (pre-generation analysis) ---
    print("\n[2/5] Computing memory savings analysis...")
    engine = PrefixSharingTraceEngine(
        model=model,
        hbm=hbm,
        shared_prefix_len=args.shared_prefix_len,
        num_users=args.num_users,
        sample_rate=args.sample_rate
    )
    
    savings = engine.compute_savings(args.num_users, args.user_context_len)
    
    print(f"  ┌─ Memory Analysis ─────────────────────────────────┐")
    print(f"  │ Without sharing: {savings['no_share_mb']:.2f} MB              │")
    print(f"  │ With sharing:    {savings['with_share_mb']:.2f} MB              │")
    print(f"  │ Storage saving:  {savings['saving_percent']:.1f}% "
          f"({savings['saving_factor']:.1f}x)           │")
    print(f"  ├─ Bandwidth Analysis ──────────────────────────────┤")
    print(f"  │ BW/step (no share):   {savings['bw_no_share_gb_per_step']:.2f} GB    │")
    print(f"  │ BW/step (sharing):    {savings['bw_with_share_gb_per_step']:.2f} GB    │")
    print(f"  │ BW saving:            {savings['bw_saving_percent']:.1f}%              │")
    print(f"  └──────────────────────────────────────────────────┘")
    
    # --- Generate Traces ---
    print("\n[3/5] Generating memory traces...")
    traces = engine.generate_full_trace(
        arrivals_ns=arrivals,
        user_context_len=args.user_context_len,
        decode_steps=args.decode_steps
    )
    
    # --- Export ---
    print(f"\n[4/5] Exporting {len(traces):,} trace entries...")
    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    
    with open(args.output, 'w') as f:
        f.write('\n'.join(traces))
        f.write('\n')
    
    file_size = os.path.getsize(args.output)
    
    # --- Statistics ---
    print(f"\n[5/5] Final statistics...")
    stats = engine.get_stats()
    
    print("\n" + "=" * 70)
    print(" Prefix-Sharing Trace Generation Complete")
    print("=" * 70)
    print(f"  Output file:       {args.output}")
    print(f"  File size:         {file_size / 1024 / 1024:.2f} MB")
    print(f"  Total entries:     {stats.get('total', 0):,}")
    print(f"  ─── Shared Region ───")
    print(f"  Shared K reads:    {stats.get('RK_shared', 0):,}")
    print(f"  Shared V reads:    {stats.get('RV_shared', 0):,}")
    print(f"  Shared read ratio: {stats.get('shared_read_ratio', 0):.1f}%")
    print(f"  ─── Private Region ───")
    print(f"  Private K reads:   {stats.get('RK_private', 0):,}")
    print(f"  Private V reads:   {stats.get('RV_private', 0):,}")
    print(f"  Private read ratio:{stats.get('private_read_ratio', 0):.1f}%")
    print(f"  ─── Writes ───")
    print(f"  K writes (PIM):    {stats.get('WK', 0):,}")
    print(f"  V writes (PIM):    {stats.get('WV', 0):,}")
    print(f"  Write ratio:       {stats.get('write_ratio', 0):.1f}%")
    
    # Paper-ready summary
    print(f"\n  📊 Key Metrics for Paper:")
    print(f"     Memory saving:  {savings['saving_percent']:.1f}%")
    print(f"     BW saving:      {savings['bw_saving_percent']:.1f}%")
    print(f"     Shared/Total:   {stats.get('shared_read_ratio', 0):.1f}% reads from shared region")
    
    # --- Save Plots ---
    if args.save_plots:
        plot_dir = os.path.dirname(args.output) or "."
        plot_arrival_distribution(
            arrivals,
            title=f"User Arrivals (λ={args.arrival_rate} users/s)",
            output=os.path.join(plot_dir, "prefix_sharing_arrivals.png")
        )
    
    # Save savings report
    report_path = args.output.replace('.trace', '_savings_report.txt')
    with open(report_path, 'w') as f:
        f.write("DisaggKV Prefix-Sharing Memory Savings Analysis\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Configuration:\n")
        f.write(f"  Users: {args.num_users}\n")
        f.write(f"  Shared prefix: {args.shared_prefix_len} tokens\n")
        f.write(f"  Private context: {args.user_context_len} tokens\n\n")
        f.write(f"Storage:\n")
        f.write(f"  Without sharing: {savings['no_share_mb']:.2f} MB\n")
        f.write(f"  With sharing:    {savings['with_share_mb']:.2f} MB\n")
        f.write(f"  Saving:          {savings['saving_percent']:.1f}%\n\n")
        f.write(f"Bandwidth (per decode step):\n")
        f.write(f"  Without sharing: {savings['bw_no_share_gb_per_step']:.4f} GB\n")
        f.write(f"  With sharing:    {savings['bw_with_share_gb_per_step']:.4f} GB\n")
        f.write(f"  Saving:          {savings['bw_saving_percent']:.1f}%\n")
    print(f"\n  Savings report: {report_path}")
    
    print("=" * 70)
    print(f"\n✅ Prefix-sharing trace ready: {args.output}")


if __name__ == "__main__":
    main()
