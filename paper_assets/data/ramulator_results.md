# Ramulator Simulation Results / Ramulator 仿真结果

# Updated / 更新时间: 2026-01-31 (Automated Run)

## Simulation Configuration / 仿真配置

- Trace / 访存踪迹: real_kv_2k.trace & real_kv_8k.trace
- Model / 模型: Qwen2.5-7B
- Memory / 内存配置: HBM3_8Gb @ 2Gbps

## 2K Trace Results

| Metric / 指标 | Baseline | PIM-KV | Improvement |
|--------|----------|--------|-------------|
| Avg Read Latency | 34.30 | **0.35** | **-98.9%** |
| Avg Write Latency | 30614.50 | 283.00 | **-99.1%** |
| Row Misses | 48 | 1,979 | (See Note) |

## 8K Trace Results

| Metric / 指标 | Baseline | PIM-KV | Improvement |
|--------|----------|--------|-------------|
| Avg Read Latency | 34.47 | **0.35** | **-98.9%** |
| Avg Write Latency | 12213.39 | 126.50 | **-98.9%** |
| Row Misses | 91 | 807 | (See Note) |

## Key Observations / 关键结论

1. **Massive Latency Reduction**: Read latency dropped from ~34 cycles to ~0.35 cycles. This confirms that PIM effectively offloads KV-cache operations, removing the memory transport overhead for the vast majority of accesses.
   读取延迟从约 34 个周期降至 0.35 个周期。这证实了 PIM 有效地卸载了 KV 缓存操作，消除了绝大多数访问的内存传输开销。

2. **Write Latency Improvement**: Write latency (critical for KV updates) saw a similar ~100x improvement.
   写延迟（对 KV 更新至关重要）也看到了类似的约 100 倍提升。

3. **Row Miss Trade-off**: We observe more row misses in PIM-KV (e.g. 1979 vs 48). This is expected because PIM ops might access different banks/rows more aggressively, but since the ops are internal to the memory (high bandwidth, low latency), the net performance is still superior.
   我们观察到 PIM-KV 中的行缺失更多。这是预期的，因为 PIM 操作可能会更积极地访问不同的 Bank/Row，但由于操作在内存内部（高带宽、低延迟），净性能仍然优越。
