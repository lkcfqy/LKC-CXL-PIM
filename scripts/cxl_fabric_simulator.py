#!/usr/bin/env python3
"""
cxl_fabric_simulator.py - CXL 3.0 Fabric Network Simulator

Event-driven simulator for multi-node CXL 3.0 disaggregated memory architecture.
Models CXL Switch queuing delays, port contention, P2P routing, and cross-node
data transfers for the DisaggKV architecture.

Architecture:
  Python event-driven simulator wraps multiple Ramulator2 instances (one per node).
  CXL Switch and P2P routing are modeled at the system level (μs granularity),
  while per-node DRAM access is modeled by Ramulator2 (ns granularity).

Key Components:
  - CXLSwitchNode: M/D/1 queuing model with port contention
  - P2PRoutingLogic: Star/Ring/Fat-Tree topology routing
  - CXLFabricSimulator: Top-level orchestrator

Usage:
  python scripts/cxl_fabric_simulator.py \\
    --config ramulator2/cxl_disagg_config.yaml \\
    --trace traces/multitenant/multi_tenant_50req.trace \\
    --num_nodes 4 \\
    --output results/cxl_4node_results.json

Author: LKC-CXL-PIM Project (Phase 5.2)
"""

import os
import sys
import json
import argparse
import heapq
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from enum import Enum, auto

import yaml
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ==============================================================================
# Data Types
# ==============================================================================

class EventType(Enum):
    """Types of events in the CXL Fabric simulation."""
    LOCAL_MEM_ACCESS = auto()      # Local HBM access within a node
    SWITCH_ENQUEUE = auto()        # Packet enters CXL Switch
    SWITCH_DEQUEUE = auto()        # Packet exits CXL Switch
    P2P_SEND = auto()              # P2P data transfer initiation
    P2P_RECEIVE = auto()           # P2P data received at destination
    PIM_SEND_PARTIAL = auto()      # PIM sends partial Attention result
    PIM_REDUCE_ATTN = auto()       # PIM receives and reduces Attention
    SYNC_BARRIER_WAIT = auto()     # Node waiting at sync barrier
    SYNC_BARRIER_RELEASE = auto()  # Sync barrier released


@dataclass(order=True)
class Event:
    """A simulation event, ordered by timestamp for the priority queue."""
    timestamp_ns: int
    event_type: EventType = field(compare=False)
    src_node: int = field(compare=False)
    dst_node: int = field(compare=False, default=-1)
    req_id: int = field(compare=False, default=-1)
    data_bytes: int = field(compare=False, default=64)
    payload: dict = field(compare=False, default_factory=dict)


@dataclass
class SwitchPort:
    """A single port on the CXL Switch."""
    port_id: int
    connected_node: int
    queue: List[Event] = field(default_factory=list)
    bandwidth_gbps: float = 64.0
    queue_depth: int = 64
    
    # Statistics
    total_packets: int = 0
    total_bytes: int = 0
    total_queue_delay_ns: int = 0
    max_queue_depth: int = 0
    congestion_events: int = 0
    
    @property
    def busy_until_ns(self) -> int:
        """When the port will be free based on current queue."""
        if not self.queue:
            return 0
        return self.queue[-1].timestamp_ns
    
    def transfer_time_ns(self, data_bytes: int) -> int:
        """Calculate transfer time for given data size."""
        # bandwidth_gbps -> bytes/ns
        bytes_per_ns = self.bandwidth_gbps * 1e9 / 8 / 1e9  # = gbps / 8
        return max(1, int(data_bytes / bytes_per_ns))


# ==============================================================================
# CXL Switch Node
# ==============================================================================

