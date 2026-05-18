#!/usr/bin/env python3
"""
Lightweight repository validation for thesis/project handoff.

The checks are intentionally fast and local: they verify that the active Python
environment can run the important self-tests, that generated paper data carries
provenance, and that removed split-paper drafts have not reappeared.
"""

from __future__ import annotations

import argparse
import json
import py_compile
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REMOVED_DRAFTS = ["pimmain.tex", "pimmain.pdf", "cxlmain.tex", "cxlmain.pdf"]
CREDIBILITY_PHRASES = [
    "Target speedup",
    "hit the 4.2x claim",
    "dummy mapping",
    "Fallback values if simulation results missing",
]
REQUIRED_FIGURES = [
    "fig1_latency_breakdown",
    "fig1_throughput_latency",
    "fig2_energy_comparison",
    "fig2_scalability",
    "fig3_kv_cache_scaling",
    "fig3_network_breakdown",
    "fig4_fault_recovery",
    "fig4_inlu_accuracy",
    "fig5_performance_speedup",
    "fig5_sensitivity_latency",
    "fig6_area_breakdown",
    "fig7_ramulator_comparison",
    "fig8_inlu_schematic",
    "fig9_outlier_schematic",
    "fig10_sensitivity_outliers",
    "fig11_attention_quality",
]


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def fail(message: str) -> None:
    raise RuntimeError(message)


def check_removed_drafts() -> None:
    found = [name for name in REMOVED_DRAFTS if (ROOT / name).exists()]
    if found:
        fail(f"Removed standalone drafts are present again: {', '.join(found)}")


def check_paper_metrics() -> None:
    metrics_path = ROOT / "paper_assets/data/paper_metrics.json"
    if not metrics_path.exists():
        fail(f"Missing {rel(metrics_path)}")
    data = json.loads(metrics_path.read_text())
    provenance = data.get("_provenance")
    if not provenance:
        fail("paper_metrics.json is missing the _provenance block")
    for source in provenance.get("sources", []):
        source_path = ROOT / source
        if not source_path.exists():
            fail(f"paper_metrics.json references missing source: {source}")
    for section in ["throughput_latency", "traffic_breakdown", "fault_recovery", "scalability"]:
        if "model" not in data.get(section, {}):
            fail(f"paper_metrics.json section lacks model metadata: {section}")


def check_inlu_metrics() -> None:
    metrics_path = ROOT / "paper_assets/data/inlu_accuracy_metrics.json"
    if not metrics_path.exists():
        fail(f"Missing {rel(metrics_path)}")
    data = json.loads(metrics_path.read_text())
    if not data.get("_provenance"):
        fail("inlu_accuracy_metrics.json is missing the _provenance block")
    config = data.get("config", {})
    if config.get("scale_bits") != 10 or config.get("output_bits") != 24:
        fail("iNLU metrics must record Q10 input and Q24 output configuration")
    metrics = data.get("metrics", {})
    for name in ["poly", "lut"]:
        if "mse" not in metrics.get(name, {}):
            fail(f"iNLU metrics missing MSE for {name}")


def check_attention_quality_metrics() -> None:
    metrics_path = ROOT / "paper_assets/data/attention_quality_metrics.json"
    if not metrics_path.exists():
        fail(f"Missing {rel(metrics_path)}")
    data = json.loads(metrics_path.read_text())
    if not data.get("_provenance"):
        fail("attention_quality_metrics.json is missing the _provenance block")
    summary = data.get("summary", {})
    required = [
        "min_output_cosine_p05",
        "max_output_relative_l2_p95",
        "max_weight_kl_p95",
    ]
    for key in required:
        if key not in summary:
            fail(f"attention_quality_metrics.json summary missing: {key}")
    if summary["min_output_cosine_p05"] < 0.999:
        fail("Attention-quality cosine check fell below 0.999")


def check_figure_assets() -> None:
    figure_dir = ROOT / "paper_assets/figures"
    for stem in REQUIRED_FIGURES:
        for suffix in [".pdf", ".png"]:
            path = figure_dir / f"{stem}{suffix}"
            if not path.exists():
                fail(f"Missing figure asset: {rel(path)}")
            if path.stat().st_size < 1_000:
                fail(f"Figure asset looks too small to be valid: {rel(path)}")
    for stem in ["fig8_inlu_schematic", "fig9_outlier_schematic"]:
        path = figure_dir / f"{stem}.dot"
        if not path.exists():
            fail(f"Missing schematic source: {rel(path)}")


def check_credibility_phrases() -> None:
    paths = [
        *sorted((ROOT / "scripts").glob("*.py")),
        ROOT / "README.md",
        ROOT / "task.md",
    ]
    offenders: list[str] = []
    for path in paths:
        if path.resolve() == Path(__file__).resolve():
            continue
        if not path.exists():
            continue
        text = path.read_text(errors="ignore")
        for phrase in CREDIBILITY_PHRASES:
            if phrase in text:
                offenders.append(f"{rel(path)}: {phrase}")
    if offenders:
        fail("Credibility-risk phrases remain:\n" + "\n".join(offenders))


def compile_python() -> None:
    py_files = list((ROOT / "scripts").glob("*.py"))
    py_files += list((ROOT / "ramulator2/verilog_verification").glob("*.py"))
    for path in sorted(py_files):
        py_compile.compile(str(path), doraise=True)


def run_command(cmd: list[str], cwd: Path = ROOT) -> None:
    result = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, check=False)
    if result.returncode != 0:
        fail(
            "Command failed: "
            + " ".join(cmd)
            + "\nstdout:\n"
            + result.stdout
            + "\nstderr:\n"
            + result.stderr
        )


def run_self_tests() -> None:
    run_command([sys.executable, "scripts/cxl_fabric_simulator.py", "--test"])
    run_command([sys.executable, "scripts/host_os_scheduler.py", "--test"])


def run_perplexity_smoke() -> None:
    run_command([
        sys.executable,
        "scripts/evaluate_perplexity.py",
        "--synthetic-smoke",
        "--output",
        "/tmp/lkc_perplexity_smoke.json",
    ])


def run_latex_checks() -> None:
    run_command(["latexmk", "-pdfxe", "-interaction=nonstopmode", "-halt-on-error", "main.tex"], ROOT / "thesis")
    run_command(["latexmk", "-pdfxe", "-interaction=nonstopmode", "-halt-on-error", "main.tex"], ROOT / "thesis_cn")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run lightweight LKC-CXL-PIM project validation.")
    parser.add_argument("--latex", action="store_true", help="Also check thesis and thesis_cn with latexmk.")
    parser.add_argument("--skip-self-tests", action="store_true", help="Skip simulator self-tests.")
    args = parser.parse_args()

    checks = [
        ("removed drafts", check_removed_drafts),
        ("paper metrics provenance", check_paper_metrics),
        ("iNLU metrics provenance", check_inlu_metrics),
        ("attention quality provenance", check_attention_quality_metrics),
        ("figure assets", check_figure_assets),
        ("credibility phrases", check_credibility_phrases),
        ("python syntax", compile_python),
    ]
    if not args.skip_self_tests:
        checks.append(("simulator self-tests", run_self_tests))
        checks.append(("perplexity smoke test", run_perplexity_smoke))
    if args.latex:
        checks.append(("latex builds", run_latex_checks))

    for name, fn in checks:
        print(f"[check] {name}")
        fn()

    print("All validation checks passed.")


if __name__ == "__main__":
    main()
