# Ramulator Simulation Results / Ramulator 仿真结果

# Updated / 更新时间: 2026-04-22

## Scope / 范围

- Source / 数据来源: `simulation_results.csv`
- Trace set / 访存踪迹: `real_kv_2k.trace`, `real_kv_8k.trace`, `real_kv_32k.trace`, `real_kv_64k.trace`, `real_kv_128k.trace`
- Model / 模型: Qwen2.5-7B-class KV-cache workload
- Memory / 内存配置: HBM3-style Ramulator setup used in the thesis experiments
- Note / 说明: The latency numbers below are aggregate trace-level counters from Ramulator. Speedups are computed by comparing the baseline and PIM-KV runs of the same trace.
  下表延迟为 Ramulator 输出的踪迹级累计计数；加速比按同一踪迹下 Baseline 与 PIM-KV 的结果直接比较。

## Trace-Level Results / 各踪迹结果

| Trace | Metric / 指标 | Baseline | PIM-KV | Improvement |
|------|------|------:|------:|------:|
| 2K | Read latency | 10,370,948 | 109,992 | 94.29x lower |
| 2K | Write latency | 4,521,722 | 40,041 | 112.93x lower |
| 2K | Row misses | 58,431 | 870 | 98.51% fewer |
| 8K | Read latency | 10,767,461 | 117,633 | 91.53x lower |
| 8K | Write latency | 4,523,263 | 50,344 | 89.85x lower |
| 8K | Row misses | 80,483 | 1,195 | 98.52% fewer |
| 32K | Read latency | 19,486,076 | 196,089 | 99.37x lower |
| 32K | Write latency | 8,264,642 | 110,489 | 74.80x lower |
| 32K | Row misses | 71,289 | 968 | 98.64% fewer |
| 64K | Read latency | 38,975,270 | 396,455 | 98.31x lower |
| 64K | Write latency | 16,433,770 | 266,064 | 61.77x lower |
| 64K | Row misses | 143,745 | 1,913 | 98.67% fewer |
| 128K | Read latency | 77,895,197 | 795,079 | 97.97x lower |
| 128K | Write latency | 32,743,881 | 352,069 | 93.00x lower |
| 128K | Row misses | 288,535 | 3,700 | 98.72% fewer |

## Key Observations / 关键结论

1. Read-side memory cost drops by roughly two orders of magnitude across all tested context lengths.
   在所有测试上下文长度下，读路径访存代价都下降了接近两个数量级。

2. Write-side latency is also reduced substantially, with speedups ranging from about 61.8x to 112.9x depending on trace length.
   写路径延迟同样显著下降，不同踪迹下加速比约为 61.8x 到 112.9x。

3. The updated data shows that PIM-KV reduces row misses rather than increasing them. This is consistent with the thesis claim that in-memory KV handling improves locality and avoids repeated host-driven row activations.
   更新后的数据表明，PIM-KV 会减少而不是增加 row misses。这与论文中的结论一致，即将 KV 处理下沉到内存内部后，可以改善局部性并减少主机侧反复触发的行激活。

4. The benefit remains stable as the trace grows from 2K to 128K, which supports the thesis argument that the architecture is especially attractive for long-context decode workloads.
   从 2K 到 128K 的踪迹扩展过程中，收益保持稳定，这也支持了论文中“该体系结构尤其适合长上下文 decode 负载”的论点。