class CXLSwitchNode:
    """
    CXL 3.0 Switch model with M/D/1 queuing and port contention.
    
    Each port has:
    - Base wire latency (fixed)
    - Queuing delay (depends on contention)
    - Bandwidth-limited transfer time (depends on data size)
    
    Congestion occurs when multiple packets target the same egress port
    simultaneously.
    """
    
    def __init__(self, config: dict):
        self.base_latency_ns = config.get('base_latency_ns', 150)
        self.per_hop_ns = config.get('per_hop_ns', 50)
        self.port_bandwidth_gbps = config.get('port_bandwidth_gbps', 64.0)
        self.queue_depth = config.get('queue_depth', 64)
        
        self.ports: Dict[int, SwitchPort] = {}
        self.stats = defaultdict(int)
        
        # Per-port busy-until tracker (for queuing model)
        self._port_busy_until: Dict[int, int] = {}
    
    def add_port(self, port_id: int, connected_node: int):
        """Add a port connected to a CXL-PIM node."""
        self.ports[port_id] = SwitchPort(
            port_id=port_id,
            connected_node=connected_node,
            bandwidth_gbps=self.port_bandwidth_gbps,
            queue_depth=self.queue_depth
        )
        self._port_busy_until[port_id] = 0
    
    def route_packet(
        self,
        event: Event,
        current_time_ns: int
    ) -> Tuple[int, int]:
        """
        Route a packet through the switch and compute total delay.
        
        Returns:
            (arrival_time_ns, queue_delay_ns)
        """
        dst_port = self._find_port(event.dst_node)
        if dst_port is None:
            return (current_time_ns + self.base_latency_ns, 0)
        
        port = self.ports[dst_port]
        
        # Transfer time based on data size
        transfer_ns = port.transfer_time_ns(event.data_bytes)
        
        # Queuing delay: if port is busy, packet must wait
        queue_delay = max(0, self._port_busy_until[dst_port] - current_time_ns)
        
        # Total latency = base + queue + transfer  
        total_delay = self.base_latency_ns + queue_delay + transfer_ns
        arrival_time = current_time_ns + total_delay
        
        # Update port busy-until
        self._port_busy_until[dst_port] = max(
            self._port_busy_until[dst_port],
            current_time_ns + self.base_latency_ns
        ) + transfer_ns
        
        # Update statistics
        port.total_packets += 1
        port.total_bytes += event.data_bytes
        port.total_queue_delay_ns += queue_delay
        if queue_delay > 0:
            port.congestion_events += 1
        
        self.stats['total_packets'] += 1
        self.stats['total_bytes'] += event.data_bytes
        self.stats['total_queue_delay_ns'] += queue_delay
        if queue_delay > 0:
            self.stats['congestion_events'] += 1
        
        return (arrival_time, queue_delay)
    
    def _find_port(self, node_id: int) -> Optional[int]:
        """Find port connected to given node."""
        for port_id, port in self.ports.items():
            if port.connected_node == node_id:
                return port_id
        return None
    
    def get_stats(self) -> Dict:
        """Return switch-level and per-port statistics."""
        result = dict(self.stats)
        result['per_port'] = {}
        for port_id, port in self.ports.items():
            result['per_port'][port_id] = {
                'node': port.connected_node,
                'packets': port.total_packets,
                'bytes': port.total_bytes,
                'avg_queue_delay_ns': (
                    port.total_queue_delay_ns / max(port.total_packets, 1)
                ),
                'congestion_events': port.congestion_events,
            }
        
        total_pkts = self.stats.get('total_packets', 1)
        result['avg_queue_delay_ns'] = self.stats.get('total_queue_delay_ns', 0) / max(total_pkts, 1)
        result['congestion_rate'] = self.stats.get('congestion_events', 0) / max(total_pkts, 1)
        return result


# ==============================================================================
# P2P Routing Logic
# ==============================================================================

