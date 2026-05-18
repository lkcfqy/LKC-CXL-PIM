#!/usr/bin/env python3
"""
Generate derived thesis metrics from checked-in simulator outputs.

This script deliberately separates measured artifact inputs from analytical
model assumptions. It does not invent fallback values when inputs are missing:
missing source files should fail loudly so the evidence chain stays auditable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

SIM_RESULTS = ROOT / "simulation_results.csv"
CXL_RESULTS = ROOT / "results/cxl_4node_results.json"
FAULT_RESULTS = ROOT / "results/fault_recovery_results.json"
SCALABILITY_RESULTS = ROOT / "results/scalability_summary.json"
DEFAULT_OUTPUT = ROOT / "paper_assets/data/paper_metrics.json"

TOKEN_COUNT_50REQ_TRACE = 259_728
BYTES_PER_ACCESS = 64

# Analytical model assumptions used only for the system-level queueing curves.
KV_IO_FRACTION_128K = 0.78
SWITCH_QUEUE_NORMALIZER_NS = 2_000.0
HOST_BASE_SERVICE_RATE_RPS = 1_000.0
HOST_BASE_LATENCY_MS = 12.0
OURS_BASE_LATENCY_MS = 6.0
HOST_QUEUE_COEFF_MS = 500.0
OURS_QUEUE_COEFF_MS = 200.0
SATURATION_MARGIN_RPS = 50.0
HOST_OVERLOAD_SLOPE_MS_PER_RPS = 5.0
OURS_OVERLOAD_SLOPE_MS_PER_RPS = 0.5

HOST_LOCAL_METADATA_FRACTION = 0.05
HOST_CXL_PROTOCOL_OVERHEAD = 1.15
BASE_THROUGHPUT_PER_NODE_RPS = 260.0
SINGLE_NODE_REFERENCE_EFFICIENCY = 0.95
HOST_SCALING_KNEE_RPS = 1_000.0
HOST_POST_KNEE_EFFICIENCY = 0.20
HOST_THROUGHPUT_CAP_RPS = 1_600.0

HOST_RDMA_RECOVERY_MS = 2_800.0
CHECKPOINT_RESTART_MS = 15_000.0


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required source file is missing: {path}")
    with path.open("r") as f:
        return json.load(f)


def load_sim_results(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required source file is missing: {path}")
    df = pd.read_csv(path)
    required = {"Trace", "Scenario", "ReadLatency", "WriteLatency", "RowMisses"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{path} is missing columns: {', '.join(missing)}")
    return df


def nested_get(source: dict[str, Any], path: tuple[str, ...]) -> Any:
    cur: Any = source
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            dotted = ".".join(path)
            raise KeyError(f"Required key is missing from source JSON: {dotted}")
        cur = cur[key]
    return cur


def ramulator_read_speedup(sim_df: pd.DataFrame, trace_fragment: str = "128k") -> float:
    trace_match = sim_df["Trace"].str.contains(trace_fragment, case=False, na=False)
    baseline = sim_df[trace_match & (sim_df["Scenario"] == "Baseline")]
    pim = sim_df[trace_match & (sim_df["Scenario"] == "PIM-KV")]
    if baseline.empty or pim.empty:
        raise ValueError(f"Could not find Baseline and PIM-KV rows for {trace_fragment}")
    baseline_read = float(baseline.iloc[0]["ReadLatency"])
    pim_read = float(pim.iloc[0]["ReadLatency"])
    if pim_read <= 0:
        raise ValueError("PIM-KV read latency must be positive")
    return baseline_read / pim_read


def latency_curve(
    throughputs: np.ndarray,
    service_rate_rps: float,
    base_latency_ms: float,
    queue_coeff_ms: float,
    overload_slope_ms_per_rps: float,
) -> list[float]:
    values: list[float] = []
    saturation_start = service_rate_rps - SATURATION_MARGIN_RPS
    for throughput in throughputs:
        if throughput < saturation_start:
            latency = base_latency_ms + queue_coeff_ms / (service_rate_rps - throughput)
        else:
            latency = (
                base_latency_ms
                + queue_coeff_ms / SATURATION_MARGIN_RPS
                + (throughput - saturation_start) * overload_slope_ms_per_rps
            )
        values.append(float(min(latency, 500.0)))
    return values


def generate_throughput_latency(
    sim_df: pd.DataFrame,
    cxl_results: dict[str, Any],
) -> dict[str, Any]:
    throughputs = np.linspace(100, 4000, 25)
    memory_speedup = ramulator_read_speedup(sim_df)
    effective_speedup = 1.0 / (
        (1.0 - KV_IO_FRACTION_128K) + (KV_IO_FRACTION_128K / memory_speedup)
    )

    queue_delay_ns = float(nested_get(cxl_results, ("switch_stats", "avg_queue_delay_ns")))
    congestion_penalty = 1.0 + (queue_delay_ns / SWITCH_QUEUE_NORMALIZER_NS)
    host_service_rate = HOST_BASE_SERVICE_RATE_RPS / congestion_penalty
    ours_service_rate = host_service_rate * effective_speedup

    return {
        "x_throughput": throughputs.tolist(),
        "y_lat_host": latency_curve(
            throughputs,
            host_service_rate,
            HOST_BASE_LATENCY_MS * congestion_penalty,
            HOST_QUEUE_COEFF_MS,
            HOST_OVERLOAD_SLOPE_MS_PER_RPS,
        ),
        "y_lat_ours": latency_curve(
            throughputs,
            ours_service_rate,
            OURS_BASE_LATENCY_MS,
            OURS_QUEUE_COEFF_MS,
            OURS_OVERLOAD_SLOPE_MS_PER_RPS,
        ),
        "sla_ms": 50.0,
        "model": {
            "type": "calibrated_queueing_curve",
            "memory_speedup_from_ramulator_128k": memory_speedup,
            "kv_io_fraction_128k": KV_IO_FRACTION_128K,
            "effective_speedup": effective_speedup,
            "avg_switch_queue_delay_ns": queue_delay_ns,
            "congestion_penalty": congestion_penalty,
            "host_service_rate_rps": host_service_rate,
            "ours_service_rate_rps": ours_service_rate,
        },
    }


def generate_traffic_breakdown(cxl_results: dict[str, Any]) -> dict[str, Any]:
    categories = ["Local HBM Access", "CXL P2P Data", "CXL-to-Host Traffic"]
    token_scale = 1_000_000 / TOKEN_COUNT_50REQ_TRACE

    metrics = nested_get(cxl_results, ("paper_metrics",))
    local_count = float(nested_get(metrics, ("total_local_accesses",)))
    remote_count = float(nested_get(metrics, ("total_remote_accesses",)))
    p2p_bytes = float(nested_get(cxl_results, ("global_stats", "total_p2p_bytes")))

    local_gb = (local_count * BYTES_PER_ACCESS) / (1024**3)
    remote_gb = (remote_count * BYTES_PER_ACCESS) / (1024**3)
    p2p_gb = p2p_bytes / (1024**3)

    disaggkv = [
        local_gb * token_scale,
        p2p_gb * token_scale,
        remote_gb * token_scale,
    ]
    host_agg = [
        local_gb * HOST_LOCAL_METADATA_FRACTION * token_scale,
        0.0,
        (
            local_gb * (1.0 - HOST_LOCAL_METADATA_FRACTION)
            + remote_gb
        )
        * HOST_CXL_PROTOCOL_OVERHEAD
        * token_scale,
    ]

    return {
        "categories": categories,
        "host_agg": host_agg,
        "disaggkv": disaggkv,
        "model": {
            "token_scale_source": "50-request multi-tenant trace",
            "tokens_in_source_trace": TOKEN_COUNT_50REQ_TRACE,
            "bytes_per_access": BYTES_PER_ACCESS,
            "host_local_metadata_fraction": HOST_LOCAL_METADATA_FRACTION,
            "host_cxl_protocol_overhead": HOST_CXL_PROTOCOL_OVERHEAD,
        },
    }


def generate_fault_recovery(fault_results: dict[str, Any]) -> dict[str, Any]:
    our_latency = float(nested_get(fault_results, ("recovery_latency_ms", "p95")))
    return {
        "methods": [
            "PIM XOR Parity (Ours)",
            "Host RDMA Backup",
            "Checkpoint Restart",
        ],
        "latencies": [our_latency, HOST_RDMA_RECOVERY_MS, CHECKPOINT_RESTART_MS],
        "model": {
            "ours_source": "results/fault_recovery_results.json recovery_latency_ms.p95",
            "baseline_values": "analytical comparison constants",
        },
    }


def generate_scalability(scal_results: dict[str, Any]) -> dict[str, Any]:
    nodes_x = [1, 2, 4, 8, 16]
    y_ours: list[float] = []
    y_host: list[float] = []
    y_ideal: list[float] = []
    efficiencies: dict[str, float] = {}

    for n in nodes_x:
        if n == 1:
            efficiency = SINGLE_NODE_REFERENCE_EFFICIENCY
        else:
            key = str(n)
            if key not in scal_results:
                raise KeyError(f"Missing scalability efficiency for {n} nodes")
            efficiency = float(scal_results[key])
        efficiencies[str(n)] = efficiency

        y_ours.append(BASE_THROUGHPUT_PER_NODE_RPS * n * (0.8 + 0.2 * efficiency))

        host_value = BASE_THROUGHPUT_PER_NODE_RPS * n
        if host_value > HOST_SCALING_KNEE_RPS:
            host_value = HOST_SCALING_KNEE_RPS + (
                host_value - HOST_SCALING_KNEE_RPS
            ) * HOST_POST_KNEE_EFFICIENCY
        y_host.append(float(min(HOST_THROUGHPUT_CAP_RPS, host_value)))
        y_ideal.append(float(BASE_THROUGHPUT_PER_NODE_RPS * n))

    return {
        "x_nodes": nodes_x,
        "y_host": y_host,
        "y_ours": y_ours,
        "y_ideal": y_ideal,
        "model": {
            "scheduler_efficiencies": efficiencies,
            "single_node_reference_efficiency": SINGLE_NODE_REFERENCE_EFFICIENCY,
            "base_throughput_per_node_rps": BASE_THROUGHPUT_PER_NODE_RPS,
            "host_scaling_knee_rps": HOST_SCALING_KNEE_RPS,
            "host_post_knee_efficiency": HOST_POST_KNEE_EFFICIENCY,
            "host_throughput_cap_rps": HOST_THROUGHPUT_CAP_RPS,
        },
    }


def build_metrics() -> dict[str, Any]:
    sim_df = load_sim_results(SIM_RESULTS)
    cxl_results = load_json(CXL_RESULTS)
    fault_results = load_json(FAULT_RESULTS)
    scal_results = load_json(SCALABILITY_RESULTS)

    return {
        "_provenance": {
            "generated_by": "scripts/generate_paper_data.py",
            "sources": [
                str(SIM_RESULTS.relative_to(ROOT)),
                str(CXL_RESULTS.relative_to(ROOT)),
                str(FAULT_RESULTS.relative_to(ROOT)),
                str(SCALABILITY_RESULTS.relative_to(ROOT)),
            ],
            "notes": (
                "Ramulator and CXL simulator outputs provide measured counters; "
                "throughput-latency and baseline recovery comparisons use the "
                "explicit analytical assumptions recorded in each section."
            ),
        },
        "throughput_latency": generate_throughput_latency(sim_df, cxl_results),
        "traffic_breakdown": generate_traffic_breakdown(cxl_results),
        "fault_recovery": generate_fault_recovery(fault_results),
        "scalability": generate_scalability(scal_results),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate paper_assets/data/paper_metrics.json from checked-in artifacts."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    data = build_metrics()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    print(f"SUCCESS: {output.relative_to(ROOT)} updated.")


if __name__ == "__main__":
    main()
