# LKC-CXL-PIM

面向长上下文大模型 KV Cache 内存墙的 CXL 近内存计算研究项目。仓库围绕 `LKC-CXL-PIM` 和 `DisaggKV` 两条线索展开：前者研究把 KV Cache 访问与规约尽量推近内存侧，后者研究在分布式推理中减少 KV 迁移与恢复开销。

## 当前状态

这是一个论文级研究仓库，包含论文 LaTeX 源码、仿真脚本、结果表、Ramulator2 相关配置、trace、以及一组用于说明 PIM 控制路径的 RTL 原型文件。当前主线以英文论文目录 `thesis/` 为准，`thesis_cn/` 保留中文版本和备份材料。

需要注意：仓库中的 RTL 是架构验证和控制逻辑原型，不是完整可流片 CXL endpoint；性能与能耗结论来自脚本化建模和仿真，不应解读为真实芯片测量。

## 主要内容

- `thesis/`：英文论文源码和当前主版本 PDF。
- `thesis_cn/`：中文论文材料。
- `scripts/`：项目校验、实验复现和结果生成脚本。
- `results/`：整理后的实验结果。
- `ramulator2/`：内存系统模拟、验证脚本和相关 RTL 原型。
- `traces/`：用于仿真和论文实验的 trace 数据。

## 关键结果摘要

仓库当前材料中记录的核心结论包括：

- PIM-KV 读路径在论文设定下把 128K 长上下文读延迟从约 `77.90M` cycles 降到约 `0.80M` cycles。
- 不同上下文长度下，PIM-KV 读延迟改善约为 `91.5x` 到 `99.4x`。
- iNLU 场景的能耗节省在已记录实验中约为 `8.3%`、`24.9%`、`50.0%`。
- DisaggKV 将每百万 decoded tokens 的 KV 迁移量从约 `3.624 GB` 降到约 `0.282 GB`。
- 注意力质量校验记录中，p05 cosine 约为 `0.999921`。

这些数字应与仓库内脚本、表格和论文上下文一起阅读。

## 快速验证

```bash
conda run -n lkcpim python scripts/validate_project.py
```

如需同时检查 LaTeX 构建：

```bash
conda run -n lkcpim python scripts/validate_project.py --latex
```

更多复现实验入口请从 `scripts/` 和论文中的实验说明开始。

## 许可证

当前仓库未包含独立 `LICENSE` 文件。如需公开复用、引用代码或分发实验材料，请先补充明确的许可证与引用说明。
