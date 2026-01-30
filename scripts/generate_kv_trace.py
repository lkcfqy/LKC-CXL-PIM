#!/usr/bin/env python3
"""
generate_kv_trace.py - KV-Cache Trace Generator for LLM Attention Simulation

This script generates memory traces that simulate the KV-Cache access patterns
of Large Language Models during the decode phase.

Trace format:
  R addr ch,pc,bg,ba,row,col   # Read request
  W addr ch,pc,bg,ba,row,col   # Write request  
  K addr ch,pc,bg,ba,row,col   # Key cache write (triggers PIM compression)
  V addr ch,pc,bg,ba,row,col   # Value cache write (triggers PIM compression)

Usage:
  python generate_kv_trace.py --seq_len 8192 --num_heads 32 --head_dim 128 --output trace.trace
"""

import argparse
import random
import os
from dataclasses import dataclass
from typing import List, Tuple


from utils import HBM3Config, generate_addr_vec

@dataclass
class LLMConfig:
    """LLM architecture parameters (Qwen 2.5 7B style)"""
    num_layers: int = 28
    num_heads: int = 28
    head_dim: int = 128
    
    @property
    def kv_size_per_token(self) -> int:
        """Bytes per token for K or V (assuming FP16)"""
        return self.num_heads * self.head_dim * 2  # 2 bytes for FP16


def generate_attention_trace(
    seq_len: int,
    llm: LLMConfig,
    hbm: HBM3Config,
    kv_ratio: float = 0.6
) -> List[str]:
    """
    Generate trace simulating LLM decode phase attention.
    
    During decode:
    1. Read all historical K/V from memory (seq_len reads per head)
    2. Write new K/V for current token (1 write per head)
    3. Regular weight reads (non-KV)
    
    Args:
        seq_len: Context length (number of tokens)
        llm: LLM configuration
        hbm: HBM3 configuration
        kv_ratio: Fraction of accesses that are KV-Cache (vs weights)
    
    Returns:
        List of trace lines
    """
    traces = []
    
    # Simulate multiple decode steps
    num_decode_steps = min(100, seq_len // 10)  # Simulate a portion of decode
    
    for step in range(num_decode_steps):
        current_pos = seq_len - num_decode_steps + step
        
        for layer in range(llm.num_layers):
            # Distribute across banks
            base_bank = (layer * 2) % hbm.total_banks
            
            # 1. Read historical K cache (seq_len reads spread across banks)
            num_k_reads = min(current_pos, 50)  # Sample reads
            for i in range(num_k_reads):
                pos = random.randint(0, current_pos - 1)
                bank = (base_bank + pos % 4) % hbm.total_banks
                row = (pos * llm.num_heads) % hbm.rows
                col = random.randint(0, hbm.columns - 1)
                addr = pos * llm.kv_size_per_token
                traces.append(f"RK {addr} {generate_addr_vec(hbm, bank, row, col)}")
            
            # 2. Read historical V cache
            num_v_reads = min(current_pos, 50)
            for i in range(num_v_reads):
                pos = random.randint(0, current_pos - 1)
                bank = (base_bank + 1 + pos % 4) % hbm.total_banks
                row = (pos * llm.num_heads + llm.num_heads // 2) % hbm.rows
                col = random.randint(0, hbm.columns - 1)
                addr = pos * llm.kv_size_per_token + llm.kv_size_per_token // 2
                traces.append(f"RV {addr} {generate_addr_vec(hbm, bank, row, col)}")
            
            # 3. Write new K cache for current token (KV-Cache write)
            bank = base_bank
            row = (current_pos * llm.num_heads) % hbm.rows
            col = layer % hbm.columns
            addr = current_pos * llm.kv_size_per_token
            traces.append(f"K {addr} {generate_addr_vec(hbm, bank, row, col)}")
            
            # 4. Write new V cache for current token (KV-Cache write)
            bank = (base_bank + 1) % hbm.total_banks
            row = (current_pos * llm.num_heads + llm.num_heads // 2) % hbm.rows
            col = layer % hbm.columns
            addr = current_pos * llm.kv_size_per_token + llm.kv_size_per_token // 2
            traces.append(f"V {addr} {generate_addr_vec(hbm, bank, row, col)}")
            
            # 5. Some weight reads (non-KV)
            if random.random() > kv_ratio:
                bank = random.randint(0, hbm.total_banks - 1)
                row = random.randint(0, hbm.rows - 1)
                col = random.randint(0, hbm.columns - 1)
                addr = random.randint(0, 1 << 30)
                traces.append(f"R {addr} {generate_addr_vec(hbm, bank, row, col)}")
            
            # 6. Some output writes (non-KV)
            if random.random() > 0.8:
                bank = random.randint(0, hbm.total_banks - 1)
                row = random.randint(0, hbm.rows - 1)
                col = random.randint(0, hbm.columns - 1)
                addr = random.randint(0, 1 << 30)
                traces.append(f"W {addr} {generate_addr_vec(hbm, bank, row, col)}")
    
    return traces


def main():
    parser = argparse.ArgumentParser(
        description="Generate KV-Cache memory traces for LLM simulation"
    )
    parser.add_argument(
        "--seq_len", type=int, default=8192,
        help="Sequence length (context size)"
    )
    parser.add_argument(
        "--num_layers", type=int, default=28,
        help="Number of transformer layers"
    )
    parser.add_argument(
        "--num_heads", type=int, default=28,
        help="Number of attention heads"
    )
    parser.add_argument(
        "--head_dim", type=int, default=128,
        help="Dimension per attention head"
    )
    parser.add_argument(
        "--kv_ratio", type=float, default=0.6,
        help="Fraction of accesses that are KV-Cache"
    )
    parser.add_argument(
        "--output", type=str, required=True,
        help="Output trace file path"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility"
    )
    
    args = parser.parse_args()
    
    random.seed(args.seed)
    
    llm = LLMConfig(
        num_layers=args.num_layers,
        num_heads=args.num_heads,
        head_dim=args.head_dim
    )
    hbm = HBM3Config()
    
    print(f"Generating trace for seq_len={args.seq_len}...")
    print(f"  LLM config: {llm.num_layers} layers, {llm.num_heads} heads, {llm.head_dim} dim")
    print(f"  KV size per token: {llm.kv_size_per_token} bytes")
    
    traces = generate_attention_trace(
        seq_len=args.seq_len,
        llm=llm,
        hbm=hbm,
        kv_ratio=args.kv_ratio
    )
    
    # Write trace file
    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
    with open(args.output, "w") as f:
        f.write("\n".join(traces))
        f.write("\n")
    
    # Statistics
    k_writes = sum(1 for t in traces if t.startswith("K "))
    v_writes = sum(1 for t in traces if t.startswith("V "))
    reads = sum(1 for t in traces if t.startswith("R "))
    writes = sum(1 for t in traces if t.startswith("W "))
    
    print(f"\nTrace generated: {args.output}")
    print(f"  Total lines: {len(traces)}")
    print(f"  K writes (PIM): {k_writes}")
    print(f"  V writes (PIM): {v_writes}")
    print(f"  Regular reads: {reads}")
    print(f"  Regular writes: {writes}")
    print(f"  KV ratio: {(k_writes + v_writes) / len(traces) * 100:.1f}%")


if __name__ == "__main__":
    main()