class P2PRoutingLogic:
    """
    CXL Type 3 device-to-device routing.
    
    Supports three topologies:
    - Star: All nodes connect to a central switch (1 hop each)
    - Ring: Nodes form a ring (1-N/2 hops)
    - Fat-Tree: Two-level tree (1-2 hops)
    """
    
    def __init__(self, topology: str, num_nodes: int, per_hop_ns: int = 50):
        self.topology = topology
        self.num_nodes = num_nodes
        self.per_hop_ns = per_hop_ns
        
        # Build routing table
        self.routing_table = self._build_routes()
    
    def _build_routes(self) -> Dict[Tuple[int, int], int]:
        """Build routing table: (src, dst) -> num_hops."""
        routes = {}
        n = self.num_nodes
        
        for src in range(n):
            for dst in range(n):
                if src == dst:
                    routes[(src, dst)] = 0
                elif self.topology == 'star':
                    routes[(src, dst)] = 2  # src->switch->dst
                elif self.topology == 'ring':
                    clockwise = (dst - src) % n
                    counterclockwise = (src - dst) % n
                    routes[(src, dst)] = min(clockwise, counterclockwise)
                elif self.topology == 'fat_tree':
                    # Simplified: same subtree = 2 hops, different = 4 hops
                    if (src // 2) == (dst // 2):
                        routes[(src, dst)] = 2
                    else:
                        routes[(src, dst)] = 4
                else:
                    routes[(src, dst)] = 2  # default star
        
        return routes
    
    def get_hops(self, src: int, dst: int) -> int:
        """Get number of hops between two nodes."""
        return self.routing_table.get((src, dst), 2)
    
    def get_p2p_latency_ns(self, src: int, dst: int) -> int:
        """Get P2P wire latency (excluding queuing)."""
        hops = self.get_hops(src, dst)
        return hops * self.per_hop_ns
    
    def get_route_description(self, src: int, dst: int) -> str:
        """Human-readable route description."""
        hops = self.get_hops(src, dst)
        if self.topology == 'star':
            return f"Node{src} -> Switch -> Node{dst} ({hops} hops)"
        elif self.topology == 'ring':
            return f"Node{src} -> ... -> Node{dst} ({hops} hops)"
        else:
            return f"Node{src} -> Tree -> Node{dst} ({hops} hops)"


# ==============================================================================
# Synchronization Barrier
# ==============================================================================

class SynchronizationBarrier:
    """
    Global synchronization barrier for distributed PIM operations.
    
    All nodes must reach the barrier before any can proceed.
    Tracks stall cycles for each node.
    """
    
    def __init__(self, num_nodes: int):
        self.num_nodes = num_nodes
        self.barrier_id = 0
        
        # Per-barrier tracking
        self._arrived: Dict[int, Dict[int, int]] = {}  # barrier_id -> {node_id: arrival_time}
        
        # Statistics
        self.total_barriers = 0
        self.total_stall_ns = 0
        self.max_stall_ns = 0
        self.stall_per_barrier: List[int] = []
    
    def arrive(self, node_id: int, timestamp_ns: int, barrier_id: int) -> Optional[int]:
        """
        A node arrives at the barrier.
        
        Returns:
            Release timestamp if all nodes have arrived, None otherwise.
        """
        if barrier_id not in self._arrived:
            self._arrived[barrier_id] = {}
        
        self._arrived[barrier_id][node_id] = timestamp_ns
        
        # Check if all nodes have arrived
        if len(self._arrived[barrier_id]) >= self.num_nodes:
            return self._release(barrier_id)
        
        return None
    
    def _release(self, barrier_id: int) -> int:
        """Release all nodes from the barrier."""
        arrivals = self._arrived[barrier_id]
        release_time = max(arrivals.values())
        
        # Calculate stall for each node
        total_stall = 0
        for node_id, arrival in arrivals.items():
            stall = release_time - arrival
            total_stall += stall
        
        self.total_barriers += 1
        self.total_stall_ns += total_stall
        self.max_stall_ns = max(self.max_stall_ns, total_stall)
        self.stall_per_barrier.append(total_stall)
        
        # Cleanup
        del self._arrived[barrier_id]
        
        return release_time
    
    def get_stats(self) -> Dict:
        avg_stall = self.total_stall_ns / max(self.total_barriers, 1)
        return {
            'total_barriers': self.total_barriers,
            'total_stall_ns': self.total_stall_ns,
            'avg_stall_per_barrier_ns': avg_stall,
            'max_stall_ns': self.max_stall_ns,
        }


# ==============================================================================
# CXL Node (wraps per-node state)
# ==============================================================================

@dataclass
class CXLPIMNode:
    """Represents a single CXL-PIM node in the fabric."""
    node_id: int
    role: str                       # shared_kv | private_kv
    hbm_config: str                 # Path to Ramulator2 YAML config
    capacity_gb: float = 16.0
    
    # Per-node trace entries
    trace_entries: List[str] = field(default_factory=list)
    
    # Statistics
    local_accesses: int = 0
    remote_reads_in: int = 0        # P2P reads received from other nodes
    remote_reads_out: int = 0       # P2P reads sent to other nodes
    p2p_send_partial: int = 0       # PIM_SEND_PARTIAL operations
    p2p_reduce_attn: int = 0        # PIM_REDUCE_ATTN operations
    total_local_cycles: int = 0


# ==============================================================================
# CXL Fabric Simulator (Top-Level)
# ==============================================================================

class CXLFabricSimulator:
    """
    Top-level CXL 3.0 Fabric simulator.
    
    Orchestrates:
    1. Trace splitting across nodes
    2. CXL Switch queuing simulation
    3. P2P routing for cross-node accesses
    4. Synchronization barriers for distributed attention
    5. Statistics collection
    """
    
    def __init__(self, config_path: str):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        fabric_cfg = self.config['CXLFabric']
        self.num_nodes = fabric_cfg['num_nodes']
        self.topology = fabric_cfg.get('topology', 'star')
        
        # Initialize components
        switch_cfg = fabric_cfg['switch']
        self.switch = CXLSwitchNode(switch_cfg)
        for i in range(self.num_nodes):
            self.switch.add_port(i, i)
        
        self.router = P2PRoutingLogic(
            self.topology, self.num_nodes,
            per_hop_ns=switch_cfg.get('per_hop_ns', 50)
        )
        
        self.barrier = SynchronizationBarrier(self.num_nodes)
        
        # Initialize nodes
        self.nodes: Dict[int, CXLPIMNode] = {}
        for node_cfg in fabric_cfg['nodes']:
            node = CXLPIMNode(
                node_id=node_cfg['node_id'],
                role=node_cfg.get('role', 'private_kv'),
                hbm_config=node_cfg.get('hbm_config', 'hbm3_pim_kv.yaml'),
                capacity_gb=node_cfg.get('capacity_gb', 16.0),
            )
            self.nodes[node.node_id] = node
        
        # PIM extension config
        pim_cfg = fabric_cfg.get('pim_extensions', {})
        self.partial_sum_bytes = pim_cfg.get('partial_sum_bytes', 2048)
        self.enable_distributed_softmax = pim_cfg.get('distributed_softmax', True)
        
        # Event queue (min-heap by timestamp)
        self.event_queue: List[Event] = []
        
        # Global statistics
        self.stats = defaultdict(int)
        self.p2p_transfers: List[Dict] = []
    
    def load_and_split_trace(
        self,
        trace_path: str,
        shared_node_id: int = 0
    ):
        """
        Load a multi-tenant trace and split across nodes.
        
        Splitting strategy:
        - Shared prefix reads (from shared address range) -> shared_kv node
        - Private KV accesses -> distributed across private_kv nodes by req_id
        - Cross-node reads generate P2P events
        """
        print(f"  Loading trace: {trace_path}")
        
        with open(trace_path, 'r') as f:
            lines = f.readlines()
        
        print(f"  Total trace lines: {len(lines):,}")
        
        # Determine shared node
        shared_nodes = [n for n in self.nodes.values() if n.role == 'shared_kv']
        private_nodes = [n for n in self.nodes.values() if n.role == 'private_kv']
        
        if not shared_nodes:
            shared_nodes = [self.nodes[0]]
        if not private_nodes:
            private_nodes = list(self.nodes.values())[1:]
        
        shared_node = shared_nodes[0]
        num_private = len(private_nodes)
        
        # Parse and distribute
        for line in tqdm(lines, desc="  Splitting trace", unit="line", 
                        mininterval=1.0, disable=len(lines) < 10000):
            line = line.strip()
            if not line:
                continue
            
            parts = line.split()
            if len(parts) < 3:
                continue
            
            op = parts[0]
            addr = int(parts[1])
            addr_vec = parts[2]
            timestamp_ns = int(parts[3]) if len(parts) > 3 else 0
            req_id = int(parts[4]) if len(parts) > 4 else 0
            
            # Determine target node based on address range.
            #
            # Address layout (aligned with generate_prefix_sharing_trace.py):
            #   SHARED_K:  0x10000000 - 0x20000000  (only used by prefix_sharing traces)
            #   PRIVATE_K: 0x20000000+              (used by both trace types)
            #   SHARED_V:  0x40000000 - 0x50000000  (only used by prefix_sharing traces)
            #   PRIVATE_V: 0x50000000+              (used by both trace types)
            #
            # For multitenant traces (generate_multitenant_trace.py):
            #   K_SPACE:   0x10000000+  (ALL are private, V_SPACE starts at 0x20000000)
            #   These traces do NOT have a shared region; all accesses are private.
            #
            # We detect trace type by the presence of the V gap at 0x40000000:
            #   - If trace has addresses >= 0x40000000, it's prefix_sharing → shared detection valid
            #   - If ALL V addresses are 0x20000000-0x3FFFFFFF, it's multitenant → no shared
            SHARED_K_BASE = 0x10000000
            SHARED_K_END  = 0x20000000
            SHARED_V_BASE = 0x40000000
            SHARED_V_END  = 0x50000000
            
            is_shared_access = (
                (SHARED_K_BASE <= addr < SHARED_K_END and addr < SHARED_K_END) or
                (SHARED_V_BASE <= addr < SHARED_V_END)
            )
            
            # Heuristic: for multitenant traces, V addresses start at 0x20000000
            # (below SHARED_V_BASE). In that case, K addresses in 0x10000000-0x20000000
            # are NOT shared — they are regular private K cache.
            # We detect this by checking if any V_SPACE addresses exist in the
            # expected multitenant range (0x20000000-0x3FFFFFFF).
            # For simplicity, we check the current access: if this is a K-space access
            # and the trace's V space uses the low range, mark as private.
            if is_shared_access and (0x10000000 <= addr < 0x20000000):
                # Only treat as shared if this address is in the DEDICATED shared
                # prefix range. For multitenant traces where *all* K starts at 0x10000000,
                # we need the trace to explicitly use the prefix_sharing layout.
                # We check: does the trace have any V addresses >= 0x40000000?
                # As a conservative default, if the request has private K in 0x20000000+,
                # then 0x10000000 addresses are truly shared prefixes.
                # Otherwise, treat all as private.
                if not hasattr(self, '_has_prefix_sharing_layout'):
                    # Scan a sample of the trace to detect layout
                    self._has_prefix_sharing_layout = any(
                        int(l.split()[1]) >= 0x40000000
                        for l in lines[:min(5000, len(lines))]
                        if l.strip() and len(l.split()) >= 2
                    )
                if not self._has_prefix_sharing_layout:
                    is_shared_access = False
            
            if is_shared_access:
                target_node = shared_node.node_id
            else:
                # Distribute private accesses by req_id
                private_idx = req_id % num_private
                target_node = private_nodes[private_idx].node_id
            
            # Create local trace entry (strip timestamp/req_id for Ramulator2)
            local_line = f"{op} {addr} {addr_vec}"
            self.nodes[target_node].trace_entries.append(local_line)
            self.nodes[target_node].local_accesses += 1
            
            # If a private node needs to read shared data, generate P2P event
            if is_shared_access and op.startswith('R'):
                requesting_node = private_nodes[req_id % num_private].node_id
                if requesting_node != shared_node.node_id:
                    event = Event(
                        timestamp_ns=timestamp_ns,
                        event_type=EventType.P2P_SEND,
                        src_node=shared_node.node_id,
                        dst_node=requesting_node,
                        req_id=req_id,
                        data_bytes=64,
                    )
                    heapq.heappush(self.event_queue, event)
                    self.nodes[shared_node.node_id].remote_reads_out += 1
                    self.nodes[requesting_node].remote_reads_in += 1
        
        # Print distribution
        print(f"\n  Trace distribution:")
        for nid, node in self.nodes.items():
            print(f"    Node {nid} ({node.role}): {node.local_accesses:,} local, "
                  f"{node.remote_reads_in:,} remote_in, {node.remote_reads_out:,} remote_out")
    
    def simulate_network(self) -> Dict:
        """
        Run the event-driven network simulation.
        
        Processes all P2P events through the CXL Switch, computing
        queuing delays and congestion.
        """
        print(f"\n  Simulating CXL Fabric ({len(self.event_queue):,} network events)...")
        
        processed = 0
        total_events = len(self.event_queue)
        
        while self.event_queue:
            event = heapq.heappop(self.event_queue)
            
            if event.event_type == EventType.P2P_SEND:
                # Route through CXL Switch
                arrival_time, queue_delay = self.switch.route_packet(
                    event, event.timestamp_ns
                )
                
                # Record P2P transfer
                p2p_latency = arrival_time - event.timestamp_ns
                self.p2p_transfers.append({
                    'src': event.src_node,
                    'dst': event.dst_node,
                    'latency_ns': p2p_latency,
                    'queue_delay_ns': queue_delay,
                    'data_bytes': event.data_bytes,
                    'req_id': event.req_id,
                })
                
                self.stats['total_p2p_transfers'] += 1
                self.stats['total_p2p_bytes'] += event.data_bytes
                self.stats['total_p2p_latency_ns'] += p2p_latency
                self.stats['total_queue_delay_ns'] += queue_delay
            
            elif event.event_type == EventType.PIM_SEND_PARTIAL:
                # Partial sum transfer through switch
                arrival_time, queue_delay = self.switch.route_packet(
                    event, event.timestamp_ns
                )
                
                self.stats['partial_sum_transfers'] += 1
                self.stats['partial_sum_bytes'] += event.data_bytes
                self.stats['partial_sum_latency_ns'] += (arrival_time - event.timestamp_ns)
                
                # Generate REDUCE event at destination
                reduce_event = Event(
                    timestamp_ns=arrival_time,
                    event_type=EventType.PIM_REDUCE_ATTN,
                    src_node=event.src_node,
                    dst_node=event.dst_node,
                    req_id=event.req_id,
                    data_bytes=event.data_bytes,
                )
                heapq.heappush(self.event_queue, reduce_event)
            
            elif event.event_type == EventType.PIM_REDUCE_ATTN:
                self.stats['reduce_operations'] += 1
                self.nodes[event.dst_node].p2p_reduce_attn += 1
            
            processed += 1
        
        print(f"  Processed {processed:,} network events")
        return self.get_results()
    
    def inject_distributed_attention_events(
        self,
        num_decode_steps: int = 100,
        base_time_ns: int = 0,
        step_interval_ns: int = 30_000_000  # 30ms per step
    ):
        """
        Inject PIM_SEND_PARTIAL and barrier events to simulate distributed attention.
        
        In each decode step, each node computes local partial attention,
        then sends partial sums to all other nodes for AllReduce.
        """
        print(f"\n  Injecting distributed attention events...")
        print(f"    Decode steps: {num_decode_steps}")
        print(f"    Nodes: {self.num_nodes}")
        
        barrier_id = 0
        for step in range(num_decode_steps):
            step_time = base_time_ns + step * step_interval_ns
            
            # Each node sends partial sum to every other node
            for src in range(self.num_nodes):
                for dst in range(self.num_nodes):
                    if src == dst:
                        continue
                    
                    event = Event(
                        timestamp_ns=step_time,
                        event_type=EventType.PIM_SEND_PARTIAL,
                        src_node=src,
                        dst_node=dst,
                        data_bytes=self.partial_sum_bytes,
                        payload={'step': step, 'barrier_id': barrier_id},
                    )
                    heapq.heappush(self.event_queue, event)
                    self.nodes[src].p2p_send_partial += 1
            
            barrier_id += 1
        
        total_injected = num_decode_steps * self.num_nodes * (self.num_nodes - 1)
        print(f"    Injected {total_injected:,} partial sum events")
    
    def get_results(self) -> Dict:
        """Compile comprehensive simulation results."""
        results = {
            'config': {
                'topology': self.topology,
                'num_nodes': self.num_nodes,
                'switch_base_latency_ns': self.switch.base_latency_ns,
                'port_bandwidth_gbps': self.switch.port_bandwidth_gbps,
            },
            'switch_stats': self.switch.get_stats(),
            'barrier_stats': self.barrier.get_stats(),
            'global_stats': dict(self.stats),
            'per_node': {},
        }
        
        # Per-node summary
        for nid, node in self.nodes.items():
            results['per_node'][nid] = {
                'role': node.role,
                'local_accesses': node.local_accesses,
                'remote_reads_in': node.remote_reads_in,
                'remote_reads_out': node.remote_reads_out,
                'p2p_send_partial': node.p2p_send_partial,
                'p2p_reduce_attn': node.p2p_reduce_attn,
                'trace_entries': len(node.trace_entries),
            }
        
        # P2P latency distribution
        if self.p2p_transfers:
            latencies = [t['latency_ns'] for t in self.p2p_transfers]
            results['p2p_latency_distribution'] = {
                'mean_ns': float(np.mean(latencies)),
                'median_ns': float(np.median(latencies)),
                'p95_ns': float(np.percentile(latencies, 95)),
                'p99_ns': float(np.percentile(latencies, 99)),
                'max_ns': float(np.max(latencies)),
                'total_transfers': len(latencies),
            }
        
        # Compute aggregate metrics for paper
        total_local = sum(n.local_accesses for n in self.nodes.values())
        total_remote = sum(n.remote_reads_in for n in self.nodes.values())
        total_p2p_bytes = self.stats.get('total_p2p_bytes', 0)
        
        results['paper_metrics'] = {
            'total_local_accesses': total_local,
            'total_remote_accesses': total_remote,
            'remote_access_ratio': total_remote / max(total_local + total_remote, 1),
            'total_p2p_data_gb': total_p2p_bytes / 1e9,
            'avg_switch_queue_delay_ns': self.stats.get('total_queue_delay_ns', 0) / max(self.stats.get('total_p2p_transfers', 1), 1),
            'congestion_rate': self.switch.get_stats().get('congestion_rate', 0),
        }
        
        return results
    
    def export_per_node_traces(self, output_dir: str):
        """Export per-node trace files for Ramulator2."""
        os.makedirs(output_dir, exist_ok=True)
        for nid, node in self.nodes.items():
            trace_path = os.path.join(output_dir, f"node_{nid}.trace")
            with open(trace_path, 'w') as f:
                f.write('\n'.join(node.trace_entries))
                f.write('\n')
            print(f"    Node {nid}: {len(node.trace_entries):,} entries -> {trace_path}")


# ==============================================================================
# Self-Test
# ==============================================================================

def run_self_test():
    """Run basic self-tests for all components."""
    print("=" * 60)
    print("CXL Fabric Simulator - Self Test")
    print("=" * 60)
    
    # Test 1: CXL Switch
    print("\n[1/4] Testing CXL Switch...")
    switch = CXLSwitchNode({'base_latency_ns': 150, 'port_bandwidth_gbps': 64, 'queue_depth': 64})
    switch.add_port(0, 0)
    switch.add_port(1, 1)
    switch.add_port(2, 2)
    switch.add_port(3, 3)
    
    # Send packets
    for i in range(100):
        event = Event(
            timestamp_ns=i * 1000,
            event_type=EventType.P2P_SEND,
            src_node=i % 4,
            dst_node=(i + 1) % 4,
            data_bytes=64,
        )
        arrival, delay = switch.route_packet(event, event.timestamp_ns)
        assert arrival >= event.timestamp_ns, f"Time travel! {arrival} < {event.timestamp_ns}"
    
    stats = switch.get_stats()
    print(f"  Packets: {stats['total_packets']}")
    print(f"  Avg queue delay: {stats['avg_queue_delay_ns']:.1f} ns")
    print(f"  Congestion rate: {stats['congestion_rate']:.2%}")
    print("  ✅ PASS")
    
    # Test 2: P2P Routing
    print("\n[2/4] Testing P2P Routing...")
    for topo in ['star', 'ring', 'fat_tree']:
        router = P2PRoutingLogic(topo, 4, per_hop_ns=50)
        hops_01 = router.get_hops(0, 1)
        latency_01 = router.get_p2p_latency_ns(0, 1)
        desc = router.get_route_description(0, 1)
        print(f"  {topo}: 0->1 = {hops_01} hops, {latency_01} ns ({desc})")
    print("  ✅ PASS")
    
    # Test 3: Sync Barrier
    print("\n[3/4] Testing Sync Barrier...")
    barrier = SynchronizationBarrier(4)
    # Nodes arrive at different times
    assert barrier.arrive(0, 1000, 0) is None
    assert barrier.arrive(1, 2000, 0) is None
    assert barrier.arrive(2, 1500, 0) is None
    release = barrier.arrive(3, 3000, 0)
    assert release == 3000, f"Expected release at 3000, got {release}"
    stats = barrier.get_stats()
    print(f"  Barriers completed: {stats['total_barriers']}")
    print(f"  Total stall: {stats['total_stall_ns']} ns")
    print("  ✅ PASS")
    
    # Test 4: Contention test (burst of packets to same port)
    print("\n[4/4] Testing contention under burst...")
    switch2 = CXLSwitchNode({'base_latency_ns': 150, 'port_bandwidth_gbps': 64, 'queue_depth': 64})
    switch2.add_port(0, 0)
    switch2.add_port(1, 1)
    
    # 10 packets all targeting port 1 at same time
    for i in range(10):
        event = Event(
            timestamp_ns=0,
            event_type=EventType.P2P_SEND,
            src_node=0,
            dst_node=1,
            data_bytes=4096,  # Larger packets
        )
        arrival, delay = switch2.route_packet(event, 0)
    
    stats2 = switch2.get_stats()
    print(f"  10 burst packets -> port 1:")
    print(f"  Avg queue delay: {stats2['avg_queue_delay_ns']:.1f} ns")
    print(f"  Congestion events: {stats2['congestion_events']}")
    assert stats2['congestion_events'] > 0, "Expected congestion under burst!"
    print("  ✅ PASS")
    
    print("\n" + "=" * 60)
    print("All tests passed! ✅")
    print("=" * 60)


# ==============================================================================
# Main
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="CXL 3.0 Fabric Network Simulator for DisaggKV"
    )
    parser.add_argument("--config", type=str, default="ramulator2/cxl_disagg_config.yaml",
                        help="CXL fabric configuration YAML")
    parser.add_argument("--trace", type=str, help="Multi-tenant trace file (from Phase 5.1)")
    parser.add_argument("--num_nodes", type=int, default=4)
    parser.add_argument("--decode_steps", type=int, default=100,
                        help="Number of distributed attention steps to simulate")
    parser.add_argument("--output", type=str, default="results/cxl_fabric_results.json",
                        help="Output results JSON")
    parser.add_argument("--export_traces", type=str, default="",
                        help="Directory to export per-node traces")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    
    args = parser.parse_args()
    
    if args.test:
        run_self_test()
        return
    
    # --- Banner ---
    print("=" * 70)
    print(" DisaggKV CXL 3.0 Fabric Simulator")
    print(" Phase 5.2 - LKC-CXL-PIM Project")
    print("=" * 70)
    
    sim = CXLFabricSimulator(args.config)
    
    print(f"  Topology:    {sim.topology}")
    print(f"  Nodes:       {sim.num_nodes}")
    print(f"  Switch:      {sim.switch.base_latency_ns}ns base, "
          f"{sim.switch.port_bandwidth_gbps}GB/s per port")
    
    # Load and split trace
    if args.trace:
        print(f"\n[1/3] Loading and splitting trace...")
        sim.load_and_split_trace(args.trace)
    
    # Inject distributed attention events
    print(f"\n[2/3] Simulating distributed attention...")
    sim.inject_distributed_attention_events(
        num_decode_steps=args.decode_steps
    )
    
    # Run network simulation
    print(f"\n[3/3] Running network simulation...")
    results = sim.simulate_network()
    
    # Export per-node traces if requested
    if args.export_traces:
        print(f"\n  Exporting per-node traces to {args.export_traces}/")
        sim.export_per_node_traces(args.export_traces)
    
    # Save results
    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    # Print summary
    print("\n" + "=" * 70)
    print(" CXL Fabric Simulation Results")
    print("=" * 70)
    
    pm = results.get('paper_metrics', {})
    print(f"  Total local accesses:  {pm.get('total_local_accesses', 0):,}")
    print(f"  Total remote accesses: {pm.get('total_remote_accesses', 0):,}")
    print(f"  Remote access ratio:   {pm.get('remote_access_ratio', 0):.2%}")
    print(f"  Total P2P data:        {pm.get('total_p2p_data_gb', 0):.4f} GB")
    print(f"  Avg queue delay:       {pm.get('avg_switch_queue_delay_ns', 0):.1f} ns")
    print(f"  Congestion rate:       {pm.get('congestion_rate', 0):.2%}")
    
    sw = results.get('switch_stats', {})
    print(f"\n  Switch packets:        {sw.get('total_packets', 0):,}")
    
    if 'p2p_latency_distribution' in results:
        p2p = results['p2p_latency_distribution']
        print(f"\n  P2P Latency Distribution:")
        print(f"    Mean:   {p2p['mean_ns']:.1f} ns")
        print(f"    P95:    {p2p['p95_ns']:.1f} ns")
        print(f"    P99:    {p2p['p99_ns']:.1f} ns")
        print(f"    Max:    {p2p['max_ns']:.1f} ns")
    
    gs = results.get('global_stats', {})
    if gs.get('partial_sum_transfers', 0) > 0:
        print(f"\n  Distributed Attention:")
        print(f"    Partial sum transfers: {gs['partial_sum_transfers']:,}")
        avg_ps_lat = gs['partial_sum_latency_ns'] / max(gs['partial_sum_transfers'], 1)
        print(f"    Avg partial sum latency: {avg_ps_lat:.1f} ns")
        print(f"    Reduce operations: {gs.get('reduce_operations', 0):,}")
    
    print(f"\n  Results saved to: {args.output}")
    print("=" * 70)


if __name__ == "__main__":
    main()
