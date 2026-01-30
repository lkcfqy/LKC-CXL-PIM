# LKC-CXL-PIM: 面向大上下文 LLM 推理的全整数存内计算架构

本项目包含**LKC-CXL-PIM (Large-KV-Cache CXL PIM)** 架构的研究代码、仿真环境及实验评估脚本。

针对大语言模型 (LLM) 在长上下文 (Long Context) 推理中面临的 KV-Cache 存储与带宽瓶颈（即 "Memory Wall"），我们提出了一种基于 **HBM3** 的**全整数 (Integer-Only) 存内计算 (PIM)** 方案。

## 🌟 核心特性 (Key Features)

本架构通过软硬协同设计，显著降低了长文本推理的延迟与能耗：

1.  **全整数架构 (Integer-Only Architecture)**
    *   **iNLU (Integer Non-Linear Unit)**: 摒弃了昂贵的 FP16 浮点单元，使用多项式拟合 (Polynomial Approximation) 和查找表 (LUT) 实现了 Softmax 和 Gelu 的全整数计算。
    *   **优势**: 面积开销降低 17%，能耗显著减少。

2.  **近存 KV 压缩 (In-Situ KV Compression)**
    *   **机制**: 在 PIM 内部直接将 FP16 的 KV-Cache 压缩为 **INT4** 格式。
    *   **效果**: 实现了 4:1 的存储密度提升，直接将内存带宽需求降低 75%。

3.  **异常值感知 (Outlier-Aware Mechanism)**
    *   **策略**: 自动检测 1% 的显著激活值 (Outliers)，并通过独立的高精度路径处理，其余 99% 数据走低精度压缩路径。
    *   **精度**: 在极高压缩比下仍能保持 >99% 的模型精度。

4.  **Ramulator2 仿真集成**
    *   基于 `Ramulator2` 开发了定制化的 C++ 控制器插件 `KVCompressionPlugin`，实现了周期精确 (Cycle-Accurate) 的性能仿真。

---

## 📂 项目结构 (Repository Structure)

```text
LKC-CXL-PIM/
├── ramulator2/                     # 修改后的 Ramulator2 仿真器核心
│   ├── src/dram_controller/impl/plugin/kv_compression.cpp  # [核心] PIM 压缩逻辑实现
│   ├── hbm3_pim_baseline.yaml      # Baseline 配置 (普通 HBM-PIM，无压缩)
│   ├── hbm3_pim_kv.yaml            # Ours 配置 (支持 KV 压缩与 iNLU)
│   ├── compose-dev.yaml            # Docker 编排文件
│   └── ...
│
├── scripts/                        # 实验与分析脚本工具箱
│   ├── reproduce_results.sh        # [一键脚本] 自动化运行完整仿真并提取数据
│   ├── profile_energy.py           # [能耗模型] 系统级能耗估算 (修正了 GQA 模型)
│   ├── plot_ramulator_results.py   # [绘图] 绘制仿真延迟与 Row Miss 对比图
│   ├── generate_paper_figures.py   # [绘图] 生成论文所需的全部 6 张关键图表
│   ├── generate_kv_trace.py        # [工具] KV Trace 生成器 (Qwen 2.5 7B 参数)
│   ├── utils.py                    # [工具] 通用配置类与计算函数
│   └── ...
│
├── traces/                         # 访存踪迹文件
│   ├── real_kv_2k.trace            # 真实捕获的 2K 上下文 Trace
│   ├── real_kv_8k.trace            # 基于真实数据外推的 8K Trace
│   └── ...
│
├── paper_assets/                   # 用于论文的最终产出
│   ├── figures/                    # 生成的高清图表 (PNG/PDF)
│   ├── data/                       # 处理后的实验数据汇总
│   └── architecture_diagrams.md    # 架构设计的 Mermaid 源码
│
└── environment.yml                 # Conda 环境配置文件
```

---

## 🛠️ 快速开始 (Quick Start)

### 0. 环境准备
本项目需要 Linux 环境，建议使用 Docker 进行 C++ 仿真，使用 Conda 进行 Python 数据分析。

### 1. 配置 Conda 环境
用于运行 Python 脚本及绘图：
```bash
conda env create -f environment.yml
conda activate lkcpim
```

### 2. 运行 Ramulator 仿真 (性能实验)
我们提供了一个自动化脚本，它会自动处理 Docker 权限、路径映射、配置修改，并依次运行 Baseline 和 Ours 的对比仿真。

**执行命令**:
```bash
# 位于项目根目录
# 脚本会运行: 2K Trace (Baseline vs Ours), 8K Trace (Baseline vs Ours)
./scripts/reproduce_results.sh
```

**输出结果**:
*   终端会显示实时进度。
*   最终数据会汇总写入 `simulation_results.csv`。

### 3. 运行能耗评估 (能耗实验)
运行基于 Qwen 2.5 7B (GQA) 架构的系统级能耗模型。

**执行命令**:
```bash
python scripts/profile_energy.py
```

**输出结果**:
*   终端打印 8K/32K/128K 上下文下的能耗对比。
*   JSON 数据保存至 `paper_assets/data/inlu_overhead_comparison.json`。

### 4. 生成论文图表
脚本会读取上述步骤生成的 CSV 和 JSON 数据，一键生成论文中所有的图表。

**执行命令**:
```bash
# 确保在 lkcpim 环境中
conda run -n lkcpim python scripts/generate_paper_figures.py
```

**输出结果**:
*   所有图表保存在 `paper_assets/figures/` 目录下。

---

## 📊 实验结果摘要

以下数据基于 **Qwen 2.5 7B** 模型配置：

### 1. 性能 (Latency)
得益于将 KV-Cache 的处理卸载到内存侧 (PIM)，大幅减少了数据搬运：

| 指标 (2K Trace) | Baseline (FP16 PIM) | Ours (Integer PIM) | 提升幅度 |
| :--- | :--- | :--- | :--- |
| **平均读取延迟** | 34.30 cycles | **0.35 cycles** | **~100x** (显著降低) |
| **平均写入延迟** | 30614 cycles | 283 cycles | **~100x** |
| **Row Buffer Miss** | 48 | 1979 | (由于 PIM 内部调度增加，但在可接受范围) |

*注：PIM-KV 的读取不经过总线，直接在 Bank 内部完成，因此延迟极低。*

### 2. 能耗 (Energy)
随着上下文长度增加，KV-Cache 的 I/O 占比越来越高，我们的压缩优势也越明显：

| 上下文长度 | 节省比例 (Saving) | 说明 |
| :--- | :--- | :--- |
| **8K** | ~8% | 权重 I/O 仍占主导 |
| **32K** | ~25% | KV I/O 占比提升 |
| **128K** | **~50%** | KV I/O 主导，压缩收益最大化 |

---

## 🔗 架构设计资料

详细的架构图源码（Mermaid 格式）位于 `paper_assets/architecture_diagrams.md`，包含：
1.  **Overall Architecture**: 整体 PIM 架构图
2.  **iNLU Pipeline**: 整数非线性单元流水线
3.  **Outlier Logic**: 异常值处理逻辑
4.  **Compression Datapath**: 压缩数据通路

---

## 📝 许可证

MIT License
