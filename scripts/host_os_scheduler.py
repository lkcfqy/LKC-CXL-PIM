#!/usr/bin/env python3
"""
host_os_scheduler.py - Host OS Disaggregated KV Scheduler

The "brain" of the DisaggKV system: decides where KV-Cache token slices are placed
across CXL-PIM memory nodes. Implements the Hypervisor-level global KV page table,
load balancing, and dynamic migration policies.

Key Components:
  1. GlobalKVPageTable: Virtual-to-physical mapping supporting cross-CXL-device addressing.
     Each KV page (fixed-size block of KV-Cache) maps to a (node_id, physical_page_id).
  2. LoadBalancer: Detects hotspot nodes and redirects new page allocations to cold nodes.
     Policies: RoundRobin, LeastLoaded, LocalityAware.
  3. DynamicMigrator: Background defragmentation and cross-card data migration using
     CXL bandwidth. Triggers when fragmentation or imbalance exceeds thresholds.

This module can operate:
  - Standalone: processes a multi-tenant trace and outputs placement decisions
  - Integrated: called by cxl_fabric_simulator.py as the allocation layer

Usage:
  python scripts/host_os_scheduler.py \\
    --config ramulator2/cxl_disagg_config.yaml \\
    --trace traces/multitenant/multi_tenant_50req.trace \\
    --policy least_loaded \\
    --output results/scheduler_results.json

Author: LKC-CXL-PIM Project (Phase 5.3)
"""

import os
import sys
import json
import argparse
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict
from enum import Enum, auto
import time as time_mod

import yaml
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ==============================================================================
# Constants
# ==============================================================================

KV_PAGE_SIZE_BYTES = 4096           # 4KB per KV page (one cache line group)
KV_BLOCK_TOKENS = 16                # Tokens per KV block (vLLM-style paging)
BYTES_PER_TOKEN_KV = 256            # Bytes per token per KV head (K+V combined)
                                    # = 2 (K+V) × head_dim(128) × dtype(1 byte INT8)


# ==============================================================================
# Data Types
# ==============================================================================

class AllocationPolicy(Enum):
    ROUND_ROBIN = auto()
    LEAST_LOADED = auto()
    LOCALITY_AWARE = auto()


class PageState(Enum):
    FREE = auto()
    ALLOCATED = auto()
    MIGRATING = auto()
    SHARED = auto()         # Shared prefix page (read-only, multi-ref)


@dataclass
class KVPage:
    """A single KV-Cache page in the global page table."""
    virtual_page_id: int
    node_id: int                    # Physical CXL node
    physical_page_id: int           # Physical page within node
    req_id: int                     # Owning request (-1 for shared)
    state: PageState = PageState.ALLOCATED
    access_count: int = 0           # Read access counter (for hotspot detection)
    last_access_ns: int = 0         # Last access timestamp
    is_shared_prefix: bool = False  # True if part of shared system prompt
    ref_count: int = 1              # Number of requests referencing this page

    @property
    def is_hot(self) -> bool:
        """Heuristic: page is 'hot' if accessed more than 100 times."""
        return self.access_count > 100


@dataclass
class NodeMemoryState:
    """Memory state of a single CXL-PIM node."""
    node_id: int
    capacity_pages: int             # Total page capacity
    allocated_pages: int = 0        # Currently allocated pages
    free_pages: int = 0             # Currently free pages
    access_count: int = 0           # Total accesses to this node
    migration_in: int = 0           # Pages migrated into this node
    migration_out: int = 0          # Pages migrated out
    fragmentation: float = 0.0     # Fragmentation ratio [0, 1]

    # Per-request page lists
    request_pages: Dict[int, List[int]] = field(default_factory=lambda: defaultdict(list))

    @property
    def utilization(self) -> float:
        return self.allocated_pages / max(self.capacity_pages, 1)

    @property
    def is_overloaded(self) -> bool:
        return self.utilization > 0.85

    def __post_init__(self):
        self.free_pages = self.capacity_pages - self.allocated_pages


@dataclass
class MigrationEvent:
    """Records a page migration between nodes."""
    page_id: int
    src_node: int
    dst_node: int
    timestamp_ns: int
    data_bytes: int
    latency_ns: int
    reason: str  # "load_balance" | "defragment" | "locality"


# ==============================================================================
# Global KV Page Table
# ==============================================================================

