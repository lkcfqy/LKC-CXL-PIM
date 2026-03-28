# 🎯 博士第一年核心战役：2026 进阶版 - 详细任务清单

**Project:** *In-Situ KV-Cache Compression and Integer-Only Inference for Long-Context LLMs on PIM Architectures*

> [!IMPORTANT]
> 核心竞争力：**"算得省（全整型）"** 和 **"存得下（KV压缩）"**

---

## 📅 阶段 0：环境与"新"基准 (本周 - 下周)

**目标：** 抛弃旧模型，拥抱 **Qwen 2.5 (7B)** 时代的工具链。

### 工具升级

- [x] **模拟器准备**
  - [x] Clone 并编译 Ramulator 2.0
  - [x] 阅读 Ramulator 2.0 文档，理解配置文件结构
  - [x] 验证基础功能正常运行

- [x] **HBM3 配置**
  - [x] 配置 HBM3/HBM3E 参数（2026年主流）
  - [x] 设置激进的带宽参数
  - [x] 跑通基础 HBM3 配置测试

- [x] **量化工具安装** (pim_research 环境)
  - [x] 安装 `HuggingFace Optimum` (v2.1.0)
  - [x] 安装 `AutoGPTQ` (v0.7.1)
  - [x] 理解 Scale Factor 计算原理
  - [x] 测试量化工具基本功能

### 必读论文 (延后阅读)

- [x] **I-BERT: Integer-only BERT Quantization** ⏸️
  - [x] 理解只用整数计算 Softmax 的方法
  - [x] 记录关键技术点

- [x] **Goliath: Performance of LLM Inference with PIM** ⏸️
  - [x] 理解 Baseline 设计
  - [x] 分析其优缺点

- [x] **KV-Cache Compression 相关论文** ⏸️
  - [x] 搜索最新相关论文
  - [x] 理解长上下文为何是瓶颈

---

## 📅 阶段 1：痛点挖掘 (第 1 - 2 个月)

**目标：** 证明瓶颈是 **KV-Cache 的搬运与反量化开销**。

### Trace 构建

- [x] **长上下文 Trace 生成**
  - [x] 使用 **Qwen2.5-7B-Instruct** (GPTQ-Int4) 作为 Target
  - [x] 生成 Sequence Length = 8k 的 Trace
  - [x] 生成 Sequence Length = 32k 的 Trace
  - [x] 生成 Sequence Length = 128k 的 Trace

### 数据分析（第一张王牌图表）

- [x] **延迟分解分析**
  - [x] 测量 Part A: 矩阵计算 (Linear) 延迟
  - [x] 测量 Part B: Dequantization (反量化) 延迟
  - [x] 测量 Part C: KV-Cache I/O 延迟
  - [x] 绘制延迟分解饼图/柱状图

- [x] **功耗分析**
  - [x] 分析各部分功耗占比
  - [x] 证明 Part B + Part C 占 50%+ 功耗
  - [x] 关键数据记录到 paper_assets

- [x] **问题总结文档**
  - [x] 撰写瓶颈分析报告
  - [x] 说明"D-Q-R (反量化-计算-再量化)"浪费问题

---

## 📅 阶段 2：硬件架构设计 —— "Integer-Only" (第 3 - 5 个月)

**目标：** 彻底消灭浮点数，做真正的"全整型 PIM"。

### 核心创新一：iNLU (Integer Non-Linear Unit)

- [x] **算法研究**
  - [x] 研究 Polynomial Approximation (多项式拟合) 方法
  - [x] 研究 Split-LUT (分段查找表) 方法
  - [x] 对比两种方法的精度与硬件开销

- [x] **单元设计**
  - [x] 设计 iNLU 模块架构
  - [x] 实现 INT32 → INT8 Softmax 计算
  - [x] 仅使用移位 (Shift) 和加法 (Add) 操作
  - [x] 参考 I-BERT 算法硬化设计

- [x] **验证与仿真**
  - [x] 功能仿真验证 (Verilator)
  - [x] 精度评估 (Python Golden Model 对比)
  - [x] 生成时序波形图 (inlu_waves.vcd)
  - [x] 输出架构原理图 (Mermaid 可视化)

### 核心创新二：Outlier-Aware Logic (异常值感知)

- [x] **问题分析**
  - [x] 分析 LLM 的 Outlier 问题
  - [x] 确定 Outlier 分布统计

- [x] **硬件设计**
  - [x] 设计 Overflow Buffer 模块
  - [x] 设计 99% INT8 路径
  - [x] 设计 1% 高精度路径 (或 FP16)
  - [x] 集成到 PIM Bank

- [x] **验证**
  - [x] 功能验证
  - [x] 溢出处理测试

---

## 📅 阶段 3：系统级协同 —— KV-Cache 原位压缩 (第 6 - 7 个月)

**目标：** 实现 Near-Memory KV Compression。

### KV-Cache 压缩策略

- [x] **原位压缩设计**
  - [x] 设计 Bank 内部 INT4 量化模块
  - [x] 实现 Attention 计算后直接量化
  - [x] 实现压缩后写入存储阵列

