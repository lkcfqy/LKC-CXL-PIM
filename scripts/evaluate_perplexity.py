#!/usr/bin/env python3
"""
evaluate_perplexity.py - Evaluate Model Perplexity on WikiText-2

This script evaluates the perplexity of quantized models to verify
accuracy loss is within acceptable bounds (< 0.5% target).

Usage:
    python evaluate_perplexity.py --model Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4

Output: paper_assets/data/perplexity_results.json
"""

import os
import json
import argparse
import torch
from tqdm import tqdm

def evaluate_perplexity(model, tokenizer, dataset, max_length=2048, stride=512):
    """
    Evaluate perplexity on a dataset using sliding window.
    
    Following the standard PPL calculation from Hugging Face docs.
    """
    model.eval()
    device = next(model.parameters()).device
    
    encodings = tokenizer("\n\n".join(dataset["text"]), return_tensors="pt")
    seq_len = encodings.input_ids.size(1)
    
    nlls = []
    prev_end_loc = 0
    
    for begin_loc in tqdm(range(0, seq_len, stride), desc="Evaluating PPL"):
        end_loc = min(begin_loc + max_length, seq_len)
        trg_len = end_loc - prev_end_loc
        
        input_ids = encodings.input_ids[:, begin_loc:end_loc].to(device)
        target_ids = input_ids.clone()
        target_ids[:, :-trg_len] = -100
        
        with torch.no_grad():
            outputs = model(input_ids, labels=target_ids)
            neg_log_likelihood = outputs.loss
        
        nlls.append(neg_log_likelihood * trg_len)
        prev_end_loc = end_loc
        
        if end_loc >= seq_len:
            break
    
    ppl = torch.exp(torch.stack(nlls).sum() / prev_end_loc)
    return ppl.item()


def main():
    parser = argparse.ArgumentParser(description="Evaluate model perplexity")
    parser.add_argument("--model", type=str, default="Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4")
    parser.add_argument("--max_length", type=int, default=2048)
    parser.add_argument("--stride", type=int, default=512)
    parser.add_argument("--num_samples", type=int, default=None, help="Number of segments to evaluate (for speed)")
    parser.add_argument("--output", type=str, default="paper_assets/data/perplexity_results.json")
    args = parser.parse_args()
    
    print("=" * 60)
    print("Perplexity Evaluation")
    print("=" * 60)
    print(f"Model: {args.model}")
    print(f"Max Length: {args.max_length}")
    
    # Load dataset
    print("\n[1/3] Loading WikiText-2 dataset...")
    from datasets import load_dataset
    dataset = load_dataset("wikitext", "wikitext-2-raw-v1", split="test")
    
    # Filter dataset if num_samples is specified
    if args.num_samples:
        dataset = dataset.select(range(min(args.num_samples, len(dataset))))
        print(f"  Using subset of {len(dataset)} segments for speed.")
    
    # Load tokenizer
    print("[2/3] Loading tokenizer and model...")
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    
    # Load model
    try:
        from auto_gptq import AutoGPTQForCausalLM
        model = AutoGPTQForCausalLM.from_quantized(
            args.model,
            device_map="auto",
            use_safetensors=True,
            trust_remote_code=True
        )
        model_type = "GPTQ-Int4"
    except:
        from transformers import AutoModelForCausalLM
        model = AutoModelForCausalLM.from_pretrained(
            args.model,
            device_map="auto",
            torch_dtype=torch.float16,
            trust_remote_code=True
        )
        model_type = "FP16"
    
    # Evaluate
    print("[3/3] Evaluating perplexity...")
    ppl = evaluate_perplexity(model, tokenizer, dataset, args.max_length, args.stride)
    
    print("\n" + "=" * 60)
    print(f"Perplexity: {ppl:.4f}")
    print("=" * 60)
    
    # Reference values (from literature)
    # Qwen2.5-7B FP16: ~5.5-6.0 PPL on WikiText-2
    # Qwen2.5-7B INT4: ~5.7-6.2 PPL (expected <5% increase)
    
    results = {
        "model": args.model,
        "model_type": model_type,
        "dataset": "wikitext-2-raw-v1",
        "max_length": args.max_length,
        "perplexity": ppl,
        "notes": "Lower is better. INT4 quantization typically adds <5% PPL increase."
    }
    
    # Save
    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to {args.output}")
    
    # Quick check
    if ppl < 10:
        print("📊 Perplexity is within expected range for 7B models.")
    else:
        print("⚠️  Perplexity seems high. Check model loading.")


if __name__ == "__main__":
    main()
