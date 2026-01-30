
import pandas as pd
import json
import os

# Energy Constants (Industry averages/Literature data for 2024-2025 HBM3 + PIM)
# pJ = picoJoules
ENERGY_HBM_READ_PER_BYTE = 56.0  # ~7 pJ/bit
ENERGY_INT4_COMPUTE_PER_OP = 0.1  # INT4 Add/Mul in PIM logic layer

# iNLU Specific Energy (pJ per Attention Score element)
# Reference: I-BERT (ICML'21) & General PIM arch papers
ENERGY_FP16_SOFTMAX = 25.0    # Floating point unit involves complex exp/div
ENERGY_INT_POLY = 2.5        # Shift-Add based (approx 10x less than FP16)
ENERGY_INT_LUT = 4.0        # Memory (SRAM) access based for table lookup

# Qwen 2.5 7B Model Stats
NUM_LAYERS = 28
HIDDEN_SIZE = 3584
INTERMEDIATE_SIZE = 18944 
NUM_HEADS = 28
HEAD_DIM = HIDDEN_SIZE // NUM_HEADS

def calculate_system_energy(context_len):
    # --- Common Constants ---
    total_params = 7.61e9 
    weight_bytes = total_params * 0.5 # INT4 weights (always compressed in storage)
    
    # GQA: 4 KV heads, 28 Q heads.
    # Baseline reads KV as FP16 (2 bytes)
    # Ours reads KV as INT4 (0.5 bytes) -> 4x reduction
    num_elements_kv = context_len * NUM_LAYERS * 2 * (4 * HEAD_DIM) 
    
    # --- 1. Baseline System (HBM-PIM but FP16 datapath) ---
    # Cost: Weights I/O + Uncompressed KV I/O + Dequant overhead + FP16 Softmax
    
    e_base_io_weights = weight_bytes * ENERGY_HBM_READ_PER_BYTE
    e_base_io_kv = (num_elements_kv * 2) * ENERGY_HBM_READ_PER_BYTE # FP16 = 2 bytes
    
    # Compute overheads (simplified)
    # Dequantization energy is significant in Baseline
    e_base_compute = (4 * HIDDEN_SIZE**2 * 2) * ENERGY_INT4_COMPUTE_PER_OP # Matrix
    e_base_dequant = e_base_compute * 0.20 # Assume 20% overhead for dequant
    e_base_softmax = (NUM_LAYERS * NUM_HEADS * context_len) * ENERGY_FP16_SOFTMAX
    
    total_baseline = e_base_io_weights + e_base_io_kv + e_base_compute + e_base_dequant + e_base_softmax

    # --- 2. Ours (Integer-Only PIM) ---
    # Cost: Weights I/O + Compressed KV I/O + No Dequant + Integer Softmax
    
    e_ours_io_weights = weight_bytes * ENERGY_HBM_READ_PER_BYTE
    e_ours_io_kv = (num_elements_kv * 0.5) * ENERGY_HBM_READ_PER_BYTE # INT4 = 0.5 bytes
    
    e_ours_compute = e_base_compute # Matrix compute is same (INT4 MACs)
    e_ours_dequant = 0 # Eliminated!
    e_ours_softmax = (NUM_LAYERS * NUM_HEADS * context_len) * ENERGY_INT_POLY
    
    total_ours = e_ours_io_weights + e_ours_io_kv + e_ours_compute + e_ours_dequant + e_ours_softmax
    
    return {
        "context_len": context_len,
        "baseline_pj": total_baseline,
        "ours_pj": total_ours,
        "saving_pct": (1 - total_ours/total_baseline) * 100
    }

def main():
    contexts = [8192, 32768, 131072]
    results = []
    
    print("\n" + "="*80)
    print("SYSTEM ENERGY CONSUMPTION COMPARISON (picoJoules per token)")
    print("="*80)
    print(f"{'Context':<10} | {'Baseline (nJ)':<15} | {'Ours (nJ)':<15} | {'Saving %':<10} | {'Normalized (Ours)'}")
    print("-" * 80)
    
    for c in contexts:
        res = calculate_system_energy(c)
        results.append(res)
        
        base_nj = res['baseline_pj'] / 1000.0
        ours_nj = res['ours_pj'] / 1000.0
        norm = res['ours_pj'] / res['baseline_pj']
        
        print(f"{c:<10} | {base_nj:15.2f} | {ours_nj:15.2f} | {res['saving_pct']:8.2f}% | {norm:.2f}x")

    # Save to paper_assets
    os.makedirs("paper_assets/data", exist_ok=True)
    # df.to_csv(...) <--- Removed dependency
    
    with open("paper_assets/data/inlu_overhead_comparison.json", "w") as f:
        json.dump(results, f, indent=4)
        
    print(f"\n✅ iNLU 硬件开销对比数据已保存至 paper_assets/data/inlu_overhead_comparison.json")

if __name__ == "__main__":
    main()
