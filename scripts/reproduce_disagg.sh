#!/bin/bash
# reproduce_disagg.sh - Phase 5.5
# One-click script to reproduce DisaggKV evaluation results and figures.

set -e

echo "======================================================================"
echo " DisaggKV Evaluation Pipeline - Phase 5.5"
echo "======================================================================"

# 1. Setup directories
echo "[1/4] Preparing directories..."
mkdir -p paper_assets/data
mkdir -p paper_assets/figures
mkdir -p results/reproduce

# 2. Generate model data
echo "[2/4] Generating analytical model data..."
conda run -n lkcpim python scripts/generate_paper_data.py

# 3. Parse existing simulator logs (from Phase 5.3) for internal consistency
if [ -f "results/scheduler_results_comparison.json" ]; then
    echo "[3/4] Parsing Phase 5.3 scheduler logs..."
    conda run -n lkcpim python scripts/parse_network_logs.py \
        results/scheduler_results_least_loaded.json \
        results/reproduce/scheduler_metrics.csv
else
    echo "[3/4] Skipping scheduler log parsing (results/scheduler_results_comparison.json not found)."
fi

# 4. Plot final figures
echo "[4/4] Generating 'The Big Four' figures..."
conda run -n lkcpim python scripts/plot_paper_figures.py

echo "======================================================================"
echo " SUCCESS: DisaggKV figures are ready in paper_assets/figures/"
echo "======================================================================"
ls -lh paper_assets/figures/
