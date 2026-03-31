# LKC-CXL-PIM & DisaggKV: Long-Context LLM Acceleration

This repository contains the hardware-software co-designed architecture and simulation infrastructure for two research papers on accelerating ultra-long context Large Language Models (LLMs) using CXL-attached Processing-in-Memory (PIM).

1.  **LKC-CXL-PIM**: Focuses on integer-only PIM acceleration of near-memory Attention (iNLU) to overcome the HBM capacity wall.
2.  **DisaggKV**: Focuses on scalable, disaggregated CXL memory pooling with P2P fabric synchronization for multi-tenant serving.

## 🚀 Quick Start: Reproduction

To reproduce all experimental results and figures for both papers, ensure you have the `lkcpim` conda environment active.

### 1. Paper 1: LKC-CXL-PIM (Single-Node Evaluation)
This executes cycle-accurate Ramulator 2.0 simulations for context lengths from 2K to 128K.
```bash
# Verify HBM3PIM trace identification (RK/RV tags)
python3 scripts/generate_llm_memory_trace.py

# Run full baseline vs. PIM-KV suite
bash scripts/reproduce_results.sh
```
Results are saved to `simulation_results.csv`.

### 2. Paper 2: DisaggKV (Multi-Node Evaluation)
This simulates a CXL 3.0 fabric with 1-16 distributed memory nodes.
```bash
# Generate multi-node scalability data points
python3 scripts/recompute_scalability_data.py

# Generate fault recovery and traffic breakdown data
python3 scripts/generate_paper_data.py

# Plot publication-quality figures (PDF/PNG)
python3 scripts/plot_paper_figures.py
```
Figures are saved to `paper_assets/figures/`.

## 📂 Project Structure

- `ramulator2/`: Heavily modified Ramulator 2.0 with HBM3PIM and CXL protocol support.
- `scripts/`: Implementation of iNLU Golden Models, CXL Fabric Simulators, and Trace Generators.
- `paper_assets/`: Data reports (`synthesis_summary.rpt`) and generated figures.
- `traces/`: Sample LLM memory access traces (RK/RV/WR format).
- `results/`: Raw JSON outputs from distributed simulators.

## 🛠 Hardware Verification
RTL modules for the **Integer Non-Linear Unit (iNLU)** and **Outlier-Aware Logic** are located in:
- `ramulator2/src/dram/impl/HBM3PIM.cpp` (Sim model)
- `ramulator2/verilog_verification/` (RTL source & testbenches)

## 📄 Manuscripts
- `pimmain.tex`: *Long KV Cache via CXL Processing-in-Memory*
- `cxlmain.tex`: *Scalable and Disaggregated CXL-PIM Pooling for Multi-Tenant LLM Serving*

---
**Contact:** Kaichen Li (lkcfqy@gmail.com)
