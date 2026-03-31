#!/usr/bin/env python3
"""
generate_multitenant_trace.py - Multi-Tenant KV-Cache Trace Generator

Generates memory traces that simulate concurrent multi-tenant LLM serving
workloads on a CXL-PIM disaggregated memory architecture.

Key Features:
  1. Poisson/MMPP request arrival modeling
  2. Per-request independent KV-Cache address spaces
  3. Time-interleaved memory accesses across concurrent requests
  4. Extended trace format with timestamps and request IDs

Extended Trace Format:
  <OP> <addr> <ch,pc,bg,ba,row,col> <timestamp_ns> <req_id>

Where OP is one of:
  RK - Read Key cache (historical)
  RV - Read Value cache (historical)
  K  - Write Key cache (new token, triggers PIM compression)
  V  - Write Value cache (new token, triggers PIM compression)
  R  - Read (weights/other)
  W  - Write (output/other)

Usage:
  python scripts/generate_multitenant_trace.py \\
    --num_requests 50 \\
    --arrival_rate 10.0 \\
    --context_dist lognormal \\
    --mean_context_len 4096 \\
    --decode_steps 100 \\
    --output traces/multitenant/multi_tenant_50req.trace \\
    --seed 42

Author: LKC-CXL-PIM Project (Phase 5.1)
"""

import os
import sys
import argparse
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from collections import defaultdict
from tqdm import tqdm

# Add scripts dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import HBM3Config, addr_to_hbm_vector
from workload_distributions import (
    ArrivalConfig, ContextConfig,
    generate_request_batch, RequestDescriptor,
    plot_arrival_distribution, plot_context_distribution,
    validate_poisson
)


# ==============================================================================
# Model Configuration
# ==============================================================================

@dataclass
class Qwen25_7B_Config:
    """Qwen2.5-7B model parameters (from real capture in Phase 1)."""
    num_layers: int = 28
    num_kv_heads: int = 4       # GQA: 4 KV heads
    head_dim: int = 128
    
    @property
    def bytes_per_kv_token(self) -> int:
        """Bytes per token for K or V (FP16)."""
        return self.num_kv_heads * self.head_dim * 2  # 2 bytes for FP16
    
    @property 
    def kv_pair_bytes_per_token(self) -> int:
        """Bytes per token for K+V combined."""
        return self.bytes_per_kv_token * 2


# ==============================================================================
# Multi-Tenant Trace Engine
# ==============================================================================

