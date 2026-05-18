# LKC-CXL-PIM Repository Status

Updated: `2026-04-22`

## Scope

This repository tracks two closely related research artifacts:

1. `LKC-CXL-PIM`, which studies single-node near-memory KV-cache attention with an integer nonlinear unit and outlier-aware routing.
2. `DisaggKV`, which studies distributed CXL pooling and peer-to-peer reduction for multi-node decode serving.

## Verified Artifact Outputs

### Single-node evidence

- `simulation_results.csv` is the authoritative table for the Ramulator trace-level comparisons.
- `paper_assets/data/ramulator_results.md` is the synchronized human-readable summary of those results.
- The current data supports large reductions in aggregate read and write latency counters and a strong reduction in row misses across `2K` to `128K` traces.
- Area and energy trend summaries are tracked in `paper_assets/data/inlu_overhead_comparison.json`.

### Distributed-system evidence

- `paper_assets/data/paper_metrics.json` is the authoritative source for throughput-latency, traffic, scalability, and fault-recovery comparison plots.
- `paper_assets/data/paper_metrics.json` records provenance and analytical model assumptions, so measured counters and derived curves can be audited separately.
- `results/fault_recovery_results.json` stores the detailed injected-fault run used for the recovery summary.
- The synchronized result set supports the thesis claim that `DisaggKV` keeps the `50 ms` tail-latency target until roughly `2.9K req/s`, sharply reduces host-facing traffic, and recovers within sub-second latency in the modeled setting.

### Manuscripts

- `thesis/` is the current manuscript tree aligned with the repository data.
- `thesis_cn/` is a Chinese manuscript tree that should be reviewed separately before treating it as synchronized with the English thesis.
- The standalone `pimmain` and `cxlmain` drafts have been removed; `thesis/` is the current integrated manuscript tree.

## Current Confidence Level

- The repository's data summaries, top-level README, and English thesis now tell the same story.
- The most important previously inconsistent note, `paper_assets/data/ramulator_results.md`, has been corrected.
- The project is in a good state for thesis review, advisor review, and repository walkthroughs.

## Known Follow-up Work

- Synchronize `thesis_cn/` with the revised English thesis if the Chinese manuscript will be used for submission or defense.
- Add end-to-end model quality evaluation such as perplexity or task accuracy if a stronger algorithmic-fidelity story is needed.
- Improve environment capture and artifact-version logging if the repository will be released as a public reproducibility package.
- The fixed-point iNLU path now has a lightweight attention-output quality benchmark, and `evaluate_perplexity.py` has a local smoke-test mode; a full WikiText/model run remains useful when optional dataset/model dependencies are available.
- If a future conference submission is needed, derive it from the synchronized thesis and data rather than reviving the removed standalone drafts.