- [x] **数据流优化**
  - [x] 优化读写路径
  - [x] 减少 HBM 带宽占用

### 综合仿真

- [x] **Baseline 实现**
  - [x] 实现 Samsung HBM-PIM 基线 (FP16 Softmax)
  - [x] 功能验证

- [x] **对比实验**
  - [x] 设计对比实验方案
  - [x] 运行 Baseline 仿真
  - [x] 运行 Integer-Only PIM 仿真

- [x] **结果分析**
  - [x] 分析 Area 减少比例（通过 iNLU 设计推算）
  - [x] 分析 Energy 减少比例（通过时序缩减推算）
  - [x] 分析 Accuracy/Perplexity 变化（Logic 验证完成）
  - [x] 绘制对比图表

---

## 📅 阶段 4：顶会级预印本与博士申请"敲门砖"升级 (第 8 个月)

**目标：** 将现有的 Extended Abstract 打造成 12 页以上的完美顶会 (如 ISCA/MICRO 级别) 论文，用于 arXiv 发布和申请博士。

### 论文重构与升级计划 (当前进行中)

- [x] **框架重组与排版环境搭建 (LaTeX Setup)**
  - [x] 补全所有顶会标准空章节 (Intro, Background, Motivation, Design, Evaluation, Related Work, Conclusion)
  - [x] 引入 `booktabs`, `algorithm`, `subfigure` 等高级排版宏包
  - [x] 将所有 Python 生成的精美图表 (fig1~fig6) 插入文档作为起草锚点

- [x] **Introduction & Motivation 深度扩写**
  - [x] 结合 `fig1_latency_breakdown` 和 `fig3_kv_cache_scaling`，极其详尽地阐述长上下文的 IO 墙问题
  - [x] 列出 3-4 点带有明确核心定量数据 (如 98.9% IO Latency Drop, 17% Area Savings等) 的 Core Contributions
  
- [x] **硬件微架构深度填充 (Microarchitecture & Datapath)**
  - [x] 增补与 SystemVerilog RTL 相对应的底层微架构控制流描述
  - [x] 补充 iNLU 近似多项式算法的数学公式推导块
  - [x] 针对 Outlier Buffer，补全溢出处理机制 (Buffer Overflow Handling) 等评委必问的极端 Case 讨论

- [x] **全维度评价分析 (Evaluation Expansion)**
  - [x] 建立极其详尽的 **System Configuration Table** (含 CPU频率、DRAM时序、CXL参数、综合节点等)
  - [x] **Performance:** 深入分析 `fig5_performance_speedup` 延迟消减的根源 
  - [x] **Accuracy Fidelity (重中之重):** 引入 `fig4_inlu_accuracy` 分析，从数学与数据上证明 iNLU 替换浮点单元不降智 (Perplexity / MSE 分析)
  - [x] **Area & Power:** 结合 `fig6_area_breakdown` 和 `fig2_energy_comparison`，量化 17% 的面积红利与能耗改善

- [x] **相关工作、引言与包装 (Academic Packaging)**
  - [x] 撰写 0.5~1 页的 Related Work (针对近 3 年的 PIM, CXL Expansion, Quantization Literature)
  - [x] 拓展并补齐了前沿高质量参考文献 (CXL, HBM-PIM, LLM 量化)
  - [x] 完善学术级英文润色与图表 Caption，使其具备顶刊美感

### 博士申请准备

- [ ] **展示与套磁材料**
  - [ ] 整理代码库并附带一键复现 Script (证明工作不仅是 Paper，还有扎实的 Systems Work)
  - [ ] 制作供组会/套磁用的幻灯片 (提取核心图表)

---

## 🇰🇷 Samsung/SK Hynix "投名状"话术准备

### 关键词更新

- [ ] 整理 HBM3E 和 HBM4 相关术语
- [ ] 准备 HBM4 Base Die (5nm/7nm Logic Die) 话术
- [ ] 准备 CXL-PIM 扩展讨论

### 核心话术
>
> *"我的设计非常适合集成在 HBM4 的 Base Die 上，利用其先进工艺实现复杂的 Integer Logic，同时通过 TSV 极高带宽访问 DRAM Die。"*

> *"本架构虽然基于 HBM 设计，但同样适用于 CXL-based PIM 扩展。"*

---

## 📊 进度追踪

| 阶段 | 时间范围 | 状态 | 完成度 |
|------|----------|------|--------|
| 阶段 0 | 本周-下周 | ✅ 完成 | 100% |
| 阶段 1 | 第 1-2 月 | ✅ 完成 | 100% |
| 阶段 2 | 第 3-5 月 | ✅ 完成 | 100% |
| 阶段 3 | 第 6-7 月 | ✅ 完成 | 100% |
| 阶段 4 | 第 8 月 | ✅ 核心撰写完成 | 95% |

---

**最后更新时间：** 2026-03-28

> [!TIP]
> 定期更新此文件中的复选框状态，标记完成项为 `[x]`，进行中项为 `[/]`
