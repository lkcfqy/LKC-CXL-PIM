# LKC-CXL-PIM 与 DisaggKV

最后更新：2026-05-18

本项目研究长上下文大语言模型推理中的 KV cache memory wall，重点关注 decode 阶段反复访问历史 Key/Value 状态时产生的内存容量、带宽和跨设备数据移动压力。项目包含两个相关 artifact：

1. `LKC-CXL-PIM`：面向单个 CXL-attached HBM endpoint 的整数化近内存注意力架构。
2. `DisaggKV`：面向 CXL memory pool 的多节点 KV cache 放置与 peer-to-peer softmax reduction 框架。

当前与数据、图表和验证脚本同步的主论文是英文版 `thesis/`。`thesis_cn/` 保留中文稿件树作为参考和备份，但当前主线以英文版为准。

## 项目状态

- 英文最终论文：`thesis/main.pdf`
- 英文论文源码：`thesis/main.tex` 与 `thesis/chapters/`
- 图表与论文数据：`paper_assets/`
- 分布式仿真结果：`results/`
- KV trace 与多租户 trace：`traces/`
- 修改版 Ramulator 2.0 与 RTL 支撑文件：`ramulator2/`
- 项目自检入口：`scripts/validate_project.py`

本项目已经清理掉 LaTeX 中间文件、Python 缓存、临时 build 目录和旧的独立草稿。最终 PDF、源码、实验数据和可复现脚本被保留。

## 核心结果

以下数字来自项目内仿真、综合代理估计和论文数据文件。它们是 artifact 级建模结果，不是已流片芯片或生产 CXL 集群的实测结果。

- 单节点 Ramulator trace 覆盖 `2K` 到 `128K` context length。相对 host-aggregated baseline，`PIM-KV` 在读延迟计数上降低约 `91.5x` 到 `99.4x`，row misses 减少约 `98.5%` 到 `98.7%`。来源：`simulation_results.csv`、`paper_assets/data/ramulator_results.md`。
- 128K-token 单 endpoint 结果中，LKC-CXL-PIM 将 read latency 从 `77.90M cycles` 降到 `0.80M cycles`，整体 logic-die area 归一化值从 `1.00` 降到 `0.83`。
- iNLU 相关能耗代理结果显示，在 `8K`、`32K`、`128K` 上分别节省约 `8.3%`、`24.9%`、`50.0%`。来源：`paper_assets/data/inlu_overhead_comparison.json`。
- 分布式仿真中，DisaggKV 在约 `2.86K req/s` 前保持低于 `50 ms` tail-latency 目标；每 `1M` decoded tokens 的 host-facing traffic 从 `3.624 GB` 降到 `0.282 GB`。
- fault injection 模型中，PIM XOR parity 路径的 p95 recovery latency 为 `416.384 ms`。来源：`paper_assets/data/paper_metrics.json`、`results/fault_recovery_results.json`。
- fixed-point iNLU attention-quality benchmark 中，最差序列长度下的 output-vector cosine p05 为 `0.999921`，relative L2 p95 最大值为 `1.96%`。来源：`paper_assets/data/attention_quality_metrics.json`。

## 研究贡献

- 以 KV cache 为中心重新组织 long-context decode 数据路径，减少历史 K/V state 回到 host-facing path 的次数。
- 在 CXL-attached HBM endpoint 中引入整数化 iNLU，使 softmax exponential 尽量留在 fixed-point/integer datapath。
- 使用 outlier-aware logic 将常见值保留在 INT8 主路径，并将少量高幅值激活送入 overflow route。
- 在 CXL memory pool 中区分 shared prefix pages 与 private continuation pages，并通过 endpoint-side peer-to-peer reduction 交换 softmax 所需的 global max 和 global sum。
- 提供从 trace generation、Ramulator timing、CXL fabric event model、fault model、attention-quality check 到论文图表的数据链路。

## RTL 支撑范围

项目包含关键模块级 SystemVerilog/Verilog RTL 支撑文件，主要位于：

- `ramulator2/verilog_verification/sources/inlu_core.sv`
- `ramulator2/verilog_verification/sources/outlier_logic.sv`
- `ramulator2/verilog_verification/sources/distributed_reduce.sv`
- `ramulator2/verilog_verification/sources/async_fifo.sv`
- `ramulator2/verilog_verification/sources/*_tb.sv`

这些文件覆盖 iNLU、outlier-aware logic、distributed reduction controller、boundary FIFO 和相关 testbench。准确表述是：

> 本项目实现并验证了关键数据通路和同步模块的 RTL 原型，但尚未完成整个 CXL-PIM endpoint 的端到端 full-system RTL 实现。

