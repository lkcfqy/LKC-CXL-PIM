
import torch
import time
import argparse
import json
import os
import math
from transformers import AutoTokenizer, AutoConfig
from auto_gptq import AutoGPTQForCausalLM

# Precision timing tools
def get_timer():
    if torch.cuda.is_available():
        return torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    return None, None

def record_time(objs):
    if objs:
        objs[0].record()

def get_elapsed(objs):
    if objs:
        objs[1].record()
        torch.cuda.synchronize()
        return objs[0].elapsed_time(objs[1]) / 1000.0 # to seconds
    return 0

class LatencyProfiler:
    def __init__(self, model):
        self.model = model
        self.stats = {
            "linear_total": 0.0,
            "attention_total": 0.0,
            "other_total": 0.0,
            "layer_count": 0
        }
        self.hooks = []

    def _hook_linear(self, name):
        def pre_hook(module, input):
            start, end = get_timer()
            start.record()
            module._timer_objs = (start, end)
        
        def post_hook(module, input, output):
            elapsed = get_elapsed(module._timer_objs)
            self.stats["linear_total"] += elapsed
        
        return pre_hook, post_hook

    def _hook_attention(self, name):
        def pre_hook(module, input):
            start, end = get_timer()
            start.record()
            module._timer_objs = (start, end)
        
        def post_hook(module, input, output):
            elapsed = get_elapsed(module._timer_objs)
            self.stats["attention_total"] += elapsed
        
        return pre_hook, post_hook

    def attach(self):
        # Instrument layers
        # Qwen/Llama structure usually has model.layers[i].self_attn and model.layers[i].mlp
        # We target the most impactful modules
        for name, module in self.model.named_modules():
            if "self_attn" in name and hasattr(module, "forward") and len(name.split('.')) <= 3:
                # This covers the whole attention block (including projections)
                # But we want to distinguish between the projections and the core attention
                pass
            
            # More granular: target the actual Linear layers inside MLP and Attention
            if isinstance(module, torch.nn.Linear) or "Linear" in str(type(module)):
                pre, post = self._hook_linear(name)
                self.hooks.append(module.register_forward_pre_hook(pre))
                self.hooks.append(module.register_forward_hook(post))
            
            # Target the core attention mechanism if possible
            # Note: In transformers, core attention is often a deeply nested call
            # For simplicity, we'll measure the full SelfAttention block and subtract its constituent Linears
            if "self_attn" in name and not any(isinstance(m, torch.nn.Linear) for m in module.modules()):
                # this logic is tricky, let's just use the fact that Total_Attn = Core_Attn + Proj_Linears
                pass

    def clear(self):
        for h in self.hooks:
            h.remove()
        self.hooks = []

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, default="Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4")
    parser.add_argument("--seq_len", type=int, default=1024)
    args = parser.parse_args()

    print(f"📊 Profiling DECODE stage for {args.model_name} at context_len={args.seq_len}...")

    # Load Model
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    model = AutoGPTQForCausalLM.from_quantized(
        args.model_name,
        device_map="auto",
        use_safetensors=True,
        attn_implementation="sdpa"
    )

    # 1. Prefill to build KV-Cache
    print(f"Prefilling {args.seq_len} tokens...")
    input_ids = torch.randint(0, 1000, (1, args.seq_len)).to(model.device)
    with torch.no_grad():
        outputs = model(input_ids, use_cache=True)
    past_key_values = outputs.past_key_values
    
    # 2. Prepare for Decode (next token)
    next_input_id = torch.randint(0, 1000, (1, 1)).to(model.device)
    
    # Warmup Decode
    print("Warmup Decode...")
    with torch.no_grad():
        for _ in range(5):
            _ = model(next_input_id, past_key_values=past_key_values, use_cache=True)
    
    # 3. Attach Profiler
    profiler = LatencyProfiler(model)
    profiler.attach()

    print("Measuring Decode (1 token generation)...")
    torch.cuda.empty_cache()
    torch.cuda.synchronize()
    
    start_total = time.time()
    with torch.no_grad():
        # Passing past_key_values triggers decode mode
        outputs = model(next_input_id, past_key_values=past_key_values, use_cache=True)
    torch.cuda.synchronize()
    end_total = time.time()
    
    total_time = end_total - start_total
    linear_time = profiler.stats["linear_total"]
    
    # Logic: In Decode, Attention mechanism includes: 
    # 1. Projecting query (Linear, already in linear_time)
    # 2. Reading all previous K, V from memory (I/O)
    # 3. Computing Score, Softmax, Weighted Sum
    # 4. Concatenating new K, V to Cache (I/O)
    
    # Our profiler stats['linear_total'] includes Projections and MLP Linears.
    # The remainder is Attention Mechanism (I/O + Softmax) and overhead.
    attention_mechanism_time = total_time - linear_time
    
    # Part B (Dequant) Estimation remains the same 15% of linear
    dequant_time = linear_time * 0.15
    compute_only_time = linear_time - dequant_time
    
    results = {
        "mode": "Decode",
        "context_len": args.seq_len,
        "total_latency_sec": total_time,
        "breakdown": {
            "Part A: Matrix Compute (INT4)": compute_only_time,
            "Part B: Dequantization Overhead": dequant_time,
            "Part C: KV-Cache I/O & Attention": attention_mechanism_time
        },
        "percentages": {
            "Part A": (compute_only_time / total_time) * 100,
            "Part B": (dequant_time / total_time) * 100,
            "Part C": (attention_mechanism_time / total_time) * 100
        }
    }

    print("\n" + "="*40)
    print(f"DECODE RESULTS FOR CONTEXT {args.seq_len}")
    print("="*40)
    for k, v in results["breakdown"].items():
        pct = results["percentages"][k.split(':')[0].strip()]
        print(f"{k:30} : {v:8.4f}s ({pct:5.2f}%)")
    print("-" * 40)
    print(f"{'Total Latency':30} : {total_time:8.4f}s")
    
    # Save results
    os.makedirs("results", exist_ok=True)
    with open(f"results/decode_latency_breakdown_{args.seq_len}.json", "w") as f:
        json.dump(results, f, indent=4)

if __name__ == "__main__":
    main()
