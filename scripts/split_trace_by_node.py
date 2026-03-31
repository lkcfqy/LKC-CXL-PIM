#!/usr/bin/env python3
"""
split_trace_by_node.py - Split Multi-Tenant Trace by CXL Node

Splits a multi-tenant trace (from Phase 5.1) into per-node sub-traces
based on the CXL disaggregated memory configuration.

Splitting Strategy:
  - Shared prefix accesses (address range detection) -> shared_kv node
  - Private KV accesses -> round-robin across private_kv nodes by req_id
  - Cross-node communication trace is generated for P2P transfers

Output:
  - N per-node trace files (compatible with Ramulator2 ReadWriteTrace)
  - 1 cross-node communication trace (for CXL Fabric simulator)
  - Summary statistics

Usage:
  python scripts/split_trace_by_node.py \\
    --input traces/multitenant/prefix_sharing_50u_8k.trace \\
    --config ramulator2/cxl_disagg_config.yaml \\
    --output_dir traces/multitenant/split_4node/

Author: LKC-CXL-PIM Project (Phase 5.2)
"""

import os
import sys
import argparse
import json
from collections import defaultdict
from typing import Dict, List

import yaml
from tqdm import tqdm


def split_trace(
    input_path: str,
    config_path: str,
    output_dir: str,
    shared_k_range: tuple = (0x10000000, 0x20000000),
    shared_v_range: tuple = (0x40000000, 0x50000000),
):
    """
    Split a multi-tenant trace into per-node sub-traces.
    """
    # Load CXL config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    fabric_cfg = config['CXLFabric']
    num_nodes = fabric_cfg['num_nodes']
    
    # Identify shared vs private nodes
    shared_node_ids = []
    private_node_ids = []
    for node_cfg in fabric_cfg['nodes']:
        if node_cfg.get('role') == 'shared_kv':
            shared_node_ids.append(node_cfg['node_id'])
        else:
            private_node_ids.append(node_cfg['node_id'])
    
    if not shared_node_ids:
        shared_node_ids = [0]
    if not private_node_ids:
        private_node_ids = list(range(1, num_nodes))
    
    shared_node = shared_node_ids[0]
    num_private = len(private_node_ids)
    
    print(f"  Nodes: {num_nodes} total")
    print(f"  Shared KV node: {shared_node}")
    print(f"  Private KV nodes: {private_node_ids}")
    
    # Prepare output
    os.makedirs(output_dir, exist_ok=True)
    
    # Per-node trace buffers
    node_traces: Dict[int, List[str]] = {i: [] for i in range(num_nodes)}
    cross_node_trace: List[str] = []
    
    # Statistics
    stats = defaultdict(int)
    per_node_stats = {i: defaultdict(int) for i in range(num_nodes)}
    
    # Read and split
    print(f"  Reading: {input_path}")
    with open(input_path, 'r') as f:
        lines = f.readlines()
    
    total_lines = len(lines)
    print(f"  Total lines: {total_lines:,}")
    
    for line in tqdm(lines, desc="  Splitting", unit="line", mininterval=1.0):
        line = line.strip()
        if not line:
            continue
        
        parts = line.split()
        if len(parts) < 3:
            continue
        
        op = parts[0]
        addr = int(parts[1])
        addr_vec = parts[2]
        timestamp = parts[3] if len(parts) > 3 else "0"
        req_id = int(parts[4]) if len(parts) > 4 else 0
        
        # Determine if shared or private access
        is_shared = (
            (shared_k_range[0] <= addr < shared_k_range[1]) or
            (shared_v_range[0] <= addr < shared_v_range[1])
        )
        
        # Ramulator2-compatible line (strip timestamp and req_id)
        ram_line = f"{op} {addr} {addr_vec}"
        
        if is_shared:
            # Shared access -> shared node
            node_traces[shared_node].append(ram_line)
            per_node_stats[shared_node]['local'] += 1
            stats['shared_accesses'] += 1
            
            # If it's a read from a private user, generate cross-node event
            if op.startswith('R'):
                requesting_private = private_node_ids[req_id % num_private]
                cross_line = f"P2P_READ {shared_node} {requesting_private} {addr} {timestamp} {req_id}"
                cross_node_trace.append(cross_line)
                stats['cross_node_reads'] += 1
                per_node_stats[shared_node]['remote_out'] += 1
                per_node_stats[requesting_private]['remote_in'] += 1
        else:
            # Private access -> distributed by req_id
            private_idx = req_id % num_private
            target_node = private_node_ids[private_idx]
            node_traces[target_node].append(ram_line)
            per_node_stats[target_node]['local'] += 1
            stats['private_accesses'] += 1
        
        stats['total_lines'] += 1
    
    # Write per-node traces
    print(f"\n  Writing per-node trace files...")
    for nid in range(num_nodes):
        trace_path = os.path.join(output_dir, f"node_{nid}.trace")
        with open(trace_path, 'w') as f:
            f.write('\n'.join(node_traces[nid]))
            if node_traces[nid]:
                f.write('\n')
        entries = len(node_traces[nid])
        size_mb = os.path.getsize(trace_path) / 1024 / 1024
        print(f"    Node {nid}: {entries:,} entries ({size_mb:.1f} MB)")
    
    # Write cross-node trace
    cross_path = os.path.join(output_dir, "cross_node.trace")
    with open(cross_path, 'w') as f:
        f.write('\n'.join(cross_node_trace))
        if cross_node_trace:
            f.write('\n')
    print(f"    Cross-node: {len(cross_node_trace):,} entries")
    
    # Validation
    total_split = sum(len(node_traces[nid]) for nid in range(num_nodes))
    print(f"\n  Validation:")
    print(f"    Input lines:  {stats['total_lines']:,}")
    print(f"    Split total:  {total_split:,}")
    print(f"    Cross-node:   {len(cross_node_trace):,}")
    
    mismatch = stats['total_lines'] - total_split
    if mismatch == 0:
        print(f"    ✅ Line count matches!")
    else:
        print(f"    ⚠️ Mismatch: {mismatch} lines")
    
    # Save summary
    summary = {
        'input': input_path,
        'config': config_path,
        'num_nodes': num_nodes,
        'shared_node': shared_node,
        'private_nodes': private_node_ids,
        'total_lines': stats['total_lines'],
        'shared_accesses': stats['shared_accesses'],
        'private_accesses': stats['private_accesses'],
        'cross_node_reads': stats['cross_node_reads'],
        'per_node': {
            nid: {
                'entries': len(node_traces[nid]),
                'local': per_node_stats[nid]['local'],
                'remote_in': per_node_stats[nid]['remote_in'],
                'remote_out': per_node_stats[nid]['remote_out'],
            }
            for nid in range(num_nodes)
        },
    }
    
    summary_path = os.path.join(output_dir, "split_summary.json")
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Summary saved to: {summary_path}")
    
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Split multi-tenant trace by CXL node"
    )
    parser.add_argument("--input", type=str, required=True,
                        help="Input multi-tenant trace file")
    parser.add_argument("--config", type=str, default="ramulator2/cxl_disagg_config.yaml",
                        help="CXL fabric configuration")
    parser.add_argument("--output_dir", type=str, required=True,
                        help="Output directory for per-node traces")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print(" DisaggKV Trace Splitter")
    print(" Phase 5.2 - LKC-CXL-PIM Project")
    print("=" * 70)
    
    summary = split_trace(args.input, args.config, args.output_dir)
    
    print("\n" + "=" * 70)
    print(" Split Complete")
    print("=" * 70)
    print(f"  Shared:   {summary['shared_accesses']:,} accesses")
    print(f"  Private:  {summary['private_accesses']:,} accesses")
    print(f"  Cross:    {summary['cross_node_reads']:,} P2P reads")
    print(f"  Output:   {args.output_dir}/")
    print("=" * 70)


if __name__ == "__main__":
    main()