class GlobalKVPageTable:
    """
    Hypervisor-level virtual-to-physical KV-Cache page mapping.

    Supports:
    - Cross-CXL device addressing (virtual page -> (node, physical_page))
    - Shared prefix pages (multi-reference, read-only)
    - Page access tracking for hotspot detection
    - Reverse index: node_id -> [pages]
    """

    def __init__(self, num_nodes: int, pages_per_node: int):
        self.num_nodes = num_nodes
        self.pages_per_node = pages_per_node

        # Virtual -> Physical mapping
        self.page_table: Dict[int, KVPage] = {}

        # Reverse index: node -> set of virtual page IDs
        self.node_pages: Dict[int, Set[int]] = {
            i: set() for i in range(num_nodes)
        }

        # Per-node physical page allocation bitmaps
        self._next_physical: Dict[int, int] = {i: 0 for i in range(num_nodes)}
        self._free_lists: Dict[int, List[int]] = {i: [] for i in range(num_nodes)}

        # Global counters
        self._next_virtual_id = 0

        # Statistics
        self.total_allocations = 0
        self.total_frees = 0
        self.total_lookups = 0
        self.shared_page_hits = 0

    def allocate_page(
        self,
        node_id: int,
        req_id: int,
        is_shared: bool = False,
        timestamp_ns: int = 0
    ) -> Optional[KVPage]:
        """Allocate a new KV page on the specified node."""
        # Get physical page
        phys_id = self._alloc_physical(node_id)
        if phys_id is None:
            return None  # Node is full

        virt_id = self._next_virtual_id
        self._next_virtual_id += 1

        page = KVPage(
            virtual_page_id=virt_id,
            node_id=node_id,
            physical_page_id=phys_id,
            req_id=req_id,
            state=PageState.SHARED if is_shared else PageState.ALLOCATED,
            is_shared_prefix=is_shared,
            last_access_ns=timestamp_ns,
        )

        self.page_table[virt_id] = page
        self.node_pages[node_id].add(virt_id)
        self.total_allocations += 1

        return page

    def free_page(self, virtual_page_id: int) -> bool:
        """Free a KV page. For shared pages, decrement ref_count first."""
        page = self.page_table.get(virtual_page_id)
        if page is None:
            return False

        if page.is_shared_prefix:
            page.ref_count -= 1
            if page.ref_count > 0:
                return True  # Still referenced

        # Actually free the page
        self._free_physical(page.node_id, page.physical_page_id)
        self.node_pages[page.node_id].discard(virtual_page_id)
        del self.page_table[virtual_page_id]
        self.total_frees += 1

        return True

    def lookup(self, virtual_page_id: int) -> Optional[Tuple[int, int]]:
        """Look up physical location: returns (node_id, physical_page_id)."""
        self.total_lookups += 1
        page = self.page_table.get(virtual_page_id)
        if page is None:
            return None
        return (page.node_id, page.physical_page_id)

    def record_access(self, virtual_page_id: int, timestamp_ns: int = 0):
        """Record an access to a page (for hotspot tracking)."""
        page = self.page_table.get(virtual_page_id)
        if page:
            page.access_count += 1
            page.last_access_ns = timestamp_ns
            if page.is_shared_prefix:
                self.shared_page_hits += 1

    def migrate_page(self, virtual_page_id: int, dst_node: int) -> bool:
        """Migrate a page from its current node to dst_node."""
        page = self.page_table.get(virtual_page_id)
        if page is None or page.node_id == dst_node:
            return False

        # Allocate on destination
        new_phys = self._alloc_physical(dst_node)
        if new_phys is None:
            return False

        src_node = page.node_id

        # Free on source
        self._free_physical(src_node, page.physical_page_id)
        self.node_pages[src_node].discard(virtual_page_id)

        # Update mapping
        page.node_id = dst_node
        page.physical_page_id = new_phys
        page.state = PageState.ALLOCATED
        self.node_pages[dst_node].add(virtual_page_id)

        return True

    def get_node_stats(self) -> Dict[int, Dict]:
        """Get per-node page table statistics."""
        stats = {}
        for nid in range(self.num_nodes):
            pages = [self.page_table[vid] for vid in self.node_pages[nid]
                     if vid in self.page_table]
            total_access = sum(p.access_count for p in pages)
            shared_count = sum(1 for p in pages if p.is_shared_prefix)

            stats[nid] = {
                'allocated_pages': len(pages),
                'total_capacity': self.pages_per_node,
                'utilization': len(pages) / max(self.pages_per_node, 1),
                'total_accesses': total_access,
                'shared_pages': shared_count,
                'hot_pages': sum(1 for p in pages if p.is_hot),
            }
        return stats

    # --- Internal helpers ---
    def _alloc_physical(self, node_id: int) -> Optional[int]:
        if self._free_lists[node_id]:
            return self._free_lists[node_id].pop()
        if self._next_physical[node_id] < self.pages_per_node:
            phys_id = self._next_physical[node_id]
            self._next_physical[node_id] += 1
            return phys_id
        return None  # Node full

    def _free_physical(self, node_id: int, phys_id: int):
        self._free_lists[node_id].append(phys_id)


# ==============================================================================
# Load Balancer
# ==============================================================================

