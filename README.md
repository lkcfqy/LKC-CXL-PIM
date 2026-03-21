# 🚀 LKC-CXL-PIM: 基于 CXL 存内计算的长 KV 缓存 (Long KV Cache via CXL Processing-in-Memory) 🧠✨

欢迎来到 **LKC-CXL-PIM**！🎉 本仓库包含我们前沿研究项目的源代码、硬件 RTL 设计以及仿真基础设施！该项目旨在解决困扰**大型语言模型 (LLM)** 的长上下文 **KV Cache** 内存瓶颈问题。📚💥

通过结合 **CXL (Compute Express Link)** 内存扩展技术与 **PIM (存内计算, Processing-in-Memory)**，并引入我们新颖的 **iNLU** 软硬协同设计，本项目大幅降低了长上下文 LLM 的推理延迟和能耗！⚡📈

---

## ✨ 核心亮点 🌟

* 🧠 **iNLU 算法与硬件 RTL**：一种专为加速 KV Cache 检索而设计的异常值感知 (Outlier-aware) 逻辑架构，已在 SystemVerilog 中完成验证！🔍
* 💻 **定制版 Ramulator 2.0 集成**：一个完全自定义的周期级精度内存模拟器，专为 CXL-PIM 架构构建，并包含 KV 压缩插件。⚙️
* 📊 **端到端评估**：提供全面的 Python 脚本，以评估 LLM 困惑度 (Perplexity)、延迟、能耗及 iNLU 算法性能！🔬
* 📜 **论文级复现**：包含完美复现我们研究论文中 Baseline 与 PIM 对比图表所需的所有脚本和资产！🏆

---

## 📂 项目结构 🗺️

这里是代码库的快速指南：

* 📁 `ramulator2/` ⚙️: 周期级精度的内存仿真环境。
    * `src/` 🧩: DRAM 控制器与 PIM 逻辑的 C/C++ 源代码。
    * `verilog_verification/` 🛠️: 用于硬件验证的 SystemVerilog RTL 源文件（如 `inlu_core.sv`, `outlier_logic.sv`）及其 Testbench 测试平台。
* 📁 `scripts/` 🐍: 用于生成 Trace、解析仿真结果和绘制图表的自动化脚本！
    * `reproduce_results.sh` 🚀: 一键运行完整评估流水线的核心主脚本。
* 📁 `paper_assets/` 🖼️: 存储生成的评估数据 (`.csv`, `.json`) 以及用于表示 KV Cache 缩放、延迟和能耗的精美矢量图表 (`.pdf`, `.png`)。
* 📁 `logs/` 📝: 包含 Baseline 与 PIM-KV 在不同上下文长度（如 2K、8K）下的详细真实内存 Trace 日志。
* 📄 `simulation_results.csv` 📊: 实验得出的汇总结果文件。

---

## 🛠️ 系统要求 (🌟 新增补充)

在开始之前，请确保您的系统满足以下基本要求：
- **操作系统**: Linux (推荐 Ubuntu 20.04/22.04 或 CentOS) 🐧
- **包管理器**: Conda (用于快速配置 python 流水线及依赖)
- **硬件仿真环境**: 项目中提供了针对硬件验证的支持 (包含 `modelsim.do` 和 `run_modelsim`)，如需运行 `verilog_verification/` 下的 RTL 仿真，需配置 ModelSim 或其他兼容的仿真器。

---

## 🚀 快速开始 🛠️

准备好潜入 PIM 和 CXL 的世界了吗？请按照以下步骤操作！

### 1. 配置环境 🌱
我们使用 Conda 来确保所有依赖项得到完美管理！
```bash
conda env create -f environment.yml
conda activate lkc-cxl-pim
```

### 2. 生成 Trace 并进行 Profile 🏃‍♂️💨

使用我们提供的脚本来生成 LLM 内存 Trace，并评估 iNLU 算法。

```bash
python scripts/generate_llm_memory_trace.py
python scripts/iNLU_algorithm_sim.py
```

### 3. 复现论文结果 🏆

想要完全重现我们论文中的确切结果吗？只需运行主 Shell 脚本即可！
*(提示: 整个长上下文仿真和端到端评估过程可能需要一定时间，建议使用 `tmux` 或 `nohup` 在后台运行)*

```bash
./scripts/reproduce_results.sh
```

### 4. 绘制图表 🎨

一旦仿真完成，您可以生成存储在 `paper_assets/figures/` 中的精美 PDF 和 PNG 图表！

```bash
python scripts/generate_paper_figures.py
```

---

## 📖 引用我们的工作 (🌟 新增补充)

如果 LKC-CXL-PIM 帮助了您的研究或在您的项目中被使用，请考虑引用我们的论文（请在文章正式发表后完善以下内容）：

```bibtex
@inproceedings{LKC-CXL-PIM-202X,
  title={{LKC-CXL-PIM}: Long KV Cache via CXL Processing-in-Memory},
  author={你的名字 和 你的合作者们},
  booktitle={Proceedings of the XXth International Symposium on XXXX},
  year={202X}
}
```

---

*用 ❤️ 构建，旨在实现从内存架构到 LLM 效率的性能飞跃！Happy hacking!* 🎉
