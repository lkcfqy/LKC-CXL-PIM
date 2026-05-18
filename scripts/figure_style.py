"""Shared plotting style for thesis and paper figures.

The palette follows a restrained, colorblind-safe systems-paper style: neutral
gray for baselines, blue for the proposed design, and a small set of supporting
colors for compute, traffic, and error components.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt


COLORS = {
    "baseline": "#6E6E6E",
    "ours": "#0072B2",
    "host": "#6E6E6E",
    "ideal": "#222222",
    "compute": "#009E73",
    "dequant": "#D55E00",
    "kv_io": "#0072B2",
    "fp32": "#6E6E6E",
    "inlu": "#0072B2",
    "lut": "#E69F00",
    "area": "#CC79A7",
    "fault": "#D55E00",
    "p2p": "#009E73",
    "grid": "#D9D9D9",
    "text": "#222222",
}

HATCHES = {
    "baseline": "///",
    "ours": "\\\\\\",
    "host": "///",
    "compute": "",
    "dequant": "...",
    "kv_io": "///",
    "inlu": "\\\\\\",
    "lut": "...",
    "p2p": "",
}


def apply_conference_style() -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    matplotlib.rcParams.update({
        "font.family": "serif",
        "font.size": 10,
        "axes.labelsize": 10.5,
        "axes.titlesize": 10.5,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 8.8,
        "lines.linewidth": 1.8,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "axes.edgecolor": COLORS["text"],
        "axes.facecolor": "white",
        "grid.color": COLORS["grid"],
        "grid.alpha": 0.65,
        "grid.linestyle": "--",
        "grid.linewidth": 0.55,
        "patch.linewidth": 0.75,
        "legend.frameon": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def clean_axis(ax, grid_axis: str = "y", hide_right: bool = True) -> None:
    ax.grid(axis=grid_axis)
    ax.spines["top"].set_visible(False)
    if hide_right:
        ax.spines["right"].set_visible(False)


def save_pdf_png(fig, output_dir: str | Path, stem: str) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_dir / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(output_dir / f"{stem}.png", dpi=300, bbox_inches="tight")