class LoadBalancer:
    """
    Distributes new KV-Cache page allocations across CXL-PIM nodes.

    Policies:
    - RoundRobin: Cycle through nodes (simple baseline)
    - LeastLoaded: Pick the node with lowest utilization
    - LocalityAware: Prefer the node that already holds most pages for the
      same request (minimize cross-node accesses), but redirect to cold
      nodes if the preferred node is overloaded.
    """

    def __init__(
        self,
        num_nodes: int,
        policy: AllocationPolicy = AllocationPolicy.LEAST_LOADED,
        overload_threshold: float = 0.85,
        shared_node_id: int = 0,
    ):
        self.num_nodes = num_nodes
        self.policy = policy
        self.overload_threshold = overload_threshold
        self.shared_node_id = shared_node_id

        # RoundRobin state
        self._rr_counter = 0

        # Per-node utilization cache (updated by scheduler)
        self._node_utilization: Dict[int, float] = {i: 0.0 for i in range(num_nodes)}
        self._node_access_counts: Dict[int, int] = {i: 0 for i in range(num_nodes)}

        # Per-request locality tracker: req_id -> {node_id: page_count}
        self._request_locality: Dict[int, Dict[int, int]] = defaultdict(lambda: defaultdict(int))

        # Statistics
        self.allocation_decisions: Dict[str, int] = defaultdict(int)

    def select_node(
        self,
        req_id: int,
        is_shared: bool = False,
        page_table: Optional[GlobalKVPageTable] = None,
    ) -> int:
        """Select the best node for a new page allocation."""
        if is_shared:
            self.allocation_decisions['shared'] += 1
            return self.shared_node_id

        if self.policy == AllocationPolicy.ROUND_ROBIN:
            return self._round_robin(req_id)
        elif self.policy == AllocationPolicy.LEAST_LOADED:
            return self._least_loaded(req_id)
        elif self.policy == AllocationPolicy.LOCALITY_AWARE:
            return self._locality_aware(req_id, page_table)
        else:
            return self._round_robin(req_id)

    def update_utilization(self, node_id: int, utilization: float, access_count: int = 0):
        """Update cached utilization for a node."""
        self._node_utilization[node_id] = utilization
        self._node_access_counts[node_id] = access_count

    def record_allocation(self, req_id: int, node_id: int):
        """Record that a page for req_id was allocated on node_id."""
        self._request_locality[req_id][node_id] += 1

    def _round_robin(self, req_id: int) -> int:
        # Skip shared node to keep it reserved
        candidates = [i for i in range(self.num_nodes) if i != self.shared_node_id]
        node = candidates[self._rr_counter % len(candidates)]
        self._rr_counter += 1
        self.allocation_decisions['round_robin'] += 1
        return node

    def _least_loaded(self, req_id: int) -> int:
        candidates = [i for i in range(self.num_nodes) if i != self.shared_node_id]
        best = min(candidates, key=lambda n: self._node_utilization.get(n, 0))
        self.allocation_decisions['least_loaded'] += 1
        return best

    def _locality_aware(self, req_id: int, page_table: Optional[GlobalKVPageTable]) -> int:
        locality = self._request_locality.get(req_id, {})
        candidates = [i for i in range(self.num_nodes) if i != self.shared_node_id]

        if locality:
            # Prefer node with most pages for this request
            preferred = max(locality.items(), key=lambda x: x[1])[0]
            if (self._node_utilization.get(preferred, 0) < self.overload_threshold
                    and preferred in candidates):
                self.allocation_decisions['locality_hit'] += 1
                return preferred

        # Fallback to least loaded
        best = min(candidates, key=lambda n: self._node_utilization.get(n, 0))
        self.allocation_decisions['locality_fallback'] += 1
        return best


# ==============================================================================
# Dynamic Migrator
# ==============================================================================

