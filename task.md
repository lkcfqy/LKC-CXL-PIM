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

## 📅 阶段 4：论文与投稿 (第 8 个月)

**目标：** 投中 ISPASS 或 IEEE CAL。

### 论文撰写

- [ ] **论文框架**
  - [ ] 确定论文标题和架构名称
  - [ ] 撰写 Abstract
  - [ ] 撰写 Introduction
  - [ ] 撰写 Background & Motivation
  - [ ] 撰写 Architecture Design
  - [ ] 撰写 Evaluation
  - [ ] 撰写 Discussion (包含 CXL-PIM 扩展讨论)
  - [ ] 撰写 Conclusion

- [x] **图表制作**
  - [x] 架构总览图 (见 architecture_diagrams.md)
  - [x] iNLU 模块设计图 (见 fig8_inlu_schematic.pdf)
  - [x] Outlier-Aware Logic 示意图 (见 fig9_outlier_schematic.pdf)
  - [x] 性能对比图表 (见 figures/fig5)
  - [x] 能耗对比图表 (见 figures/fig2)

### 投稿准备

- [ ] **目标会议/期刊**
  - [ ] ISPASS 2027（首选，3-4月截稿）
  - [ ] IEEE CAL / IEEE TC（备选，快速发表）

- [ ] **投稿材料**
  - [ ] 论文终稿
  - [ ] Cover Letter
  - [ ] Supplementary Materials

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
| 阶段 4 | 第 8 月 | 🔄 进行中 | 25% |

---

**最后更新时间：** 2026-01-23

> [!TIP]
> 定期更新此文件中的复选框状态，标记完成项为 `[x]`，进行中项为 `[/]`
