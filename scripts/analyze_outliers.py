
import torch
import numpy as np
import matplotlib.pyplot as plt
from transformers import AutoTokenizer
from auto_gptq import AutoGPTQForCausalLM
import os

# 配置
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
SAVE_DIR = "paper_assets/data"
PLOT_DIR = "paper_assets/notes"

def analyze_outliers():
    print(f"🚀 正在加载模型: {MODEL_NAME} ...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoGPTQForCausalLM.from_quantized(
        MODEL_NAME,
        device_map="auto",
        use_safetensors=True,
        attn_implementation="sdpa"
    )

    # 测试输入（长上下文）
    text = "The quick brown fox jumps over the lazy dog. " * 100 
    inputs = tokenizer(text, return_tensors="pt").to(DEVICE)
    
    outlier_stats = []

    def hook_fn(name):
        def hook(module, input, output):
            # 获取激活值 (Hidden States)
            # shape: [batch, seq_len, hidden_size]
            data = output[0] if isinstance(output, tuple) else output
            data_flat = data.detach().cpu().numpy().flatten()
            
            # 统计指标
            mean = np.mean(data_flat)
            std = np.std(data_flat)
            max_val = np.max(np.abs(data_flat))
            
            # 定义异常值：超过 6 倍标准差的值
            threshold = 6 * std
            outliers = data_flat[np.abs(data_flat) > threshold]
            outlier_ratio = len(outliers) / len(data_flat) * 100
            
            outlier_stats.append({
                "layer": name,
                "mean": float(mean),
                "std": float(std),
                "max": float(max_val),
                "outlier_ratio_6sigma": float(outlier_ratio)
            })
            
            # 仅在中间层绘制直方图
            if "layers.14" in name:
                plt.figure(figsize=(10, 6))
                plt.hist(data_flat, bins=100, color='skyblue', edgecolor='black', alpha=0.7)
                plt.axvline(threshold, color='red', linestyle='--', label='6-Sigma Threshold')
                plt.axvline(-threshold, color='red', linestyle='--')
                plt.yscale('log')
                plt.title(f"Activation Distribution - {name} (Log Scale)")
                plt.xlabel("Value")
                plt.ylabel("Frequency")
                plt.legend()
                plt.grid(True, which="both", ls="-", alpha=0.3)
                plt.savefig(f"{PLOT_DIR}/outlier_distribution_layer14.png")
                print(f"✅ 已保存层 14 分布图至 {PLOT_DIR}")

        return hook

    # 注册钩子
    print("Hooking layers...")
    hooks = []
    for name, module in model.named_modules():
        if "mlp.down_proj" in name or "self_attn.o_proj" in name: # 重点关注线性层输出
            hooks.append(module.register_forward_hook(hook_fn(name)))

    # 运行推理
    print("Running inference...")
    with torch.no_grad():
        model(**inputs)

    # 移除钩子
    for h in hooks:
        h.remove()

    # 保存统计数据
    import json
    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(f"{SAVE_DIR}/outlier_statistics.json", "w") as f:
        json.dump(outlier_stats, f, indent=4)
    
    print(f"✅ 异常值统计已保存至 {SAVE_DIR}/outlier_statistics.json")

    # 打印总结
    avg_ratio = np.mean([s['outlier_ratio_6sigma'] for s in outlier_stats])
    max_ratio = np.max([s['outlier_ratio_6sigma'] for s in outlier_stats])
    print(f"\n--- 异常值分析总结 ---")
    print(f"平均异常值比例 (>6σ): {avg_ratio:.4f}%")
    print(f"最大层异常值比例: {max_ratio:.4f}%")
    print(f"建议溢出缓冲区容量: {max_ratio * 1.5:.2f}% (约为总容量的 0.1% - 1%)")

if __name__ == "__main__":
    analyze_outliers()