class DynamicMigrator:
    """
    Background KV-Cache page migration engine.

    Triggers migration when:
    1. Load imbalance: a node's utilization exceeds threshold while others are low
    2. Fragmentation: free pages are scattered, causing poor row-buffer locality
    3. Locality optimization: move pages closer to the requesting node

    Migration uses CXL bandwidth (modeled with latency).
    """

    def __init__(
        self,
        page_table: GlobalKVPageTable,
        cxl_bandwidth_gbps: float = 64.0,
        imbalance_threshold: float = 0.2,
        migration_batch_size: int = 64,
    ):
        self.page_table = page_table
        self.cxl_bandwidth_gbps = cxl_bandwidth_gbps
        self.imbalance_threshold = imbalance_threshold
        self.migration_batch_size = migration_batch_size

        # Migration log
        self.migrations: List[MigrationEvent] = []
        self.total_migrated_pages = 0
        self.total_migrated_bytes = 0
        self.total_migration_latency_ns = 0

    def check_and_migrate(self, timestamp_ns: int = 0) -> int:
        """
        Check all nodes for imbalance and trigger migrations.

        Returns:
            Number of pages migrated.
        """
        node_stats = self.page_table.get_node_stats()
        utils = {nid: s['utilization'] for nid, s in node_stats.items()}

        if not utils:
            return 0

        mean_util = np.mean(list(utils.values()))
        max_util = max(utils.values())
        min_util = min(utils.values())

        # Check if imbalance exceeds threshold
        if (max_util - min_util) < self.imbalance_threshold:
            return 0

        # Find overloaded and underloaded nodes
        overloaded = [nid for nid, u in utils.items() if u > mean_util + self.imbalance_threshold / 2]
        underloaded = [nid for nid, u in utils.items() if u < mean_util - self.imbalance_threshold / 2]

        if not overloaded or not underloaded:
            return 0

        migrated = 0
        for src_node in overloaded:
            if migrated >= self.migration_batch_size:
                break

            # Get pages on this node (non-shared, sorted by access count ascending)
            src_pages = sorted(
                [vid for vid in self.page_table.node_pages[src_node]
                 if vid in self.page_table.page_table
                 and not self.page_table.page_table[vid].is_shared_prefix],
                key=lambda vid: self.page_table.page_table[vid].access_count
            )

            for vid in src_pages:
                if migrated >= self.migration_batch_size:
                    break
                if not underloaded:
                    break

                dst_node = min(underloaded, key=lambda n: utils.get(n, 1.0))

                # Perform migration
                if self.page_table.migrate_page(vid, dst_node):
                    latency_ns = self._compute_migration_latency(KV_PAGE_SIZE_BYTES)

                    self.migrations.append(MigrationEvent(
                        page_id=vid,
                        src_node=src_node,
                        dst_node=dst_node,
                        timestamp_ns=timestamp_ns,
                        data_bytes=KV_PAGE_SIZE_BYTES,
                        latency_ns=latency_ns,
                        reason="load_balance",
                    ))

                    migrated += 1
                    self.total_migrated_pages += 1
                    self.total_migrated_bytes += KV_PAGE_SIZE_BYTES
                    self.total_migration_latency_ns += latency_ns

                    # Update utilization estimate
                    utils[src_node] -= 1.0 / self.page_table.pages_per_node
                    utils[dst_node] += 1.0 / self.page_table.pages_per_node

        return migrated

    def defragment(self, node_id: int, timestamp_ns: int = 0) -> int:
        """
        Defragment free pages on a single node by compacting allocated pages.
        """
        pages = sorted(
            [vid for vid in self.page_table.node_pages[node_id]
             if vid in self.page_table.page_table],
            key=lambda vid: self.page_table.page_table[vid].physical_page_id
        )

        compacted = 0
        for i, vid in enumerate(pages):
            page = self.page_table.page_table[vid]
            if page.physical_page_id != i:
                old_phys = page.physical_page_id
                page.physical_page_id = i
                compacted += 1

        return compacted

    def _compute_migration_latency(self, data_bytes: int) -> int:
        """Compute migration latency based on data size and CXL bandwidth."""
        bytes_per_ns = self.cxl_bandwidth_gbps * 1e9 / 8 / 1e9
        return max(1, int(data_bytes / bytes_per_ns))

    def get_stats(self) -> Dict:
        return {
            'total_migrations': self.total_migrated_pages,
            'total_migrated_mb': self.total_migrated_bytes / 1e6,
            'total_migration_latency_ms': self.total_migration_latency_ns / 1e6,
            'avg_migration_latency_ns': (
                self.total_migration_latency_ns / max(self.total_migrated_pages, 1)
            ),
            'migration_log_size': len(self.migrations),
        }


# ==============================================================================
# Host OS KV Scheduler (Top-Level)
# ==============================================================================

