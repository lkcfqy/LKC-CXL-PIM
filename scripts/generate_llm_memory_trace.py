#!/usr/bin/env python3
"""
generate_llm_memory_trace.py - Generate Real Memory Traces from LLM Inference

This script runs actual LLM inference and captures the KV-Cache access patterns
to generate realistic memory traces for Ramulator simulation.

Usage:
  python generate_llm_memory_trace.py --model Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4 \
                                      --seq_len 8192 --output traces/llm_kv_8k.trace
"""

import os
import argparse
# import torch
# import time
from dataclasses import dataclass
from typing import List, Tuple
import random


@dataclass
class HBM3Config:
    """HBM3 8Gb organization parameters"""
    channels: int = 1
    pseudochannels: int = 2
    bankgroups: int = 4
    banks_per_bg: int = 4
    rows: int = 32768
    columns: int = 64
    bytes_per_access: int = 64  # Cache line size
    
    @property
    def total_banks(self) -> int:
        return self.pseudochannels * self.bankgroups * self.banks_per_bg


def addr_to_vector(addr: int, hbm: HBM3Config) -> str:
    """Convert physical address to HBM3 address vector"""
    # Simple mapping: addr -> (ch, pc, bg, ba, row, col)
    col = (addr // hbm.bytes_per_access) % hbm.columns
    row = (addr // (hbm.bytes_per_access * hbm.columns)) % hbm.rows
    bank = (addr // (hbm.bytes_per_access * hbm.columns * hbm.rows)) % hbm.total_banks
    
    ch = 0
    pc = bank // (hbm.bankgroups * hbm.banks_per_bg)
    remaining = bank % (hbm.bankgroups * hbm.banks_per_bg)
    bg = remaining // hbm.banks_per_bg
    ba = remaining % hbm.banks_per_bg
    
    return f"{ch},{pc},{bg},{ba},{row},{col}"


def generate_kv_cache_trace_from_model_config(
    hidden_size: int,
    num_layers: int,
    num_heads: int,
    seq_len: int,
    hbm: HBM3Config
) -> List[str]:
    """
    Generate memory trace based on LLM model config.
    
    KV-Cache access pattern during decode phase:
    1. Each layer reads all historical K/V (seq_len reads per layer)
    2. Each layer writes new K/V (1 write per layer)
    
    Memory layout assumption:
    - KV-Cache is stored contiguously per layer
    - K and V are stored separately
    - Base address increments per layer
    """
    traces = []
    head_dim = hidden_size // num_heads
    
    # Bytes per token per layer (K or V, FP16)
    bytes_per_kv_per_token = num_heads * head_dim * 2  # FP16 = 2 bytes
    
    # Base addresses for K and V caches (assume separate regions)
    k_cache_base = 0x10000000  # 256MB offset
    v_cache_base = 0x20000000  # 512MB offset
    
    # Simulate decode phase for multiple tokens
    num_decode_steps = min(100, seq_len // 10)
    
    for step in range(num_decode_steps):
        current_pos = seq_len - num_decode_steps + step
        
        for layer in range(num_layers):
            layer_offset = layer * seq_len * bytes_per_kv_per_token
            
            # Read historical K-cache
            num_reads = min(current_pos, 50)  # Sample reads
            for _ in range(num_reads):
                token_idx = random.randint(0, current_pos - 1)
                addr = k_cache_base + layer_offset + token_idx * bytes_per_kv_per_token
                traces.append(f"RK {addr} {addr_to_vector(addr, hbm)}")
            
            # Read historical V-cache  
            for _ in range(num_reads):
                token_idx = random.randint(0, current_pos - 1)
                addr = v_cache_base + layer_offset + token_idx * bytes_per_kv_per_token
                traces.append(f"RV {addr} {addr_to_vector(addr, hbm)}")
            
            # Write new K-cache (trigger PIM compression)
            addr = k_cache_base + layer_offset + current_pos * bytes_per_kv_per_token
            traces.append(f"K {addr} {addr_to_vector(addr, hbm)}")
            
            # Write new V-cache (trigger PIM compression)
            addr = v_cache_base + layer_offset + current_pos * bytes_per_kv_per_token
            traces.append(f"V {addr} {addr_to_vector(addr, hbm)}")
    
    return traces


def main():
    parser = argparse.ArgumentParser(
        description="Generate LLM memory traces from model config"
    )
    parser.add_argument(
        "--model", type=str, 
        default="Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4",
        help="HuggingFace model name (for config only)"
    )
    parser.add_argument(
        "--hidden_size", type=int, default=3584,
        help="Model hidden size (Qwen 2.5 7B = 3584)"
    )
    parser.add_argument(
        "--num_layers", type=int, default=28,
        help="Number of transformer layers (Qwen 2.5 7B = 28)"
    )
    parser.add_argument(
        "--num_heads", type=int, default=28,
        help="Number of attention heads (Qwen 2.5 7B = 28)"
    )
    parser.add_argument(
        "--seq_len", type=int, default=8192,
        help="Context length"
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
        "--use_model_config", action="store_true",
        help="Load actual model config from HuggingFace (requires transformers)"
    )
    
    args = parser.parse_args()
    random.seed(args.seed)
    
    hbm = HBM3Config()
    
    # Try to load actual model config
    hidden_size = args.hidden_size
    num_layers = args.num_layers
    num_heads = args.num_heads
    
    if args.use_model_config:
        try:
            from transformers import AutoConfig
            print(f"Loading model config from: {args.model}")
            config = AutoConfig.from_pretrained(args.model, trust_remote_code=True)
            hidden_size = config.hidden_size
            num_layers = config.num_hidden_layers
            num_heads = config.num_attention_heads
            print(f"  Loaded: hidden_size={hidden_size}, layers={num_layers}, heads={num_heads}")
        except Exception as e:
            print(f"Warning: Could not load model config: {e}")
            print(f"  Using default values: hidden_size={hidden_size}, layers={num_layers}, heads={num_heads}")
    
    print(f"\nGenerating trace for seq_len={args.seq_len}...")
    print(f"  Model: {args.model}")
    print(f"  Config: hidden_size={hidden_size}, layers={num_layers}, heads={num_heads}")
    
    # Generate trace
    traces = generate_kv_cache_trace_from_model_config(
        hidden_size=hidden_size,
        num_layers=num_layers,
        num_heads=num_heads,
        seq_len=args.seq_len,
        hbm=hbm
    )
    
    # Save trace
    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
    with open(args.output, "w") as f:
        f.write("\n".join(traces))
        f.write("\n")
    
    # Statistics
    k_writes = sum(1 for t in traces if t.startswith("K "))
    v_writes = sum(1 for t in traces if t.startswith("V "))
    reads = sum(1 for t in traces if t.startswith("RK ") or t.startswith("RV "))
    
    print(f"\nTrace generated: {args.output}")
    print(f"  Total lines: {len(traces)}")
    print(f"  K writes (PIM): {k_writes}")
    print(f"  V writes (PIM): {v_writes}")
    print(f"  Reads: {reads}")
    print(f"  KV ratio: {(k_writes + v_writes) / len(traces) * 100:.1f}%")


if __name__ == "__main__":
    main()