class MultiTenantTraceEngine:
    """
    Generates time-interleaved memory traces for concurrent LLM requests.
    
    Each request gets an isolated KV-Cache address region computed as:
      K_BASE = 0x1000_0000 + req_id * REGION_SIZE
      V_BASE = 0x2000_0000 + req_id * REGION_SIZE
    
    where REGION_SIZE is computed from max possible KV-Cache size per request.
    """
    
    # Address space layout
    K_SPACE_BASE = 0x10000000   # 256 MB mark
    V_SPACE_BASE = 0x20000000   # 512 MB mark
    
    def __init__(
        self,
        model: Qwen25_7B_Config,
        hbm: HBM3Config,
        sample_rate: float = 0.01
    ):
        self.model = model
        self.hbm = hbm
        self.sample_rate = sample_rate
        
        # Per-request region size: enough for 128K tokens * all layers
        self.region_size = 131072 * model.bytes_per_kv_token * model.num_layers
        
        self.stats = defaultdict(int)
    
    def _k_base(self, req_id: int) -> int:
        return self.K_SPACE_BASE + req_id * self.region_size
    
    def _v_base(self, req_id: int) -> int:
        return self.V_SPACE_BASE + req_id * self.region_size
    
    def generate_decode_step_traces(
        self,
        req: RequestDescriptor,
        step: int,
        timestamp_ns: int
    ) -> List[str]:
        """
        Generate trace entries for one decode step of one request.
        
        Each decode step reads all historical K/V and writes 1 new K/V per layer.
        Reads are sampled to control trace size.
        """
        traces = []
        current_seq_len = req.context_len + step
        bytes_per_token = self.model.bytes_per_kv_token
        
        k_base = self._k_base(req.req_id)
        v_base = self._v_base(req.req_id)
        
        # Time increment per layer (rough: spread within one step)
        layer_time_step = 500  # 500 ns per layer processing
        
        for layer in range(self.model.num_layers):
            layer_ts = timestamp_ns + layer * layer_time_step
            
            # --- READ historical K/V (sampled) ---
            sample_step = max(1, int(1 / self.sample_rate)) if self.sample_rate < 1 else 1
            
            for pos in range(0, current_seq_len - 1, sample_step):
                offset = (layer * current_seq_len + pos) * bytes_per_token
                
                # Key read
                k_addr = k_base + offset
                traces.append(
                    f"RK {k_addr} {addr_to_hbm_vector(k_addr, self.hbm)} "
                    f"{layer_ts} {req.req_id}"
                )
                self.stats['RK'] += 1
                
                # Value read
                v_addr = v_base + offset
                traces.append(
                    f"RV {v_addr} {addr_to_hbm_vector(v_addr, self.hbm)} "
                    f"{layer_ts} {req.req_id}"
                )
                self.stats['RV'] += 1
            
            # --- WRITE new K/V (always, triggers PIM) ---
            new_pos = current_seq_len - 1
            offset = (layer * current_seq_len + new_pos) * bytes_per_token
            write_ts = layer_ts + (current_seq_len // sample_step) * 10  # after reads
            
            k_addr = k_base + offset
            traces.append(
                f"K {k_addr} {addr_to_hbm_vector(k_addr, self.hbm)} "
                f"{write_ts} {req.req_id}"
            )
            self.stats['WK'] += 1
            
            v_addr = v_base + offset
            traces.append(
                f"V {v_addr} {addr_to_hbm_vector(v_addr, self.hbm)} "
                f"{write_ts} {req.req_id}"
            )
            self.stats['WV'] += 1
        
        return traces
    
    def generate_full_trace(
        self,
        requests: List[RequestDescriptor],
        decode_steps: int
    ) -> List[str]:
        """
        Generate complete interleaved trace for all concurrent requests.
        
        Requests are interleaved in time-order: at each time tick,
        all active requests generate their decode step traces, then
        these are merged by timestamp.
        
        Args:
            requests: List of RequestDescriptor (sorted by arrival time)
            decode_steps: Number of decode steps per request
        
        Returns:
            List of trace lines, globally sorted by timestamp.
        """
        print(f"\n  Generating traces for {len(requests)} requests...")
        print(f"  Decode steps per request: {decode_steps}")
        print(f"  Sample rate: {self.sample_rate * 100:.1f}%")
        
        # Time per decode step (estimated from real Qwen2.5-7B inference)
        # ~30ms per token at 4K context on INT4
        decode_step_time_ns = 30_000_000  # 30 ms in nanoseconds
        
        all_traces = []
        
        for req in tqdm(requests, desc="  Requests", unit="req"):
            for step in range(min(decode_steps, req.output_tokens)):
                step_ts = req.arrival_time_ns + step * decode_step_time_ns
                step_traces = self.generate_decode_step_traces(req, step, step_ts)
                all_traces.extend(step_traces)
        
        # Sort by timestamp (field index 3, after splitting)
        print(f"\n  Sorting {len(all_traces):,} trace entries by timestamp...")
        all_traces.sort(key=lambda line: int(line.rsplit(' ', 2)[-2]))
        
        return all_traces
    
    def get_stats(self) -> Dict:
        """Return trace generation statistics."""
        total = sum(self.stats.values())
        self.stats['total'] = total
        return dict(self.stats)


# ==============================================================================
# Main
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate multi-tenant KV-Cache memory traces for CXL-PIM simulation"
    )
    parser.add_argument(
        "--num_requests", type=int, default=50,
        help="Number of concurrent requests"
    )
    parser.add_argument(
        "--arrival_rate", type=float, default=10.0,
        help="Average request arrival rate (requests/second)"
    )
    parser.add_argument(
        "--arrival_mode", type=str, default="poisson",
        choices=["poisson", "mmpp"],
        help="Arrival process model"
    )
    parser.add_argument(
        "--context_dist", type=str, default="lognormal",
        choices=["lognormal", "zipf", "sharegpt"],
        help="Context length distribution model"
    )
    parser.add_argument(
        "--mean_context_len", type=int, default=4096,
        help="Mean context length in tokens"
    )
    parser.add_argument(
        "--decode_steps", type=int, default=100,
        help="Number of decode steps per request"
    )
    parser.add_argument(
        "--sample_rate", type=float, default=0.01,
        help="KV-Cache read sampling rate (0.01 = 1%%)"
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
        help="Save distribution plots alongside trace"
    )
    
    args = parser.parse_args()
    
    # --- Configuration ---
    arr_cfg = ArrivalConfig(
        rate=args.arrival_rate,
        duration_s=args.num_requests / args.arrival_rate * 1.5,
        seed=args.seed
    )
    ctx_cfg = ContextConfig(
        mean_len=args.mean_context_len,
        seed=args.seed
    )
    model = Qwen25_7B_Config()
    hbm = HBM3Config()
    
    # --- Banner ---
    print("=" * 70)
    print(" DisaggKV Multi-Tenant Trace Generator")
    print(" Phase 5.1 - LKC-CXL-PIM Project")
    print("=" * 70)
    print(f"  Requests:      {args.num_requests}")
    print(f"  Arrival mode:  {args.arrival_mode} (λ = {args.arrival_rate} req/s)")
    print(f"  Context dist:  {args.context_dist} (mean = {args.mean_context_len} tokens)")
    print(f"  Decode steps:  {args.decode_steps}")
    print(f"  Sample rate:   {args.sample_rate * 100:.1f}%")
    print(f"  Model:         Qwen2.5-7B ({model.num_layers}L, {model.num_kv_heads}KVH, "
          f"{model.head_dim}D)")
    print(f"  Output:        {args.output}")
    
    # --- Generate Request Batch ---
    print("\n[1/4] Generating request batch...")
    requests = generate_request_batch(
        num_requests=args.num_requests,
        arrival_config=arr_cfg,
        context_config=ctx_cfg,
        arrival_mode=args.arrival_mode,
        context_mode=args.context_dist
    )
    
    # Request statistics
    arrivals = np.array([r.arrival_time_ns for r in requests])
    ctx_lens = np.array([r.context_len for r in requests])
    
    print(f"  Generated {len(requests)} requests")
    print(f"  Arrival span: {arrivals[0]/1e9:.2f}s - {arrivals[-1]/1e9:.2f}s")
    print(f"  Context lengths: mean={np.mean(ctx_lens):.0f}, "
          f"median={np.median(ctx_lens):.0f}, "
          f"min={np.min(ctx_lens)}, max={np.max(ctx_lens)}")
    
    # Validate Poisson
    if args.arrival_mode == "poisson":
        validation = validate_poisson(arrivals, args.arrival_rate)
        status = "✅ PASS" if validation['valid'] else "⚠️ FAIL"
        print(f"  Poisson KS test: {status} (p={validation['p_value']:.4f})")
    
    # --- Generate Traces ---
    print("\n[2/4] Generating memory traces...")
    engine = MultiTenantTraceEngine(
        model=model,
        hbm=hbm,
        sample_rate=args.sample_rate
    )
    
    traces = engine.generate_full_trace(requests, args.decode_steps)
    
    # --- Export ---
    print(f"\n[3/4] Exporting {len(traces):,} trace entries...")
    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    
    with open(args.output, 'w') as f:
        f.write('\n'.join(traces))
        f.write('\n')
    
    file_size = os.path.getsize(args.output)
    
    # --- Statistics ---
    print(f"\n[4/4] Finalizing...")
    stats = engine.get_stats()
    
    print("\n" + "=" * 70)
    print(" Trace Generation Complete")
    print("=" * 70)
    print(f"  Output file:    {args.output}")
    print(f"  File size:      {file_size / 1024 / 1024:.2f} MB")
    print(f"  Total entries:  {stats.get('total', 0):,}")
    print(f"  Key reads (RK): {stats.get('RK', 0):,}")
    print(f"  Val reads (RV): {stats.get('RV', 0):,}")
    print(f"  Key writes (K): {stats.get('WK', 0):,}")
    print(f"  Val writes (V): {stats.get('WV', 0):,}")
    
    total = stats.get('total', 1)
    rw_ratio = (stats.get('RK', 0) + stats.get('RV', 0)) / total * 100
    print(f"  Read ratio:     {rw_ratio:.1f}%")
    
    # Per-request summary
    kv_per_req = (stats.get('WK', 0) + stats.get('WV', 0)) / args.num_requests
    print(f"  KV writes/req:  {kv_per_req:.0f}")
    
    # Bandwidth estimate
    total_bytes = stats.get('total', 0) * hbm.bytes_per_access
    total_time_s = (arrivals[-1] - arrivals[0]) / 1e9 + args.decode_steps * 0.03
    bw_gbps = total_bytes / total_time_s / 1e9 if total_time_s > 0 else 0
    print(f"  Est. bandwidth: {bw_gbps:.2f} GB/s")
    
    # --- Save Plots ---
    if args.save_plots:
        plot_dir = os.path.dirname(args.output) or "."
        print(f"\n  Saving distribution plots to {plot_dir}/")
        plot_arrival_distribution(
            arrivals,
            title=f"Arrival Distribution (λ={args.arrival_rate}, {args.arrival_mode})",
            output=os.path.join(plot_dir, "arrival_distribution.png")
        )
        plot_context_distribution(
            ctx_lens,
            title=f"Context Length ({args.context_dist}, mean={args.mean_context_len})",
            output=os.path.join(plot_dir, "context_length_distribution.png")
        )
    
    print("=" * 70)
    print(f"\n✅ Multi-tenant trace ready: {args.output}")


if __name__ == "__main__":
    main()
