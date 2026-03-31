#!/usr/bin/env python3
"""
fault_tolerant_simulator.py - CXL Link Fault Injection & Recovery Simulator

Simulates random CXL Link failures and models PIM-side fault recovery
using Erasure Coding (Reed-Solomon) or Parity (XOR) schemes.

This produces the "Fault Recovery Latency" chart for the paper — a rare
but highly impactful evaluation dimension for system conferences.

Fault Model:
  - Random CXL Link Drop events (Poisson process, configurable MTBF)
  - Fault duration: Uniform[min_ms, max_ms]
  - Types: LINK_DOWN (complete), DEGRADED (50% bandwidth)

Recovery Model:
  - Parity:  XOR reconstruction from partner node
             recovery_time = data_size / reduced_bw + xor_cycles
  - Erasure: RS(k,m) decode from k out of (k+m) blocks
             recovery_time = data_size / reduced_bw + decode_cycles

Output:
  - Per-fault recovery latency log
  - Recovery latency distribution (for paper figure)
  - System availability statistics

Usage:
  python scripts/fault_tolerant_simulator.py \\
    --config ramulator2/cxl_disagg_config.yaml \\
    --duration_s 3600 \\
    --output results/fault_recovery_results.json

Author: LKC-CXL-PIM Project (Phase 5.2)
"""

import os
import sys
import json
import argparse
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum, auto

import yaml
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


# ==============================================================================
# Data Types
# ==============================================================================

class FaultType(Enum):
    LINK_DOWN = auto()      # Complete link failure
    DEGRADED = auto()       # 50% bandwidth degradation


class RecoveryScheme(Enum):
    PARITY = auto()
    ERASURE_CODING = auto()


@dataclass
class FaultEvent:
    """A single CXL Link fault event."""
    fault_id: int
    node_id: int               # Affected node
    start_time_s: float        # When fault starts
    duration_s: float          # How long fault lasts
    fault_type: FaultType
    
    # Recovery results (filled after recovery)
    recovery_start_s: float = 0.0
    recovery_latency_ms: float = 0.0
    data_recovered_mb: float = 0.0
    scheme_used: str = ""
    
    @property
    def end_time_s(self) -> float:
        return self.start_time_s + self.duration_s
    
    @property
    def total_downtime_ms(self) -> float:
        return (self.duration_s + self.recovery_latency_ms / 1000.0) * 1000.0


@dataclass
class NodeState:
    """Runtime state of a CXL-PIM node."""
    node_id: int
    is_online: bool = True
    kv_cache_mb: float = 256.0  # Resident KV-Cache size
    bandwidth_gbps: float = 64.0
    parity_partner: int = -1     # Partner node for XOR parity


# ==============================================================================
# Fault Injection Engine
# ==============================================================================

class FaultInjector:
    """
    Generates random CXL Link fault events via Poisson process.
    """
    
    def __init__(
        self,
        num_nodes: int,
        mtbf_seconds: float = 3600,
        duration_min_ms: float = 1.0,
        duration_max_ms: float = 10.0,
        seed: int = 42
    ):
        self.num_nodes = num_nodes
        self.mtbf_seconds = mtbf_seconds
        self.duration_min_ms = duration_min_ms
        self.duration_max_ms = duration_max_ms
        self.rng = np.random.default_rng(seed)
    
    def generate_faults(self, simulation_duration_s: float) -> List[FaultEvent]:
        """
        Generate fault events for the entire simulation duration.
        
        Per-node MTBF = system_MTBF * num_nodes (faults are independent).
        """
        faults = []
        fault_id = 0
        
        # Per-node fault rate
        per_node_rate = 1.0 / (self.mtbf_seconds * self.num_nodes)
        
        current_time = 0.0
        while current_time < simulation_duration_s:
            # Next fault time (exponential inter-arrival)
            interval = self.rng.exponential(1.0 / (per_node_rate * self.num_nodes))
            current_time += interval
            
            if current_time >= simulation_duration_s:
                break
            
            # Random node
            node_id = self.rng.integers(0, self.num_nodes)
            
            # Fault duration (uniform)
            duration_ms = self.rng.uniform(self.duration_min_ms, self.duration_max_ms)
            duration_s = duration_ms / 1000.0
            
            # Fault type (80% LINK_DOWN, 20% DEGRADED)
            fault_type = FaultType.LINK_DOWN if self.rng.random() < 0.8 else FaultType.DEGRADED
            
            faults.append(FaultEvent(
                fault_id=fault_id,
                node_id=node_id,
                start_time_s=current_time,
                duration_s=duration_s,
                fault_type=fault_type,
            ))
            fault_id += 1
        
        return faults


