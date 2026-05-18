# Data Provenance Notes

Updated: `2026-04-22`

This directory stores the compact data summaries used to generate figures and to support the synchronized thesis in `thesis/`.

## Main Files

- `paper_metrics.json`
  - Distributed-system plot data for throughput vs. tail latency, traffic breakdown, scalability, and fault recovery.
  - Used by the multi-node evaluation figures in `paper_assets/figures/`.
  - Includes a `_provenance` block plus per-section `model` blocks. These distinguish simulator-derived counters from analytical queueing and baseline-comparison assumptions.

- `inlu_overhead_comparison.json`
  - Single-node energy trend summary for representative context lengths.
  - Supports the area/energy discussion in the thesis evaluation chapter.

- `sensitivity_metrics.json`
  - Sensitivity data for interconnect latency and outlier-buffer sizing.
  - Supports the figures discussing robustness to fabric delay and the area-accuracy tradeoff of the outlier path.

- `inlu_accuracy_metrics.json`
  - Fixed-point golden-model output for the iNLU softmax approximation.
  - Records the Q10 input scale, Q24 output normalization, polynomial constants, reference vector, and error metrics used by `fig4_inlu_accuracy`.

- `attention_quality_metrics.json`
  - Lightweight attention-output quality benchmark comparing FP32 attention against the fixed-point iNLU path on synthetic Q/K/V vectors.
  - Reports attention-weight KL divergence, output-vector relative L2 error, and cosine similarity across 128, 512, and 2048-token sequences.

- `ramulator_results.md`
  - Human-readable summary derived from `simulation_results.csv`.
  - Useful for repository walkthroughs, but the CSV remains the authoritative single-node result source.

## Related Files Outside This Directory

- `simulation_results.csv`
  - Trace-level Ramulator output summary for baseline vs. `PIM-KV`.
  - Authoritative single-node comparison table.

- `results/fault_recovery_results.json`
  - Detailed event-level output for the injected-fault experiment.
  - Source for the p95 recovery number reported in the thesis.

## Refresh Path

Typical regeneration flow:

```bash
conda activate lkcpim
bash scripts/reproduce_results.sh
python3 scripts/generate_paper_data.py
python3 scripts/iNLU_algorithm_sim.py
python3 scripts/evaluate_attention_quality.py
python3 scripts/generate_paper_figures.py
python3 scripts/plot_paper_figures.py
python3 scripts/plot_ramulator_results.py
python3 scripts/generate_schematic_figures.py
```

If the regenerated numbers differ from the thesis text, update the thesis and the repository summaries together so that the evidence chain remains consistent.

`generate_paper_data.py` now fails on missing source files instead of silently filling in synthetic values. If it fails, regenerate the missing artifact first rather than editing `paper_metrics.json` by hand.

## Optional Perplexity Output

`scripts/evaluate_perplexity.py` can produce `paper_assets/data/perplexity_results.json` for an end-to-end language-model quality check. This file is optional because it depends on external model and dataset packages. Use the synthetic smoke mode for local validation, and use a real model run only when `datasets` and the selected model loader are installed.