class HostOSScheduler:
    """
    Top-level Host OS KV Scheduler.

    Integrates the Global KV Page Table, Load Balancer, and Dynamic Migrator
    into a unified scheduling system driven by incoming requests.
    """

    def __init__(self, config_path: str, policy_str: str = "least_loaded"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        fabric_cfg = self.config['CXLFabric']
        self.num_nodes = fabric_cfg['num_nodes']
        self.topology = fabric_cfg.get('topology', 'star')

        # Determine node capacities (in pages)
        self.node_configs = {}
        shared_node = 0
        for nc in fabric_cfg['nodes']:
            nid = nc['node_id']
            cap_gb = nc.get('capacity_gb', 16.0)
            cap_pages = int(cap_gb * 1024 * 1024 * 1024 / KV_PAGE_SIZE_BYTES)
            self.node_configs[nid] = {
                'capacity_pages': cap_pages,
                'capacity_gb': cap_gb,
                'role': nc.get('role', 'private_kv'),
            }
            if nc.get('role') == 'shared_kv':
                shared_node = nid

        # Parse policy
        policy_map = {
            'round_robin': AllocationPolicy.ROUND_ROBIN,
            'least_loaded': AllocationPolicy.LEAST_LOADED,
            'locality_aware': AllocationPolicy.LOCALITY_AWARE,
        }
        policy = policy_map.get(policy_str, AllocationPolicy.LEAST_LOADED)

        # Shared page table with uniform capacity (simplification)
        pages_per_node = min(nc['capacity_pages'] for nc in self.node_configs.values())
        self.page_table = GlobalKVPageTable(self.num_nodes, pages_per_node)

        # Load balancer
        self.load_balancer = LoadBalancer(
            num_nodes=self.num_nodes,
            policy=policy,
            shared_node_id=shared_node,
        )

        # Dynamic migrator
        port_bw = fabric_cfg.get('switch', {}).get('port_bandwidth_gbps', 64.0)
        self.migrator = DynamicMigrator(
            page_table=self.page_table,
            cxl_bandwidth_gbps=port_bw,
        )

        # Request tracking
        self.active_requests: Dict[int, List[int]] = {}  # req_id -> [page_ids]

        # Timeline for visualization
        self.utilization_timeline: List[Dict] = []
        self.migration_timeline: List[Dict] = []

    def process_trace(
        self,
        trace_path: str,
        migration_interval: int = 100000,
        max_lines: int = 0,
    ) -> Dict:
        """
        Process a multi-tenant trace, allocating KV pages and simulating scheduling.

        For each decoded request:
        1. Allocate KV pages (shared prefix on shared node, private on balanced nodes)
        2. Periodically check load balance and trigger migrations
        3. Track utilization over time
        """
        print(f"  Loading trace: {trace_path}")
        with open(trace_path, 'r') as f:
            lines = f.readlines()

        total_lines = len(lines)
        if max_lines > 0:
            lines = lines[:max_lines]
            total_lines = len(lines)

        print(f"  Processing {total_lines:,} trace entries...")

        # Track unique requests and their token counts
        req_tokens: Dict[int, int] = defaultdict(int)
        req_first_seen: Dict[int, int] = {}

        processed = 0
        writes_processed = 0
        migration_checks = 0

        from tqdm import tqdm

        for line in tqdm(lines, desc="  Scheduling", unit="line", mininterval=1.0):
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if len(parts) < 3:
                continue

            op = parts[0]
            addr = int(parts[1])
            timestamp_ns = int(parts[3]) if len(parts) > 3 else processed * 100
            req_id = int(parts[4]) if len(parts) > 4 else 0

            # Track this request
            if req_id not in req_first_seen:
                req_first_seen[req_id] = timestamp_ns
                self.active_requests[req_id] = []

            # On write (K/V), allocate a new page
            if op in ('K', 'V'):
                writes_processed += 1
                req_tokens[req_id] += 1

                # Decide if we need a new page (every KV_BLOCK_TOKENS tokens)
                if req_tokens[req_id] % KV_BLOCK_TOKENS == 1:
                    # Shared prefix detection:
                    # Only valid for prefix_sharing traces that use 0x40000000+ for V.
                    # For multitenant traces (V at 0x20000000), all K addresses at
                    # 0x10000000 are private, not shared.
                    is_shared_raw = (0x10000000 <= addr < 0x20000000 or
                                    0x40000000 <= addr < 0x50000000)
                    
                    # Detect trace layout by checking if V addresses >= 0x40000000 exist
                    if not hasattr(self, '_has_prefix_sharing_layout'):
                        self._has_prefix_sharing_layout = any(
                            int(l.split()[1]) >= 0x40000000
                            for l in lines[:min(5000, len(lines))]
                            if l.strip() and len(l.split()) >= 2
                        )
                    
                    is_shared = is_shared_raw and self._has_prefix_sharing_layout

                    # Select target node
                    node_id = self.load_balancer.select_node(
                        req_id, is_shared=is_shared, page_table=self.page_table
                    )

                    # Allocate page
                    page = self.page_table.allocate_page(
                        node_id, req_id,
                        is_shared=is_shared,
                        timestamp_ns=timestamp_ns
                    )

                    if page:
                        self.active_requests[req_id].append(page.virtual_page_id)
                        self.load_balancer.record_allocation(req_id, node_id)

            # On read (RK/RV), record access
            elif op in ('RK', 'RV'):
                # Map address to a virtual page (simplified: by request's page list)
                if req_id in self.active_requests and self.active_requests[req_id]:
                    # Access most recent page for this request
                    vid = self.active_requests[req_id][-1]
                    self.page_table.record_access(vid, timestamp_ns)

            processed += 1

            # Periodic migration check
            if processed % migration_interval == 0:
                # Update utilization cache
                node_stats = self.page_table.get_node_stats()
                for nid, s in node_stats.items():
                    self.load_balancer.update_utilization(
                        nid, s['utilization'], s['total_accesses']
                    )

                # Check for migration
                migrated = self.migrator.check_and_migrate(timestamp_ns)
                migration_checks += 1

                # Record timeline snapshot
                self.utilization_timeline.append({
                    'time_ns': timestamp_ns,
                    'line': processed,
                    'utilizations': {
                        nid: s['utilization']
                        for nid, s in node_stats.items()
                    },
                    'migrated': migrated,
                })

        # Final stats
        return self._compile_results(
            processed, writes_processed, migration_checks, req_tokens
        )

    def _compile_results(
        self,
        total_processed: int,
        writes_processed: int,
        migration_checks: int,
        req_tokens: Dict[int, int],
    ) -> Dict:
        """Compile comprehensive scheduling results."""
        node_stats = self.page_table.get_node_stats()
        utils = {nid: s['utilization'] for nid, s in node_stats.items()}
        util_values = list(utils.values())

        results = {
            'config': {
                'num_nodes': self.num_nodes,
                'policy': self.load_balancer.policy.name,
                'topology': self.topology,
            },
            'trace_stats': {
                'total_lines': total_processed,
                'write_operations': writes_processed,
                'unique_requests': len(req_tokens),
                'total_tokens_allocated': sum(req_tokens.values()),
            },
            'page_table': {
                'total_allocations': self.page_table.total_allocations,
                'total_frees': self.page_table.total_frees,
                'total_lookups': self.page_table.total_lookups,
                'shared_page_hits': self.page_table.shared_page_hits,
                'active_pages': len(self.page_table.page_table),
            },
            'per_node': {},
            'load_balance': {
                'utilization_mean': float(np.mean(util_values)) if util_values else 0,
                'utilization_std': float(np.std(util_values)) if util_values else 0,
                'utilization_max': float(max(util_values)) if util_values else 0,
                'utilization_min': float(min(util_values)) if util_values else 0,
                'imbalance_ratio': (
                    float((max(util_values) - min(util_values)) / max(np.mean(util_values), 1e-9))
                    if util_values else 0
                ),
                'allocation_decisions': dict(self.load_balancer.allocation_decisions),
            },
            'migration': self.migrator.get_stats(),
            'paper_metrics': {},
        }

        for nid, stats in node_stats.items():
            results['per_node'][nid] = {
                'role': self.node_configs.get(nid, {}).get('role', 'unknown'),
                **stats,
            }

        # Paper metrics
        # Paper metrics: calculate efficiency only for private_kv nodes to avoid
        # penalizing specialized or shared nodes that may be intentionally idle.
        private_utils = [
            ns['utilization'] for nid, ns in results['per_node'].items()
            if ns['role'] == 'private_kv'
        ]
        
        results['paper_metrics'] = {
            'utilization_std': float(np.std(util_values)) if util_values else 0,
            'peak_utilization': float(max(util_values)) if util_values else 0,
            'total_migrations': self.migrator.total_migrated_pages,
            'migration_overhead_ms': self.migrator.total_migration_latency_ns / 1e6,
            'scheduling_efficiency': (
                1.0 - float(np.std(private_utils)) / max(float(np.mean(private_utils)), 1e-9)
                if private_utils else 1.0
            ),
        }

        return results

    def plot_utilization_timeline(self, output: str):
        """Generate node utilization over time plot."""
        if not self.utilization_timeline:
            print("  No timeline data to plot")
            return

        fig, axes = plt.subplots(2, 1, figsize=(14, 10))

        # Extract timeline data
        times = [t['line'] for t in self.utilization_timeline]
        node_ids = sorted(self.utilization_timeline[0]['utilizations'].keys())

        colors = ['#E74C3C', '#3498DB', '#2ECC71', '#F39C12', '#9B59B6', '#1ABC9C']
        roles = {nid: self.node_configs.get(nid, {}).get('role', '')
                 for nid in node_ids}

        # Plot 1: Utilization per node
        for i, nid in enumerate(node_ids):
            utils = [t['utilizations'].get(nid, 0) for t in self.utilization_timeline]
            label = f"Node {nid} ({roles[nid]})"
            axes[0].plot(times, utils, color=colors[i % len(colors)],
                         linewidth=1.5, label=label, alpha=0.85)

        axes[0].set_xlabel('Trace Lines Processed', fontsize=12)
        axes[0].set_ylabel('Utilization', fontsize=12)
        axes[0].set_title('Per-Node Memory Utilization Over Time',
                          fontsize=13, fontweight='bold')
        axes[0].legend(fontsize=10, loc='upper left')
        axes[0].axhline(0.85, color='#E74C3C', linestyle=':', alpha=0.5,
                        label='Overload Threshold')
        axes[0].set_ylim(-0.01, 1.05)
        axes[0].grid(True, alpha=0.3)

        # Plot 2: Imbalance (max - min utilization) over time
        imbalances = []
        for t in self.utilization_timeline:
            vals = list(t['utilizations'].values())
            imbalances.append(max(vals) - min(vals) if vals else 0)

        axes[1].fill_between(times, imbalances, color='#E74C3C', alpha=0.3)
        axes[1].plot(times, imbalances, color='#E74C3C', linewidth=1.5)
        axes[1].set_xlabel('Trace Lines Processed', fontsize=12)
        axes[1].set_ylabel('Utilization Imbalance (max - min)', fontsize=12)
        axes[1].set_title('Load Imbalance Over Time', fontsize=13, fontweight='bold')
        axes[1].grid(True, alpha=0.3)

        # Add migration markers
        migration_times = [t['line'] for t in self.utilization_timeline if t.get('migrated', 0) > 0]
        if migration_times:
            for mt in migration_times:
                axes[1].axvline(mt, color='#3498DB', alpha=0.3, linewidth=0.5)

        plt.tight_layout()
        os.makedirs(os.path.dirname(output) if os.path.dirname(output) else ".", exist_ok=True)
        plt.savefig(output, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Saved plot: {output}")


# ==============================================================================
# Self-Test
# ==============================================================================

def run_self_test():
    """Run basic self-tests for all scheduler components."""
    print("=" * 60)
    print("Host OS KV Scheduler - Self Test")
    print("=" * 60)

    # Test 1: Page Table
    print("\n[1/4] Testing Global KV Page Table...")
    pt = GlobalKVPageTable(num_nodes=4, pages_per_node=1000)

    pages = []
    for i in range(100):
        p = pt.allocate_page(node_id=i % 4, req_id=i // 10)
        assert p is not None, f"Failed to allocate page {i}"
        pages.append(p)

    assert len(pt.page_table) == 100
    assert pt.total_allocations == 100

    # Lookup
    loc = pt.lookup(pages[0].virtual_page_id)
    assert loc is not None
    assert loc[0] == 0  # First page on node 0

    # Access tracking
    pt.record_access(pages[0].virtual_page_id)
    assert pt.page_table[pages[0].virtual_page_id].access_count == 1

    # Migration
    assert pt.migrate_page(pages[0].virtual_page_id, dst_node=3)
    loc = pt.lookup(pages[0].virtual_page_id)
    assert loc[0] == 3, f"Expected node 3, got {loc[0]}"

    # Free
    assert pt.free_page(pages[1].virtual_page_id)
    assert len(pt.page_table) == 99

    print(f"  Allocations: {pt.total_allocations}")
    print(f"  Active pages: {len(pt.page_table)}")
    print("  ✅ PASS")

    # Test 2: Load Balancer
    print("\n[2/4] Testing Load Balancer...")
    lb = LoadBalancer(num_nodes=4, policy=AllocationPolicy.LEAST_LOADED, shared_node_id=0)

    # Update utilization: node 1 is most loaded
    lb.update_utilization(0, 0.3)
    lb.update_utilization(1, 0.8)
    lb.update_utilization(2, 0.2)
    lb.update_utilization(3, 0.5)

    node = lb.select_node(req_id=0, is_shared=False)
    assert node == 2, f"Expected node 2 (least loaded), got {node}"

    # Shared page goes to shared node
    node = lb.select_node(req_id=0, is_shared=True)
    assert node == 0, f"Expected shared node 0, got {node}"

    print(f"  Decisions: {dict(lb.allocation_decisions)}")
    print("  ✅ PASS")

    # Test 3: Dynamic Migrator
    print("\n[3/4] Testing Dynamic Migrator...")
    pt2 = GlobalKVPageTable(num_nodes=4, pages_per_node=100)

    # Overload node 1: allocate 90 pages
    for i in range(90):
        pt2.allocate_page(node_id=1, req_id=i // 10)

    # Light load on others: 10 pages each
    for nid in [0, 2, 3]:
        for i in range(10):
            pt2.allocate_page(node_id=nid, req_id=100 + i)

    migrator = DynamicMigrator(pt2, imbalance_threshold=0.15)
    migrated = migrator.check_and_migrate(timestamp_ns=0)

    print(f"  Pages migrated: {migrated}")
    print(f"  Total migration latency: {migrator.total_migration_latency_ns} ns")

    # Check that imbalance decreased
    stats = pt2.get_node_stats()
    utils = [s['utilization'] for s in stats.values()]
    print(f"  Post-migration utilizations: {[f'{u:.2f}' for u in utils]}")
    assert max(utils) - min(utils) < 0.9 - 0.1, "Migration should reduce imbalance"
    print("  ✅ PASS")

    # Test 4: Locality-Aware Policy
    print("\n[4/4] Testing Locality-Aware Policy...")
    lb2 = LoadBalancer(num_nodes=4, policy=AllocationPolicy.LOCALITY_AWARE, shared_node_id=0)
    lb2.update_utilization(0, 0.3)
    lb2.update_utilization(1, 0.4)
    lb2.update_utilization(2, 0.3)
    lb2.update_utilization(3, 0.3)

    # Record that req 5 already has pages on node 2
    lb2.record_allocation(5, 2)
    lb2.record_allocation(5, 2)
    lb2.record_allocation(5, 2)

    node = lb2.select_node(req_id=5)
    assert node == 2, f"Expected locality: node 2, got {node}"
    print(f"  Locality-aware selected: node {node} (correct)")

    # If node 2 is overloaded, should fallback
    lb2.update_utilization(2, 0.9)  # Overload node 2
    node = lb2.select_node(req_id=5)
    assert node != 2, f"Should fallback from overloaded node 2, got {node}"
    print(f"  Fallback from overloaded: node {node}")
    print(f"  Decisions: {dict(lb2.allocation_decisions)}")
    print("  ✅ PASS")

    print("\n" + "=" * 60)
    print("All tests passed! ✅")
    print("=" * 60)


# ==============================================================================
# Main
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Host OS Disaggregated KV Scheduler"
    )
    parser.add_argument("--config", type=str, default="ramulator2/cxl_disagg_config.yaml")
    parser.add_argument("--trace", type=str, help="Multi-tenant trace (Phase 5.1)")
    parser.add_argument("--policy", type=str, default="least_loaded",
                        choices=["round_robin", "least_loaded", "locality_aware"])
    parser.add_argument("--migration_interval", type=int, default=100000,
                        help="Check migration every N trace lines")
    parser.add_argument("--max_lines", type=int, default=0,
                        help="Max trace lines to process (0 = all)")
    parser.add_argument("--output", type=str, default="results/scheduler_results.json")
    parser.add_argument("--plot", type=str, default="",
                        help="Output path for utilization timeline plot")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    parser.add_argument("--compare_policies", action="store_true",
                        help="Compare all 3 policies on the same trace")

    args = parser.parse_args()

    if args.test:
        run_self_test()
        return

    print("=" * 70)
    print(" DisaggKV Host OS KV Scheduler")
    print(" Phase 5.3 - LKC-CXL-PIM Project")
    print("=" * 70)

    if args.compare_policies and args.trace:
        # Run all 3 policies and compare
        print("\n  Comparing scheduling policies...")
        comparison = {}

        for policy in ["round_robin", "least_loaded", "locality_aware"]:
            print(f"\n{'─' * 60}")
            print(f"  Policy: {policy.upper()}")
            print(f"{'─' * 60}")

            scheduler = HostOSScheduler(args.config, policy_str=policy)
            results = scheduler.process_trace(
                args.trace,
                migration_interval=args.migration_interval,
                max_lines=args.max_lines,
            )
            comparison[policy] = results

            pm = results['paper_metrics']
            lb = results['load_balance']
            print(f"  Util std:        {pm['utilization_std']:.6f}")
            print(f"  Peak util:       {pm['peak_utilization']:.4f}")
            print(f"  Imbalance ratio: {lb['imbalance_ratio']:.4f}")
            print(f"  Migrations:      {pm['total_migrations']}")

            # Plot
            plot_path = args.output.replace('.json', f'_{policy}_timeline.png')
            scheduler.plot_utilization_timeline(plot_path)

        # Save comparison
        output_path = args.output.replace('.json', '_comparison.json')
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(comparison, f, indent=2, default=str)
        print(f"\n  Comparison saved to: {output_path}")

        # Print summary table
        print(f"\n{'=' * 70}")
        print(f" Policy Comparison Summary")
        print(f"{'=' * 70}")
        print(f"  {'Policy':<20} {'Util Std':<12} {'Peak Util':<12} {'Imbalance':<12} {'Migrations':<12}")
        print(f"  {'─'*68}")
        for policy, res in comparison.items():
            pm = res['paper_metrics']
            lb = res['load_balance']
            print(f"  {policy:<20} {pm['utilization_std']:<12.6f} "
                  f"{pm['peak_utilization']:<12.4f} "
                  f"{lb['imbalance_ratio']:<12.4f} "
                  f"{pm['total_migrations']:<12}")
        print(f"{'=' * 70}")
        return

    if not args.trace:
        print("  ERROR: --trace is required (use --test for self-tests)")
        return

    scheduler = HostOSScheduler(args.config, policy_str=args.policy)

    print(f"  Nodes:       {scheduler.num_nodes}")
    print(f"  Policy:      {args.policy}")
    print(f"  Topology:    {scheduler.topology}")

    print(f"\n[1/2] Processing trace...")
    results = scheduler.process_trace(
        args.trace,
        migration_interval=args.migration_interval,
        max_lines=args.max_lines,
    )

    # Save results
    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Plot
    plot_path = args.plot or args.output.replace('.json', '_timeline.png')
    scheduler.plot_utilization_timeline(plot_path)

    # Print summary
    print(f"\n[2/2] Results Summary")
    print("=" * 70)

    ts = results['trace_stats']
    pt = results['page_table']
    lb = results['load_balance']
    pm = results['paper_metrics']
    mg = results['migration']

    print(f"  Trace:             {ts['total_lines']:,} lines, "
          f"{ts['unique_requests']} requests")
    print(f"  KV Pages allocated:{pt['total_allocations']:,}")
    print(f"  Active pages:      {pt['active_pages']:,}")
    print(f"  Shared page hits:  {pt['shared_page_hits']:,}")

    print(f"\n  Load Balance ({args.policy}):")
    print(f"    Util mean:       {lb['utilization_mean']:.6f}")
    print(f"    Util std:        {lb['utilization_std']:.6f}")
    print(f"    Imbalance ratio: {lb['imbalance_ratio']:.4f}")
    print(f"    Decisions:       {lb['allocation_decisions']}")

    print(f"\n  Per-node:")
    for nid, ns in results['per_node'].items():
        print(f"    Node {nid} ({ns['role']}): "
              f"{ns['allocated_pages']:,} pages, "
              f"util={ns['utilization']:.4f}, "
              f"accesses={ns['total_accesses']:,}")

    print(f"\n  Migration:")
    print(f"    Total migrations:  {mg['total_migrations']}")
    print(f"    Migrated data:     {mg['total_migrated_mb']:.2f} MB")
    print(f"    Migration latency: {mg['total_migration_latency_ms']:.4f} ms")

    print(f"\n  📊 Paper Metrics:")
    print(f"     Scheduling efficiency: {pm['scheduling_efficiency']:.4f}")
    print(f"     Peak utilization:      {pm['peak_utilization']:.4f}")
    print(f"     Migration overhead:    {pm['migration_overhead_ms']:.4f} ms")

    print(f"\n  Results: {args.output}")
    print(f"  Plot:    {plot_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
