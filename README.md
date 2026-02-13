# 🚀 LKC-CXL-PIM: Long KV Cache via CXL Processing-in-Memory 🧠✨

Welcome to **LKC-CXL-PIM**! 🎉 This repository contains the source code, hardware RTL, and simulation infrastructure for our cutting-edge research project! We are tackling the infamous **Large Language Model (LLM) Long KV Cache** memory bottleneck. 📚💥

By combining **CXL (Compute Express Link)** memory expansion with **PIM (Processing-in-Memory)**, and introducing our novel **iNLU** hardware-algorithm co-design, this project dramatically reduces latency and energy consumption for Long Context LLMs! ⚡📈

---

## ✨ Core Highlights 🌟

* 🧠 **iNLU Algorithm & Hardware RTL**: A specialized outlier-aware logic architecture—verified in SystemVerilog—designed to accelerate KV cache retrieval! 🔍
* 💻 **Custom Ramulator 2.0 Integration**: A fully customized, cycle-accurate memory simulator for CXL-PIM architectures, complete with KV compression plugins. ⚙️
* 📊 **End-to-End Evaluation**: Comprehensive python scripts to evaluate LLM Perplexity, Latency, Energy, and iNLU algorithm performance! 🔬
* 📜 **Paper Ready**: All scripts and assets needed to flawlessly reproduce the baseline vs. PIM figures from our research paper! 🏆

---

## 📂 Project Structure 🗺️

Here is a quick tour of our well-organized codebase:

* 📁 `ramulator2/` ⚙️: The cycle-accurate memory simulation environment.
    * `src/` 🧩: Source code for DRAM controllers and PIM logic.
    * `verilog_verification/` 🛠️: SystemVerilog RTL files (`inlu_core.sv`, `outlier_logic.sv`) and testbenches for hardware verification.
* 📁 `scripts/` 🐍: Automation scripts for trace generation, simulation parsing, and plotting!
    * `reproduce_results.sh` 🚀: The magic master script to run the evaluation pipeline.
* 📁 `paper_assets/` 🖼️: Stores generated evaluation data (`.csv`, `.json`) and beautiful vector figures (`.pdf`, `.png`) for KV cache scaling, latency, and energy.
* 📁 `logs/` 📝: Detailed real-world memory traces for Baseline and PIM-KV across different context lengths (e.g., 2K, 8K).
* 📄 `simulation_results.csv` 📊: Aggregated results output from our experiments.

---

## 🚀 Getting Started 🛠️

Ready to dive into the world of PIM and CXL? Follow these steps!

### 1. Set Up the Environment 🌱
We use Conda to ensure all dependencies are perfectly managed!
```bash
conda env create -f environment.yml
conda activate lkc-cxl-pim

```

### 2. Generate Traces & Profile 🏃‍♂️💨

Use our provided scripts to generate LLM memory traces and evaluate the iNLU algorithm.

```bash
python scripts/generate_llm_memory_trace.py
python scripts/iNLU_algorithm_sim.py

```

### 3. Reproduce Paper Results 🏆

Want to recreate the exact results from our publication? Simply run the master shell script!

```bash
./scripts/reproduce_results.sh

```

### 4. Plot Figures 🎨

Once the simulations are done, generate the beautiful PDF figures found in `paper_assets/figures/`!

```bash
python scripts/generate_paper_figures.py

```

---

*Built with ❤️ for pushing the boundaries of memory architectures and LLM efficiency! Happy hacking!* 🎉