# ==============================================================================
# Recovery Engine
# ==============================================================================

class RecoveryEngine:
    """
    Models PIM-side fault recovery mechanisms.
    
    Parity (XOR):
      - Partner node holds XOR of its data with failed node's data
      - Recovery = read partner data + XOR compute
      - Latency = data_size / partner_bw + xor_cycles_per_mb * data_size
    
    Erasure Coding (RS):
      - k data blocks + m parity blocks distributed across nodes
      - Need any k blocks to reconstruct
      - Latency = data_size / (k * node_bw) + decode_cycles_per_mb * data_size
    """
    
    # Hardware timing parameters (derived from ASIC @7nm estimates)
    XOR_CYCLES_PER_MB = 0.01    # ms per MB for XOR parity
    RS_DECODE_CYCLES_PER_MB = 0.1  # ms per MB for RS decode (more complex)
    
    def __init__(
        self,
        scheme: RecoveryScheme,
        num_nodes: int,
        node_bandwidth_gbps: float = 64.0,
        parity_group_size: int = 2,
        erasure_k: int = 4,
        erasure_m: int = 2,
    ):
        self.scheme = scheme
        self.num_nodes = num_nodes
        self.node_bandwidth_gbps = node_bandwidth_gbps
        self.parity_group_size = parity_group_size
        self.erasure_k = erasure_k
        self.erasure_m = erasure_m
    
    def recover(self, fault: FaultEvent, kv_cache_mb: float) -> FaultEvent:
        """
        Compute recovery latency for a given fault.
        
        Returns:
            Updated FaultEvent with recovery metrics.
        """
        fault.recovery_start_s = fault.end_time_s
        
        if self.scheme == RecoveryScheme.PARITY:
            fault = self._recover_parity(fault, kv_cache_mb)
        elif self.scheme == RecoveryScheme.ERASURE_CODING:
            fault = self._recover_erasure(fault, kv_cache_mb)
        
        return fault
    
    def _recover_parity(self, fault: FaultEvent, data_mb: float) -> FaultEvent:
        """XOR parity recovery from partner node."""
        # Transfer time: read from partner
        # During recovery, use CXL bandwidth (possibly degraded)
        effective_bw_gbps = self.node_bandwidth_gbps
        if fault.fault_type == FaultType.DEGRADED:
            effective_bw_gbps *= 0.5
        
        transfer_time_ms = (data_mb / 1024) / (effective_bw_gbps / 8) * 1000
        
        # XOR compute time
        compute_time_ms = data_mb * self.XOR_CYCLES_PER_MB
        
        fault.recovery_latency_ms = transfer_time_ms + compute_time_ms
        fault.data_recovered_mb = data_mb
        fault.scheme_used = "parity"
        
        return fault
    
    def _recover_erasure(self, fault: FaultEvent, data_mb: float) -> FaultEvent:
        """Reed-Solomon erasure coding recovery."""
        # Need to read from k other nodes
        effective_bw_gbps = self.node_bandwidth_gbps
        if fault.fault_type == FaultType.DEGRADED:
            effective_bw_gbps *= 0.5
        
        # Data per block
        block_mb = data_mb / self.erasure_k
        
        # Transfer time: read k blocks (from k surviving nodes, parallel)
        transfer_time_ms = (block_mb / 1024) / (effective_bw_gbps / 8) * 1000
        
        # RS decode time (more expensive than XOR)
        compute_time_ms = data_mb * self.RS_DECODE_CYCLES_PER_MB
        
        fault.recovery_latency_ms = transfer_time_ms + compute_time_ms
        fault.data_recovered_mb = data_mb
        fault.scheme_used = "erasure_coding"
        
        return fault


# ==============================================================================
# Fault Tolerance Simulator
# ==============================================================================

