#!/usr/bin/env python3
"""
Attention-output quality benchmark for the fixed-point iNLU path.

This is a lightweight application-level check: it compares single-head FP32
attention against the fixed-point iNLU softmax path over synthetic Q/K/V
vectors. It is not a language-model perplexity run, but it directly measures
whether the iNLU approximation preserves attention weights and output vectors.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from figure_style import COLORS, apply_conference_style, clean_axis
from iNLU_algorithm_sim import (
    fixed_point_poly_exp_q10,
    integer_normalize,
    q_to_probability,
    softmax_fp32,
)

apply_conference_style()

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "paper_assets/data/attention_quality_metrics.json"
DEFAULT_FIGURE = ROOT / "paper_assets/figures/fig11_attention_quality.pdf"


def fixed_point_inlu_softmax(logits: np.ndarray) -> np.ndarray:
    shifted_q10 = np.rint((logits - np.max(logits)) * 1024).astype(np.int64)
    exp_q10, _, _ = fixed_point_poly_exp_q10(shifted_q10)
    prob_q24 = integer_normalize(exp_q10)
    return q_to_probability(prob_q24)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 1.0 if np.linalg.norm(a - b) == 0 else 0.0
    return float(np.dot(a, b) / denom)


def kl_divergence(p: np.ndarray, q: np.ndarray) -> float:
    eps = 1e-12
    p_safe = np.maximum(p, eps)
    q_safe = np.maximum(q, eps)
    return float(np.sum(p_safe * np.log(p_safe / q_safe)))


def evaluate_seq_len(
    rng: np.random.Generator,
    seq_len: int,
    head_dim: int,
    trials: int,
    value_scale: float,
) -> dict[str, Any]:
    weight_mse: list[float] = []
    weight_kl: list[float] = []
    output_mse: list[float] = []
    output_mae: list[float] = []
    output_rel_l2: list[float] = []
    output_cosine: list[float] = []

    scale = 1.0 / np.sqrt(head_dim)
    for _ in range(trials):
        q = rng.normal(0.0, 1.0, head_dim)
        k = rng.normal(0.0, 1.0, (seq_len, head_dim))
        v = rng.normal(0.0, value_scale, (seq_len, head_dim))

        logits = (k @ q) * scale
        weights_ref = softmax_fp32(logits)
        weights_i = fixed_point_inlu_softmax(logits)

        out_ref = weights_ref @ v
        out_i = weights_i @ v
        diff = out_ref - out_i

        weight_mse.append(float(np.mean((weights_ref - weights_i) ** 2)))
        weight_kl.append(kl_divergence(weights_ref, weights_i))
        output_mse.append(float(np.mean(diff ** 2)))
        output_mae.append(float(np.mean(np.abs(diff))))
        output_rel_l2.append(float(np.linalg.norm(diff) / max(np.linalg.norm(out_ref), 1e-12)))
        output_cosine.append(cosine_similarity(out_ref, out_i))

    def summarize(values: list[float]) -> dict[str, float]:
        arr = np.array(values, dtype=np.float64)
        return {
            "mean": float(np.mean(arr)),
            "p95": float(np.percentile(arr, 95)),
            "max": float(np.max(arr)),
        }

    return {
        "seq_len": seq_len,
        "trials": trials,
        "weight_mse": summarize(weight_mse),
        "weight_kl": summarize(weight_kl),
        "output_mse": summarize(output_mse),
        "output_mae": summarize(output_mae),
        "output_relative_l2": summarize(output_rel_l2),
        "output_cosine": {
            "mean": float(np.mean(output_cosine)),
            "p05": float(np.percentile(output_cosine, 5)),
            "min": float(np.min(output_cosine)),
        },
    }


def evaluate(
    seed: int,
    seq_lens: list[int],
    head_dim: int,
    trials: int,
    value_scale: float,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    results = [
        evaluate_seq_len(rng, seq_len, head_dim, trials, value_scale)
        for seq_len in seq_lens
    ]
    return {
        "_provenance": {
            "generated_by": "scripts/evaluate_attention_quality.py",
            "seed": seed,
            "benchmark": "single-head synthetic Q/K/V attention",
            "reference": "FP32 softmax attention",
            "candidate": "Q10 fixed-point iNLU softmax with Q24 normalization",
        },
        "config": {
            "seq_lens": seq_lens,
            "head_dim": head_dim,
            "trials_per_seq_len": trials,
            "value_scale": value_scale,
        },
        "results": results,
        "summary": {
            "min_output_cosine_p05": float(min(r["output_cosine"]["p05"] for r in results)),
            "max_output_relative_l2_p95": float(max(r["output_relative_l2"]["p95"] for r in results)),
            "max_weight_kl_p95": float(max(r["weight_kl"]["p95"] for r in results)),
        },
    }


def save_plot(data: dict[str, Any], output: Path) -> None:
    results = data["results"]
    seq_lens = [str(r["seq_len"]) for r in results]
    cosine_p05 = [r["output_cosine"]["p05"] for r in results]
    rel_l2_p95 = [r["output_relative_l2"]["p95"] for r in results]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.1, 3.15))
    x = np.arange(len(seq_lens))
    width = 0.55

    ax1.bar(x, cosine_p05, width, color=COLORS["ours"], edgecolor="black")
    ax1.set_ylim(0.995, 1.0002)
    ax1.set_ylabel("Cosine Similarity")
    ax1.set_xticks(x)
    ax1.set_xticklabels(seq_lens)
    ax1.set_xlabel("Sequence Length")
    ax1.set_title("Output Cosine p05")

    ax2.bar(x, rel_l2_p95, width, color=COLORS["fault"], edgecolor="black")
    ax2.set_ylabel("Relative L2 Error")
    ax2.set_xticks(x)
    ax2.set_xticklabels(seq_lens)
    ax2.set_xlabel("Sequence Length")
    ax2.set_title("Relative L2 p95")

    clean_axis(ax1)
    clean_axis(ax2)

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output, bbox_inches="tight")
    if output.suffix.lower() == ".pdf":
        fig.savefig(output.with_suffix(".png"), dpi=300, bbox_inches="tight")
    plt.close(fig)


def parse_seq_lens(text: str) -> list[int]:
    values = [int(part.strip()) for part in text.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("At least one sequence length is required")
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate iNLU attention-output quality.")
    parser.add_argument("--seq-lens", type=parse_seq_lens, default=[128, 512, 2048])
    parser.add_argument("--head-dim", type=int, default=64)
    parser.add_argument("--trials", type=int, default=128)
    parser.add_argument("--value-scale", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--figure", type=Path, default=DEFAULT_FIGURE)
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args()

    data = evaluate(args.seed, args.seq_lens, args.head_dim, args.trials, args.value_scale)

    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    if not args.no_plot:
        figure = args.figure if args.figure.is_absolute() else ROOT / args.figure
        save_plot(data, figure)

    summary = data["summary"]
    print(f"min output cosine p05: {summary['min_output_cosine_p05']:.8f}")
    print(f"max output relative-L2 p95: {summary['max_output_relative_l2_p95']:.8f}")
    print(f"max attention-weight KL p95: {summary['max_weight_kl_p95']:.8e}")
    print(f"Metrics saved to: {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
