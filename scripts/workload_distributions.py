#!/usr/bin/env python3
"""
workload_distributions.py - Workload Distribution Models for Multi-Tenant LLM Serving

Provides reusable arrival process and context length distribution models
for generating realistic multi-tenant traces.

Models:
  - Poisson arrival process (exponential inter-arrival times)
  - MMPP (Markov-Modulated Poisson Process) for bursty traffic
  - Log-Normal context length distribution (empirical LLM serving data)
  - Zipf distribution for popularity-based request routing
  - ShareGPT-derived empirical distribution

References:
  - Zheng et al., "Efficiently Programming Large Language Models using SGLang", 2024
  - Kwon et al., "Efficient Memory Management for LLM Serving with PagedAttention", SOSP 2023
  - Agrawal et al., "Taming Throughput-Latency Tradeoff in LLM Inference", OSDI 2024

Author: LKC-CXL-PIM Project (Phase 5.1)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from scipy import stats
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import os


# ==============================================================================
# Arrival Process Models
# ==============================================================================

@dataclass
class ArrivalConfig:
    """Configuration for request arrival models."""
    rate: float = 10.0          # Average arrival rate (requests/second)
    duration_s: float = 10.0    # Total simulation duration in seconds
    seed: int = 42

    # MMPP parameters (for bursty mode)
    rate_high: float = 50.0     # High-load arrival rate
    rate_low: float = 2.0       # Low-load arrival rate
    switch_prob: float = 0.05   # State transition probability per event


def poisson_arrivals(config: ArrivalConfig) -> np.ndarray:
    """
    Generate Poisson process arrival timestamps.
    
    The inter-arrival times follow an exponential distribution with
    mean = 1/rate seconds.
    
    Returns:
        Sorted array of arrival timestamps in nanoseconds (int64).
    """
    rng = np.random.default_rng(config.seed)
    
    # Expected number of events
    expected_n = int(config.rate * config.duration_s * 1.5)  # overshoot
    
    # Exponential inter-arrival times (in seconds)
    intervals = rng.exponential(scale=1.0 / config.rate, size=expected_n)
    timestamps_s = np.cumsum(intervals)
    
    # Trim to duration
    timestamps_s = timestamps_s[timestamps_s <= config.duration_s]
    
    # Convert to nanoseconds (int64)
    timestamps_ns = (timestamps_s * 1e9).astype(np.int64)
    
    return timestamps_ns


def mmpp_arrivals(config: ArrivalConfig) -> np.ndarray:
    """
    Generate Markov-Modulated Poisson Process (MMPP) arrival timestamps.
    
    Models bursty traffic with two states:
    - State 0 (HIGH): high arrival rate (e.g., peak hours)
    - State 1 (LOW):  low arrival rate (e.g., off-peak)
    
    Transitions between states happen with probability `switch_prob` per event.
    
    Returns:
        Sorted array of arrival timestamps in nanoseconds (int64).
    """
    rng = np.random.default_rng(config.seed)
    
    timestamps = []
    current_time = 0.0
    state = 0  # Start in HIGH state
    
    rates = [config.rate_high, config.rate_low]
    
    while current_time < config.duration_s:
        # Sample interval from current state's rate
        interval = rng.exponential(scale=1.0 / rates[state])
        current_time += interval
        
        if current_time >= config.duration_s:
            break
        
        timestamps.append(current_time)
        
        # State transition
        if rng.random() < config.switch_prob:
            state = 1 - state  # Toggle between 0 and 1
    
    timestamps_ns = (np.array(timestamps) * 1e9).astype(np.int64)
    return timestamps_ns


# ==============================================================================
# Context Length Distribution Models
# ==============================================================================

@dataclass
class ContextConfig:
    """Configuration for context length distributions."""
    mean_len: int = 4096        # Mean context length in tokens
    std_factor: float = 0.8     # Std dev = mean * std_factor (for log-normal)
    min_len: int = 128          # Minimum context length
    max_len: int = 131072       # Maximum context length (128K)
    seed: int = 42
    
    # Zipf parameters
    zipf_alpha: float = 1.2     # Zipf exponent (>1)
    
    # Output token configuration
    mean_output_tokens: int = 256
    output_std_factor: float = 0.5


def lognormal_context_lengths(n: int, config: ContextConfig) -> np.ndarray:
    """
    Generate context lengths from a Log-Normal distribution.
    
    Log-Normal is the most commonly observed distribution in real LLM serving
    workloads (see Orca, vLLM, SGLang papers).
    
    Returns:
        Array of integer context lengths.
    """
    rng = np.random.default_rng(config.seed)
    
    # Convert mean/std to log-normal parameters
    mean = config.mean_len
    sigma_sq = np.log(1 + (config.std_factor ** 2))
    mu = np.log(mean) - sigma_sq / 2
    sigma = np.sqrt(sigma_sq)
    
    samples = rng.lognormal(mean=mu, sigma=sigma, size=n)
    
    # Clip to valid range
    samples = np.clip(samples, config.min_len, config.max_len).astype(int)
    
    return samples


def zipf_context_lengths(n: int, config: ContextConfig) -> np.ndarray:
    """
    Generate context lengths from a Zipf distribution.
    
    Models the heavy-tail pattern where most requests are short,
    but a few are extremely long (128K+).
    
    Returns:
        Array of integer context lengths.
    """
    rng = np.random.default_rng(config.seed)
    
    # Zipf gives integers >= 1
    raw = rng.zipf(a=config.zipf_alpha, size=n)
    
    # Scale to desired range
    scale = config.mean_len / np.mean(raw[:1000]) if n >= 1000 else config.mean_len
    samples = (raw * scale).astype(int)
    samples = np.clip(samples, config.min_len, config.max_len)
    
    return samples


def sharegpt_empirical_distribution(n: int, config: ContextConfig) -> np.ndarray:
    """
    Generate context lengths based on ShareGPT conversation statistics.
    
    Uses a mixture of two log-normals to approximate the bimodal distribution
    observed in real ShareGPT data:
    - Mode 1: Short conversations (~500 tokens, 60% of traffic)
    - Mode 2: Long conversations (~8000 tokens, 40% of traffic)
    
    If the `datasets` library is available, attempts to load real data first.
    
    Returns:
        Array of integer context lengths.
    """
    rng = np.random.default_rng(config.seed)
    
    # Try loading real ShareGPT distribution
    try:
        from datasets import load_dataset
        ds = load_dataset("anon8231489123/ShareGPT_Vicuna_unfiltered",
                          split="train", streaming=True)
        
        lengths = []
        for i, item in enumerate(ds):
            if i >= 5000:
                break
            conv = item.get("conversations", [])
            total_len = sum(len(turn.get("value", "").split()) for turn in conv)
            # Rough token estimate: words * 1.3
            lengths.append(int(total_len * 1.3))
        
        if len(lengths) > 100:
            lengths = np.array(lengths)
            lengths = np.clip(lengths, config.min_len, config.max_len)
            # Resample from empirical
            return rng.choice(lengths, size=n, replace=True)
    except Exception:
        pass  # Fall back to synthetic approximation
    
    # Synthetic bimodal approximation based on published statistics
    # Reference: vLLM benchmark data, SGLang evaluation
    mix_weight = 0.6  # 60% short requests
    n_short = int(n * mix_weight)
    n_long = n - n_short
    
    # Short conversations: log-normal centered at ~500 tokens
    mu_short = np.log(500)
    sigma_short = 0.8
    short = rng.lognormal(mu_short, sigma_short, size=n_short)
    
    # Long conversations: log-normal centered at ~8000 tokens
    mu_long = np.log(8000)
    sigma_long = 0.6
    long = rng.lognormal(mu_long, sigma_long, size=n_long)
    
    combined = np.concatenate([short, long])
    rng.shuffle(combined)
    
    combined = np.clip(combined, config.min_len, config.max_len).astype(int)
    return combined


def generate_output_lengths(n: int, config: ContextConfig) -> np.ndarray:
    """
    Generate output (decode) token counts from a clipped normal distribution.
    
    Returns:
        Array of integer output token counts.
    """
    rng = np.random.default_rng(config.seed + 1000)
    
    std = config.mean_output_tokens * config.output_std_factor
    samples = rng.normal(loc=config.mean_output_tokens, scale=std, size=n)
    samples = np.clip(samples, 1, config.max_len).astype(int)
    
    return samples


# ==============================================================================
# Request Descriptor
# ==============================================================================

@dataclass
class RequestDescriptor:
    """Describes a single multi-tenant request."""
    req_id: int
    arrival_time_ns: int        # When the request arrives (nanoseconds)
    context_len: int            # Total input context length (tokens)
    shared_prefix_len: int      # How many tokens are shared prefix (0 if none)
    output_tokens: int          # Number of decode tokens to generate
    
    @property
    def private_context_len(self) -> int:
        return self.context_len - self.shared_prefix_len
    
    @property
    def total_tokens(self) -> int:
        return self.context_len + self.output_tokens


def generate_request_batch(
    num_requests: int,
    arrival_config: ArrivalConfig,
    context_config: ContextConfig,
    arrival_mode: str = "poisson",
    context_mode: str = "lognormal",
    shared_prefix_len: int = 0
) -> List[RequestDescriptor]:
    """
    Generate a batch of request descriptors with arrival times and context lengths.
    
    Args:
        num_requests: Number of requests to generate
        arrival_config: Arrival process configuration
        context_config: Context length distribution configuration
        arrival_mode: "poisson" or "mmpp"
        context_mode: "lognormal", "zipf", or "sharegpt"
        shared_prefix_len: Length of shared prefix (0 for no sharing)
    
    Returns:
        List of RequestDescriptor sorted by arrival time
    """
    # Generate arrival times
    if arrival_mode == "mmpp":
        arrivals = mmpp_arrivals(arrival_config)
    else:
        arrivals = poisson_arrivals(arrival_config)
    
    # Trim or pad to exact num_requests
    if len(arrivals) > num_requests:
        arrivals = arrivals[:num_requests]
    elif len(arrivals) < num_requests:
        # Extend with additional arrivals
        extra_config = ArrivalConfig(
            rate=arrival_config.rate,
            duration_s=arrival_config.duration_s * 2,
            seed=arrival_config.seed + 999
        )
        extra = poisson_arrivals(extra_config)
        offset = arrivals[-1] if len(arrivals) > 0 else 0
        extra = extra[:num_requests - len(arrivals)] + offset
        arrivals = np.concatenate([arrivals, extra])
    
    # Generate context lengths
    context_funcs = {
        "lognormal": lognormal_context_lengths,
        "zipf": zipf_context_lengths,
        "sharegpt": sharegpt_empirical_distribution,
    }
    context_fn = context_funcs.get(context_mode, lognormal_context_lengths)
    context_lens = context_fn(num_requests, context_config)
    
    # Ensure context >= shared_prefix
    context_lens = np.maximum(context_lens, shared_prefix_len + 128)
    
    # Generate output lengths
    output_lens = generate_output_lengths(num_requests, context_config)
    
    # Build descriptors
    requests = []
    for i in range(num_requests):
        requests.append(RequestDescriptor(
            req_id=i,
            arrival_time_ns=int(arrivals[i]),
            context_len=int(context_lens[i]),
            shared_prefix_len=shared_prefix_len,
            output_tokens=int(output_lens[i])
        ))
    
    # Sort by arrival time
    requests.sort(key=lambda r: r.arrival_time_ns)
    
    return requests


# ==============================================================================
# Visualization Utilities
# ==============================================================================

def plot_arrival_distribution(
    arrivals_ns: np.ndarray,
    title: str = "Request Arrival Distribution",
    output: Optional[str] = None
):
    """Plot histogram of inter-arrival times and arrival rate over time."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Inter-arrival times
    intervals_ms = np.diff(arrivals_ns) / 1e6  # to milliseconds
    axes[0].hist(intervals_ms, bins=50, color='#4A90D9', edgecolor='#2C5F8A', alpha=0.85)
    axes[0].set_xlabel('Inter-arrival Time (ms)', fontsize=12)
    axes[0].set_ylabel('Count', fontsize=12)
    axes[0].set_title('Inter-arrival Time Distribution', fontsize=13, fontweight='bold')
    axes[0].axvline(np.mean(intervals_ms), color='#E74C3C', linestyle='--', 
                    label=f'Mean: {np.mean(intervals_ms):.1f} ms')
    axes[0].legend(fontsize=10)
    
    # Arrival rate over time (1-second bins)
    time_s = arrivals_ns / 1e9
    max_time = time_s[-1] if len(time_s) > 0 else 1.0
    bins = np.arange(0, max_time + 1, 1.0)
    counts, bin_edges = np.histogram(time_s, bins=bins)
    axes[1].bar(bin_edges[:-1], counts, width=0.9, color='#27AE60', edgecolor='#1E8449', alpha=0.85)
    axes[1].set_xlabel('Time (seconds)', fontsize=12)
    axes[1].set_ylabel('Requests/second', fontsize=12)
    axes[1].set_title('Arrival Rate Over Time', fontsize=13, fontweight='bold')
    axes[1].axhline(np.mean(counts), color='#E74C3C', linestyle='--',
                    label=f'Mean: {np.mean(counts):.1f} req/s')
    axes[1].legend(fontsize=10)
    
    plt.tight_layout()
    if output:
        os.makedirs(os.path.dirname(output) if os.path.dirname(output) else ".", exist_ok=True)
        plt.savefig(output, dpi=150, bbox_inches='tight')
        print(f"  Saved: {output}")
    plt.close()


