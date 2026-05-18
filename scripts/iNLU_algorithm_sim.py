#!/usr/bin/env python3
"""
Fixed-point golden model for the Integer Non-Linear Unit (iNLU).

The model follows the thesis datapath:
  1. subtract the row maximum for softmax stability,
  2. quantize logits into Q10 fixed point,
  3. use base-2 range reduction with p in [-ln2, 0],
  4. approximate exp(p) with the I-BERT-style quadratic polynomial,
  5. normalize with an integer Q24 quotient.

After step 2, the polynomial path uses integer arithmetic only. The FP32
softmax is used only as the reference target for error measurement.
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


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METRICS = ROOT / "paper_assets/data/inlu_accuracy_metrics.json"
DEFAULT_FIGURE = ROOT / "paper_assets/notes/iNLU_accuracy_test.png"

SCALE_BITS = 10
SCALE = 1 << SCALE_BITS
OUTPUT_BITS = 24
OUTPUT_SCALE = 1 << OUTPUT_BITS
LN2_Q10 = 710
COEFF_A = 367
COEFF_B = 1385
COEFF_C = 352
DEFAULT_LUT_ENTRIES = 64


def softmax_fp32(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits)
    exp_vals = np.exp(shifted)
    return exp_vals / np.sum(exp_vals)


def quantize_shifted_logits(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits)
    return np.rint(shifted * SCALE).astype(np.int64)


def integer_normalize(exp_q10: np.ndarray, output_bits: int = OUTPUT_BITS) -> np.ndarray:
    total = int(np.sum(exp_q10))
    if total <= 0:
        raise ValueError("Cannot normalize non-positive fixed-point exponent sum")
    numerators = exp_q10.astype(np.int64) << output_bits
    return ((numerators + total // 2) // total).astype(np.int64)


def fixed_point_poly_exp_q10(x_q10: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    # Choose z = ceil(x / ln2), leaving p = x - z*ln2 in [-ln2, 0].
    z = -np.floor_divide(-x_q10, LN2_Q10)
    p = x_q10 - z * LN2_Q10

    # exp(p) ~= A * (p + B)^2 + C, with constants scaled for Q10.
    p_plus_b = p + COEFF_B
    poly = ((COEFF_A * (p_plus_b ** 2)) >> 20) + COEFF_C

    exp_q10 = np.empty_like(poly, dtype=np.int64)
    neg = z < 0
    exp_q10[neg] = poly[neg] >> (-z[neg])
    exp_q10[~neg] = poly[~neg] << z[~neg]
    exp_q10 = np.maximum(exp_q10, 0)
    return exp_q10, z, p


def fixed_point_lut_exp_q10(x_q10: np.ndarray, entries: int = DEFAULT_LUT_ENTRIES) -> np.ndarray:
    z = -np.floor_divide(-x_q10, LN2_Q10)
    p = x_q10 - z * LN2_Q10
    samples = np.linspace(-np.log(2), 0.0, entries)
    table = np.rint(np.exp(samples) * SCALE).astype(np.int64)
    idx = np.rint((p + LN2_Q10) * (entries - 1) / LN2_Q10).astype(np.int64)
    idx = np.clip(idx, 0, entries - 1)
    val = table[idx]

    exp_q10 = np.empty_like(val, dtype=np.int64)
    neg = z < 0
    exp_q10[neg] = val[neg] >> (-z[neg])
    exp_q10[~neg] = val[~neg] << z[~neg]
    return np.maximum(exp_q10, 0)


def q_to_probability(values_q: np.ndarray, bits: int = OUTPUT_BITS) -> np.ndarray:
    return values_q.astype(np.float64) / float(1 << bits)


def error_metrics(reference: np.ndarray, candidate: np.ndarray) -> dict[str, float]:
    abs_error = np.abs(reference - candidate)
    rel_error = abs_error / np.maximum(reference, 1e-12)
    return {
        "mse": float(np.mean((reference - candidate) ** 2)),
        "mae": float(np.mean(abs_error)),
        "max_abs_error": float(np.max(abs_error)),
        "mean_relative_error_pct": float(np.mean(rel_error) * 100.0),
        "max_relative_error_pct": float(np.max(rel_error) * 100.0),
    }


def evaluate(seed: int = 42, vector_len: int = 16, logit_scale: float = 2.0) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    logits = rng.normal(0.0, logit_scale, vector_len)
    reference = softmax_fp32(logits)
    x_q10 = quantize_shifted_logits(logits)

    poly_exp_q10, range_z, range_p = fixed_point_poly_exp_q10(x_q10)
    poly_q24 = integer_normalize(poly_exp_q10)
    poly_prob = q_to_probability(poly_q24)

    lut_exp_q10 = fixed_point_lut_exp_q10(x_q10)
    lut_q24 = integer_normalize(lut_exp_q10)
    lut_prob = q_to_probability(lut_q24)

    return {
        "_provenance": {
            "generated_by": "scripts/iNLU_algorithm_sim.py",
            "seed": seed,
            "vector_len": vector_len,
            "logit_scale": logit_scale,
            "reference": "FP32 softmax after max subtraction",
            "integer_path": "Q10 polynomial exponential plus Q24 integer normalization",
        },
        "config": {
            "scale_bits": SCALE_BITS,
            "output_bits": OUTPUT_BITS,
            "ln2_q10": LN2_Q10,
            "coeff_a": COEFF_A,
            "coeff_b": COEFF_B,
            "coeff_c": COEFF_C,
            "lut_entries": DEFAULT_LUT_ENTRIES,
        },
        "vectors": {
            "logits": logits.tolist(),
            "shifted_logits_q10": x_q10.tolist(),
            "range_z": range_z.tolist(),
            "range_p_q10": range_p.tolist(),
            "fp32_softmax": reference.tolist(),
            "poly_exp_q10": poly_exp_q10.tolist(),
            "poly_softmax_q24": poly_q24.tolist(),
            "poly_softmax": poly_prob.tolist(),
            "lut_softmax": lut_prob.tolist(),
        },
        "metrics": {
            "poly": error_metrics(reference, poly_prob),
            "lut": error_metrics(reference, lut_prob),
        },
    }


def save_plot(metrics: dict[str, Any], output: Path) -> None:
    vectors = metrics["vectors"]
    reference = np.array(vectors["fp32_softmax"], dtype=np.float64)
    poly = np.array(vectors["poly_softmax"], dtype=np.float64)
    lut = np.array(vectors["lut_softmax"], dtype=np.float64)
    x = np.arange(len(reference))
    width = 0.25

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

    ax1.bar(x - width, reference, width, label="FP32 reference", color="#DD8452")
    ax1.bar(x, poly, width, label="Fixed-point iNLU", color="#1ABC9C")
    ax1.bar(x + width, lut, width, label="Fixed-point LUT", color="#34495E")
    ax1.set_xlabel("Softmax Output Index")
    ax1.set_ylabel("Probability")
    ax1.set_title("Softmax Output Comparison")
    ax1.set_xticks(x[::2])
    ax1.legend(frameon=False)

    poly_error = np.abs(reference - poly) / np.maximum(reference, 1e-12) * 100.0
    lut_error = np.abs(reference - lut) / np.maximum(reference, 1e-12) * 100.0
    ax2.bar(x - width / 2, poly_error, width, label="iNLU error", color="#1ABC9C")
    ax2.bar(x + width / 2, lut_error, width, label="LUT error", color="#34495E")
    ax2.set_xlabel("Softmax Output Index")
    ax2.set_ylabel("Relative Error (%)")
    ax2.set_title("Fixed-Point Error")
    ax2.set_xticks(x[::2])
    ax2.legend(frameon=False)

    poly_mse = metrics["metrics"]["poly"]["mse"]
    lut_mse = metrics["metrics"]["lut"]["mse"]
    ax2.text(
        0.98,
        0.95,
        f"MSE (iNLU): {poly_mse:.2e}\nMSE (LUT): {lut_mse:.2e}",
        transform=ax2.transAxes,
        fontsize=9,
        va="top",
        ha="right",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.85, edgecolor="#cccccc"),
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output, dpi=300)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the fixed-point iNLU golden model.")
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--figure", type=Path, default=DEFAULT_FIGURE)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--vector-len", type=int, default=16)
    parser.add_argument("--logit-scale", type=float, default=2.0)
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args()

    metrics = evaluate(args.seed, args.vector_len, args.logit_scale)
    metrics_path = args.metrics if args.metrics.is_absolute() else ROOT / args.metrics
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with metrics_path.open("w") as f:
        json.dump(metrics, f, indent=2)
        f.write("\n")

    if not args.no_plot:
        figure_path = args.figure if args.figure.is_absolute() else ROOT / args.figure
        save_plot(metrics, figure_path)

    poly = metrics["metrics"]["poly"]
    lut = metrics["metrics"]["lut"]
    print(f"iNLU fixed-point MSE: {poly['mse']:.8e}")
    print(f"LUT fixed-point MSE:  {lut['mse']:.8e}")
    print(f"Metrics saved to: {metrics_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