也就是说，目前还没有完整串起 `CXL descriptor parser -> KV page walker -> HBM/PIM command path -> INT8 MAC/outlier path -> iNLU softmax -> value accumulation -> CXL response` 的完整 endpoint RTL。

## 环境准备

推荐使用项目 Conda 环境：

```bash
conda activate lkcpim
```

或者直接通过：

```bash
conda run -n lkcpim python scripts/validate_project.py
```

Ramulator 复现实验依赖 Docker Compose。项目中的 `ramulator2/ramulator2` 是 Linux binary；在 macOS 上不要直接执行该 binary，应通过 `scripts/reproduce_results.sh` 中的 Docker 路径运行。

## 快速验证

只检查项目数据、脚本、仿真自测和 perplexity smoke test：

```bash
conda run -n lkcpim python scripts/validate_project.py
```

同时检查英文和中文 LaTeX 构建：

```bash
conda run -n lkcpim python scripts/validate_project.py --latex
```

单独构建英文最终论文：

```bash
cd thesis
latexmk -xelatex -interaction=nonstopmode -halt-on-error main.tex
```

当前英文 PDF 为 `49` 页，最终文件位于 `thesis/main.pdf`。

## 结果复现

### 单节点 LKC-CXL-PIM

生成 KV trace 并运行 Ramulator baseline vs. `PIM-KV` 对比：

```bash
python scripts/generate_llm_memory_trace.py
bash scripts/reproduce_results.sh
```

主要输出：

- `simulation_results.csv`
- `logs/*.log`

注意：`logs/` 是生成目录，已在 `.gitignore` 中忽略。重新运行脚本时会自动创建。

### 多节点 DisaggKV 与论文图表

重新生成分布式仿真指标、iNLU 精度数据、attention-quality 数据和论文图表：

```bash
python scripts/recompute_scalability_data.py
python scripts/generate_paper_data.py
python scripts/iNLU_algorithm_sim.py
python scripts/evaluate_attention_quality.py
python scripts/generate_paper_figures.py
python scripts/plot_paper_figures.py
python scripts/plot_ramulator_results.py
python scripts/generate_schematic_figures.py
```

主要输出：

- `paper_assets/data/paper_metrics.json`
- `paper_assets/data/inlu_accuracy_metrics.json`
- `paper_assets/data/attention_quality_metrics.json`
- `paper_assets/figures/*.pdf`
- `paper_assets/figures/*.png`
- `results/*.json`

`paper_assets/data/paper_metrics.json` 内含 `_provenance` 字段，用于追踪图表对应的原始文件和分析假设。

### 可选 Perplexity 检查

本地 smoke test 不需要下载模型：

```bash
python scripts/evaluate_perplexity.py --synthetic-smoke --output /tmp/lkc_perplexity_smoke.json
```

真实 WikiText/model 评估需要额外安装 `datasets`，并显式选择 `--loader fp16` 或 `--loader gptq`。GPTQ 路径还需要 `auto_gptq`。

## 目录说明

- `thesis/`：英文论文源码和最终 PDF，当前主线 artifact。
- `thesis_cn/`：中文稿件树，保留作参考/备份。
- `scripts/`：trace 生成、仿真调度、数据汇总、图表生成、验证脚本。
- `paper_assets/data/`：论文数据摘要、指标 JSON、数据来源说明。
- `paper_assets/figures/`：论文图表 PDF/PNG 和部分 schematic source。
- `paper_assets/notes/`：补充说明、验证截图或中间分析材料。
- `results/`：分布式仿真与 fault recovery 的 JSON 输出。
- `traces/`：KV cache trace 和 multi-tenant trace。该目录较大，是复现实验关键输入。
- `ramulator2/`：修改版 Ramulator 2.0、配置文件、可执行入口和 Verilog verification collateral。
- `simulation_results.csv`：单节点 trace-level counters。
- `environment.yml`：Conda 环境配置。

## 数据与版本注意事项

- `simulation_results.csv` 保存的是 trace-level counters，不是归一化 per-access latency。
- `paper_assets/data/README.md` 记录主要数据文件对应的图表和论文位置。
- `traces/` 体积较大，但不建议删除；缺失后需要重新生成或重新下载/拷贝。
- `ramulator2/build/`、LaTeX 中间文件、Python `__pycache__/`、`logs/`、`build/` 都属于可再生成内容。
- 旧的独立 `pimmain.*` 和 `cxlmain.*` 草稿已移除，当前论文合并在 `thesis/`。

## 联系方式

Kaichen Li (`lkcfqy@gmail.com`)
