#!/usr/bin/env python3
"""Generate clean conceptual hardware schematics for the thesis assets."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "paper_assets" / "figures"

COLORS = {
    "input": "#EAF2FB",
    "logic": "#E8F6F3",
    "reg": "#ECEFF1",
    "side": "#FFF3E0",
    "merge": "#F3EAFB",
    "stroke": "#333333",
}


def style_axis(ax, xlim: tuple[float, float], ylim: tuple[float, float]) -> None:
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")


def box(
    ax,
    xy: tuple[float, float],
    width: float,
    height: float,
    label: str,
    facecolor: str,
    fontsize: float = 10.5,
    weight: str = "normal",
) -> FancyBboxPatch:
    patch = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle="round,pad=0.03,rounding_size=0.06",
        linewidth=1.2,
        edgecolor=COLORS["stroke"],
        facecolor=facecolor,
    )
    ax.add_patch(patch)
    ax.text(
        xy[0] + width / 2,
        xy[1] + height / 2,
        label,
        ha="center",
        va="center",
        fontsize=fontsize,
        fontweight=weight,
    )
    return patch


def arrow(
    ax,
    start: tuple[float, float],
    end: tuple[float, float],
    label: str | None = None,
    rad: float = 0.0,
    color: str = "#333333",
) -> None:
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=12,
        linewidth=1.35,
        color=color,
        connectionstyle=f"arc3,rad={rad}",
    )
    ax.add_patch(patch)
    if label:
        ax.text(
            (start[0] + end[0]) / 2,
            (start[1] + end[1]) / 2 + 0.22,
            label,
            ha="center",
            va="bottom",
            fontsize=8.8,
            color=color,
        )


def save(fig, name: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_DIR / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(OUTPUT_DIR / f"{name}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def generate_inlu_schematic() -> None:
    fig, ax = plt.subplots(figsize=(9.2, 3.25))
    style_axis(ax, (-0.25, 10.9), (-0.6, 3.0))

    y = 1.05
    h = 0.9
    w = 1.45
    xs = [0.0, 1.75, 3.5, 5.25, 7.0, 8.75]
    labels = [
        "Q10 logits\n$x_i$",
        "Range\nreduction\n$n, f$",
        "Integer\npolynomial\n$e^f$",
        "Power-of-two\nshift\n$2^n$",
        "Q24 integer\nnormalization",
        "Attention\nweights",
    ]
    faces = [
        COLORS["input"],
        COLORS["logic"],
        COLORS["logic"],
        COLORS["logic"],
        COLORS["merge"],
        COLORS["input"],
    ]

    for x, label, face in zip(xs, labels, faces):
        box(ax, (x, y), w, h, label, face, fontsize=9.8, weight="bold")

    for i in range(len(xs) - 1):
        arrow(ax, (xs[i] + w, y + h / 2), (xs[i + 1], y + h / 2))

    reg_y = 0.2
    for x in [2.85, 4.6, 6.35]:
        box(ax, (x, reg_y), 0.55, 0.42, "REG", COLORS["reg"], fontsize=8.2, weight="bold")
        arrow(ax, (x + 0.27, reg_y + 0.42), (x + 0.27, y), color="#666666")

    box(ax, (2.0, 2.35), 1.25, 0.45, "$\\ln 2$", COLORS["side"], fontsize=9.2)
    box(ax, (3.9, 2.35), 1.65, 0.45, "A/B/C constants", COLORS["side"], fontsize=9.2)
    arrow(ax, (2.62, 2.35), (2.42, y + h), color="#8A6D3B")
    arrow(ax, (4.72, 2.35), (4.22, y + h), color="#8A6D3B")

    ax.text(
        5.2,
        -0.23,
        "Fixed-point datapath: Q10 input, integer exponential approximation, Q24 normalization",
        ha="center",
        va="center",
        fontsize=10.2,
        color="#444444",
    )
    save(fig, "fig8_inlu_schematic")


def generate_outlier_schematic() -> None:
    fig, ax = plt.subplots(figsize=(8.8, 3.8))
    style_axis(ax, (-0.25, 10.2), (-0.3, 4.0))

    box(ax, (0.0, 1.45), 1.35, 0.85, "Activation\n$x$", COLORS["input"], weight="bold")
    box(ax, (1.75, 1.45), 1.35, 0.85, "Abs +\nthreshold\ncompare", COLORS["logic"], fontsize=9.6, weight="bold")
    box(ax, (3.65, 1.45), 1.15, 0.85, "Route\nselect", COLORS["merge"], fontsize=9.6, weight="bold")
    box(ax, (5.55, 2.45), 1.55, 0.85, "High-precision\noutlier buffer\n16 entries", COLORS["side"], fontsize=9.0, weight="bold")
    box(ax, (5.55, 0.55), 1.55, 0.85, "Quantized\nINT8 main path", COLORS["logic"], fontsize=9.2, weight="bold")
    box(ax, (7.85, 1.45), 1.35, 0.85, "Merge /\nreduction", COLORS["merge"], fontsize=9.6, weight="bold")

    arrow(ax, (1.35, 1.87), (1.75, 1.87))
    arrow(ax, (3.1, 1.87), (3.65, 1.87))
    arrow(ax, (4.8, 1.9), (5.55, 2.88), label="$|x| > \\Theta$", rad=0.18, color="#C44E52")
    arrow(ax, (4.8, 1.82), (5.55, 0.98), label="common case", rad=-0.18, color="#4C72B0")
    arrow(ax, (7.1, 2.88), (7.85, 1.92), rad=-0.18, color="#C44E52")
    arrow(ax, (7.1, 0.98), (7.85, 1.78), rad=0.18, color="#4C72B0")
    arrow(ax, (9.2, 1.87), (9.9, 1.87))

    ax.text(9.95, 1.87, "PIM output", ha="left", va="center", fontsize=10.2)
    ax.text(
        5.37,
        3.55,
        "Rare large activations keep higher precision; dense traffic stays in the INT8 path.",
        ha="center",
        va="center",
        fontsize=10.0,
        color="#444444",
    )
    ax.text(6.35, 2.22, "o_outlier_val", ha="center", va="top", fontsize=8.6, color="#8A5A00")
    ax.text(6.35, 0.34, "o_data_int8", ha="center", va="top", fontsize=8.6, color="#2F5D8C")
    save(fig, "fig9_outlier_schematic")


def main() -> None:
    generate_inlu_schematic()
    generate_outlier_schematic()
    print("Generated fig8_inlu_schematic and fig9_outlier_schematic as PDF/PNG")


if __name__ == "__main__":
    main()