class FaultToleranceSimulator:
    """
    Complete fault tolerance simulation pipeline.
    """
    
    def __init__(self, config_path: str):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        fabric_cfg = config['CXLFabric']
        ft_cfg = fabric_cfg.get('fault_tolerance', {})
        
        self.num_nodes = fabric_cfg['num_nodes']
        self.mtbf_seconds = ft_cfg.get('mtbf_seconds', 3600)
        
        # Recovery scheme
        scheme_str = ft_cfg.get('scheme', 'parity')
        self.scheme = (RecoveryScheme.ERASURE_CODING 
                       if scheme_str == 'erasure_coding' 
                       else RecoveryScheme.PARITY)
        
        # Injector
        self.injector = FaultInjector(
            num_nodes=self.num_nodes,
            mtbf_seconds=self.mtbf_seconds,
            duration_min_ms=ft_cfg.get('fault_duration_ms_min', 1.0),
            duration_max_ms=ft_cfg.get('fault_duration_ms_max', 10.0),
        )
        
        # Recovery engine
        port_bw = fabric_cfg.get('switch', {}).get('port_bandwidth_gbps', 64.0)
        self.recovery = RecoveryEngine(
            scheme=self.scheme,
            num_nodes=self.num_nodes,
            node_bandwidth_gbps=port_bw,
            parity_group_size=ft_cfg.get('parity_group_size', 2),
            erasure_k=ft_cfg.get('erasure_k', 4),
            erasure_m=ft_cfg.get('erasure_m', 2),
        )
        
        # Node states
        self.nodes = {}
        for node_cfg in fabric_cfg['nodes']:
            nid = node_cfg['node_id']
            self.nodes[nid] = NodeState(
                node_id=nid,
                kv_cache_mb=node_cfg.get('capacity_gb', 16.0) * 1024 * 0.1,  # 10% utilized
            )
        
        # Set parity partners (ring pairing)
        for i in range(self.num_nodes):
            self.nodes[i].parity_partner = (i + 1) % self.num_nodes
    
    def simulate(self, duration_s: float, seed: int = 42) -> Dict:
        """Run fault tolerance simulation."""
        self.injector.rng = np.random.default_rng(seed)
        
        # Generate faults
        faults = self.injector.generate_faults(duration_s)
        
        print(f"  Generated {len(faults)} fault events over {duration_s:.0f}s")
        print(f"  Expected: ~{duration_s / self.mtbf_seconds:.1f} faults "
              f"(MTBF={self.mtbf_seconds}s)")
        
        # Process recovery for each fault
        for fault in faults:
            node = self.nodes[fault.node_id]
            self.recovery.recover(fault, node.kv_cache_mb)
        
        # Compile results
        return self._compile_results(faults, duration_s)
    
    def _compile_results(self, faults: List[FaultEvent], duration_s: float) -> Dict:
        """Compile simulation results."""
        if not faults:
            return {
                'duration_s': duration_s,
                'total_faults': 0,
                'scheme': self.scheme.name,
                'message': 'No faults occurred during simulation',
            }
        
        recovery_latencies = [f.recovery_latency_ms for f in faults]
        downtimes = [f.total_downtime_ms for f in faults]
        
        results = {
            'config': {
                'num_nodes': self.num_nodes,
                'mtbf_seconds': self.mtbf_seconds,
                'scheme': self.scheme.name,
                'duration_s': duration_s,
            },
            'summary': {
                'total_faults': len(faults),
                'link_down_count': sum(1 for f in faults if f.fault_type == FaultType.LINK_DOWN),
                'degraded_count': sum(1 for f in faults if f.fault_type == FaultType.DEGRADED),
                'faults_per_node': {
                    nid: sum(1 for f in faults if f.node_id == nid)
                    for nid in range(self.num_nodes)
                },
            },
            'recovery_latency_ms': {
                'mean': float(np.mean(recovery_latencies)),
                'median': float(np.median(recovery_latencies)),
                'p95': float(np.percentile(recovery_latencies, 95)),
                'p99': float(np.percentile(recovery_latencies, 99)),
                'max': float(np.max(recovery_latencies)),
                'min': float(np.min(recovery_latencies)),
            },
            'downtime_ms': {
                'mean': float(np.mean(downtimes)),
                'total': float(np.sum(downtimes)),
            },
            'availability': {
                'total_downtime_s': float(np.sum(downtimes) / 1000),
                'uptime_percent': float(
                    (1 - np.sum(downtimes) / 1000 / duration_s) * 100
                ),
            },
            'fault_log': [
                {
                    'id': int(f.fault_id),
                    'node': int(f.node_id),
                    'time_s': round(float(f.start_time_s), 3),
                    'duration_ms': round(float(f.duration_s * 1000), 2),
                    'type': f.fault_type.name,
                    'recovery_ms': round(float(f.recovery_latency_ms), 4),
                    'total_downtime_ms': round(float(f.total_downtime_ms), 4),
                    'scheme': f.scheme_used,
                }
                for f in faults
            ],
        }
        
        return results
    
    def plot_recovery_latency(
        self,
        results: Dict,
        output: str
    ):
        """Generate recovery latency distribution plot for paper."""
        fault_log = results.get('fault_log', [])
        if not fault_log:
            print("  No faults to plot")
            return
        
        recovery_ms = [f['recovery_ms'] for f in fault_log]
        downtime_ms = [f['total_downtime_ms'] for f in fault_log]
        
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        # Recovery latency histogram
        axes[0].hist(recovery_ms, bins=30, color='#E74C3C', edgecolor='#C0392B', alpha=0.85)
        axes[0].set_xlabel('Recovery Latency (ms)', fontsize=12)
        axes[0].set_ylabel('Count', fontsize=12)
        axes[0].set_title('PIM Fault Recovery Latency', fontsize=13, fontweight='bold')
        axes[0].axvline(np.mean(recovery_ms), color='#2C3E50', linestyle='--',
                       label=f'Mean: {np.mean(recovery_ms):.3f} ms')
        axes[0].axvline(np.percentile(recovery_ms, 99), color='#F39C12', linestyle=':',
                       label=f'P99: {np.percentile(recovery_ms, 99):.3f} ms')
        axes[0].legend(fontsize=10)
        
        # Total downtime per fault
        fault_ids = [f['id'] for f in fault_log]
        colors = ['#E74C3C' if f['type'] == 'LINK_DOWN' else '#3498DB' for f in fault_log]
        axes[1].bar(fault_ids, downtime_ms, color=colors, alpha=0.85)
        axes[1].set_xlabel('Fault Event ID', fontsize=12)
        axes[1].set_ylabel('Total Downtime (ms)', fontsize=12)
        axes[1].set_title('Per-Fault System Impact', fontsize=13, fontweight='bold')
        
        # Legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#E74C3C', label='LINK_DOWN'),
            Patch(facecolor='#3498DB', label='DEGRADED'),
        ]
        axes[1].legend(handles=legend_elements, fontsize=10)
        
        plt.tight_layout()
        os.makedirs(os.path.dirname(output) if os.path.dirname(output) else ".", exist_ok=True)
        plt.savefig(output, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Saved plot: {output}")


# ==============================================================================
# Main
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="CXL Link Fault Injection & Recovery Simulator"
    )
    parser.add_argument("--config", type=str, default="ramulator2/cxl_disagg_config.yaml")
    parser.add_argument("--duration_s", type=float, default=3600,
                        help="Simulation duration in seconds")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default="results/fault_recovery_results.json")
    parser.add_argument("--plot", type=str, default="",
                        help="Output path for recovery latency plot")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print(" DisaggKV Fault Tolerance Simulator")
    print(" Phase 5.2 - LKC-CXL-PIM Project")
    print("=" * 70)
    
    sim = FaultToleranceSimulator(args.config)
    
    print(f"  Nodes:         {sim.num_nodes}")
    print(f"  MTBF:          {sim.mtbf_seconds}s")
    print(f"  Scheme:        {sim.scheme.name}")
    print(f"  Duration:      {args.duration_s}s")
    
    print(f"\n[1/2] Simulating faults and recovery...")
    results = sim.simulate(args.duration_s, args.seed)
    
    # Save results
    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    print(f"\n[2/2] Results Summary")
    print("=" * 70)
    
    if results.get('total_faults', 0) == 0 and 'summary' not in results:
        print("  No faults occurred during simulation.")
    else:
        s = results['summary']
        r = results['recovery_latency_ms']
        a = results['availability']
        
        print(f"  Total faults:       {s['total_faults']}")
        print(f"    LINK_DOWN:        {s['link_down_count']}")
        print(f"    DEGRADED:         {s['degraded_count']}")
        print(f"\n  Recovery Latency:")
        print(f"    Mean:             {r['mean']:.4f} ms")
        print(f"    Median:           {r['median']:.4f} ms")
        print(f"    P99:              {r['p99']:.4f} ms")
        print(f"    Max:              {r['max']:.4f} ms")
        print(f"\n  System Availability:")
        print(f"    Uptime:           {a['uptime_percent']:.6f}%")
        print(f"    Total downtime:   {a['total_downtime_s']:.3f}s")
        
        print(f"\n  📊 Paper Highlight:")
        print(f"     Recovery ≤ {r['p99']:.2f}ms (P99)")
        print(f"     System availability: {a['uptime_percent']:.4f}%")
    
    # Plot if requested
    plot_path = args.plot or args.output.replace('.json', '_plot.png')
    if results.get('summary', {}).get('total_faults', 0) > 0:
        sim.plot_recovery_latency(results, plot_path)
    
    print(f"\n  Results: {args.output}")
    print("=" * 70)


if __name__ == "__main__":
    main()