def plot_context_distribution(
    context_lens: np.ndarray,
    title: str = "Context Length Distribution",
    output: Optional[str] = None
):
    """Plot histogram of context lengths."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Linear scale
    axes[0].hist(context_lens, bins=50, color='#9B59B6', edgecolor='#7D3C98', alpha=0.85)
    axes[0].set_xlabel('Context Length (tokens)', fontsize=12)
    axes[0].set_ylabel('Count', fontsize=12)
    axes[0].set_title('Context Length (Linear)', fontsize=13, fontweight='bold')
    axes[0].axvline(np.mean(context_lens), color='#E74C3C', linestyle='--',
                    label=f'Mean: {np.mean(context_lens):.0f}')
    axes[0].axvline(np.median(context_lens), color='#F39C12', linestyle=':',
                    label=f'Median: {np.median(context_lens):.0f}')
    axes[0].legend(fontsize=10)
    
    # Log scale
    log_lens = np.log2(np.maximum(context_lens, 1))
    axes[1].hist(log_lens, bins=50, color='#E67E22', edgecolor='#CA6F1E', alpha=0.85)
    axes[1].set_xlabel('Context Length (log₂ tokens)', fontsize=12)
    axes[1].set_ylabel('Count', fontsize=12)
    axes[1].set_title('Context Length (Log Scale)', fontsize=13, fontweight='bold')
    
    # Add tick labels in tokens
    ticks = [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]
    labels = ['128', '256', '512', '1K', '2K', '4K', '8K', '16K', '32K', '64K', '128K']
    valid = [(t, l) for t, l in zip(ticks, labels) if t <= max(log_lens) + 1]
    if valid:
        axes[1].set_xticks([v[0] for v in valid])
        axes[1].set_xticklabels([v[1] for v in valid])
    
    plt.tight_layout()
    if output:
        os.makedirs(os.path.dirname(output) if os.path.dirname(output) else ".", exist_ok=True)
        plt.savefig(output, dpi=150, bbox_inches='tight')
        print(f"  Saved: {output}")
    plt.close()


# ==============================================================================
# Statistical Validation
# ==============================================================================

def validate_poisson(arrivals_ns: np.ndarray, expected_rate: float) -> dict:
    """
    Validate that arrivals follow a Poisson process via KS test on inter-arrival times.
    
    Returns:
        Dictionary with test statistics and pass/fail.
    """
    intervals_s = np.diff(arrivals_ns) / 1e9
    
    if len(intervals_s) < 10:
        return {"valid": False, "reason": "Too few samples"}
    
    # KS test against exponential distribution
    ks_stat, p_value = stats.kstest(intervals_s, 'expon', args=(0, 1.0 / expected_rate))
    
    observed_rate = len(arrivals_ns) / (arrivals_ns[-1] / 1e9) if arrivals_ns[-1] > 0 else 0
    
    return {
        "valid": p_value > 0.05,
        "ks_statistic": float(ks_stat),
        "p_value": float(p_value),
        "expected_rate": expected_rate,
        "observed_rate": float(observed_rate),
        "num_events": len(arrivals_ns),
        "duration_s": float(arrivals_ns[-1] / 1e9) if len(arrivals_ns) > 0 else 0
    }


if __name__ == "__main__":
    """Quick demo / sanity check."""
    print("=" * 60)
    print("Workload Distribution Models - Demo")
    print("=" * 60)
    
    # Demo: Poisson arrivals
    arr_cfg = ArrivalConfig(rate=10.0, duration_s=30.0, seed=42)
    arrivals = poisson_arrivals(arr_cfg)
    print(f"\nPoisson arrivals (λ=10 req/s, 30s):")
    print(f"  Generated: {len(arrivals)} events")
    
    validation = validate_poisson(arrivals, arr_cfg.rate)
    print(f"  KS test p-value: {validation['p_value']:.4f} "
          f"({'PASS' if validation['valid'] else 'FAIL'})")
    print(f"  Observed rate: {validation['observed_rate']:.2f} req/s")
    
    # Demo: MMPP arrivals
    mmpp = mmpp_arrivals(ArrivalConfig(rate_high=50.0, rate_low=2.0, 
                                        switch_prob=0.05, duration_s=30.0, seed=42))
    print(f"\nMMPP arrivals (bursty, 30s):")
    print(f"  Generated: {len(mmpp)} events")
    
    # Demo: Context length distributions
    ctx_cfg = ContextConfig(mean_len=4096, seed=42)
    
    for mode_name, mode_fn in [("Log-Normal", lognormal_context_lengths),
                                ("Zipf", zipf_context_lengths),
                                ("ShareGPT", sharegpt_empirical_distribution)]:
        samples = mode_fn(1000, ctx_cfg)
        print(f"\n{mode_name} context lengths (n=1000):")
        print(f"  Mean: {np.mean(samples):.0f}, Median: {np.median(samples):.0f}")
        print(f"  Min: {np.min(samples)}, Max: {np.max(samples)}")
        print(f"  P90: {np.percentile(samples, 90):.0f}, "
              f"P99: {np.percentile(samples, 99):.0f}")
    
    # Save demo plots
    demo_dir = "traces/multitenant"
    os.makedirs(demo_dir, exist_ok=True)
    
    plot_arrival_distribution(arrivals, output=f"{demo_dir}/demo_arrival_dist.png")
    
    ctx_samples = lognormal_context_lengths(1000, ctx_cfg)
    plot_context_distribution(ctx_samples, output=f"{demo_dir}/demo_context_dist.png")
    
    print(f"\n✅ Demo complete. Plots saved to {demo_dir}/")
