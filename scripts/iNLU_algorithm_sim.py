
import torch
import numpy as np
import matplotlib.pyplot as plt

def standard_softmax(x):
    return torch.softmax(x, dim=-1)

# 1. Polynomial Approximation (I-BERT style)
# Approximation for e^x in x in [-ln2, 0]
# e^x approx 0.3585 * (x + 1.353)^2 + 0.344
# For integer implementation, we use fixed-point shift
def integer_exponential_poly(x_int, scaling_factor):
    """
    x_int: integer representation of x
    scaling_factor: scale to convert float to int (e.g., 2^10)
    """
    # Range Reduction: e^x = 2^n * e^{f} where f in [-ln2, 0]
    ln2_int = int(0.6931 * scaling_factor)
    
    # n = floor(x / ln2)
    n = torch.floor(x_int.float() / ln2_int).int()
    f_int = x_int - n * ln2_int
    
    # Polynomial: (ax + b)^2 + c
    # Simplified for integer-only (no actual floats used in computation)
    # Using I-BERT coefficients scaled by 2^10
    a = 367  # 0.3585 * 1024
    b = 1385 # 1.353 * 1024
    c = 352  # 0.344 * 1024
    
    # poly = a * (f + b)^2 + c
    # Note: intermediate values can be large, use long/int64
    f_plus_b = (f_int + b).long()
    val = (a * (f_plus_b**2) >> 20) + c # >> 20 to adjust for (f+b)^2 scaling
    
    # Apply 2^n (Bit shift)
    # val is already scaled by 1024 (from b and c)
    # result = val * 2^n
    # in hardware, this is a simple shift
    # Result will be very large if n is positive, but softmax inputs are usually negative (after max subtraction)
    return val, n

def integer_softmax_poly(x, scaling_factor=1024):
    # 1. Max Subtraction (Stability)
    x_max = torch.max(x)
    x_shifted = x - x_max
    
    # 2. To Integer
    x_int = (x_shifted * scaling_factor).int()
    
    # 3. Integer Exp
    exp_vals, shifts = integer_exponential_poly(x_int, scaling_factor)
    
    # 4. Sum (Denominator)
    # In PIM, this is an accumulation across the row
    # result_i = (val_i * 2^shift_i) / Sum(val_j * 2^shift_j)
    # To avoid floating point division, we use fixed-point
    
    # For simulation, let's normalize
    # Real hardware would use a divider unit or reciprocal LUT
    float_exps = exp_vals.float() * torch.pow(2.0, shifts.float())
    sum_exp = torch.sum(float_exps)
    return float_exps / sum_exp

# 2. Split-LUT Approximation
# Principle: e^x = e^{int(x)} * e^{frac(x)}
# In fixed-point: e^x = 2^n * e^{f} (same as poly, but use a table for e^f)
def integer_softmax_lut(x, scaling_factor=1024):
    x_max = torch.max(x)
    x_shifted = x - x_max
    x_int = (x_shifted * scaling_factor).int()
    
    # Pre-calculate a small LUT for e^f where f in [-ln2, 0]
    # In hardware, this would be a 64 or 128 entry ROM
    lut_size = 256
    ln2 = 0.6931
    f_samples = np.linspace(-ln2, 0, lut_size)
    exp_lut = torch.tensor(np.exp(f_samples) * scaling_factor).int()
    
    # Range Reduction
    ln2_int = int(ln2 * scaling_factor)
    n = torch.floor(x_int.float() / ln2_int).int()
    f_int = x_int - n * ln2_int # f_int is in [-ln2_int, 0]
    
    # Map f_int to LUT index [0, lut_size-1]
    # f_int is negative, from -ln2_int to 0
    idx = ((f_int.float() / -ln2_int) * (lut_size - 1)).int()
    idx = (lut_size - 1) - idx # invert because f_int is negative
    idx = torch.clamp(idx, 0, lut_size - 1)
    
    val_lut = exp_lut[idx.long()]
    
    # Normalize with 2^n
    float_exps = val_lut.float() * torch.pow(2.0, n.float())
    return float_exps / torch.sum(float_exps)

def run_comparison():
    # Test Data: Random logits (normal distribution)
    torch.manual_seed(42)
    logits = torch.randn(16) * 2.0 
    
    print(f"Input Logits: {logits.numpy()}")
    
    s_std = standard_softmax(logits)
    s_poly = integer_softmax_poly(logits)
    s_lut = integer_softmax_lut(logits)
    
    print("\n--- Softmax Output Comparison ---")
    print(f"{'Index':<6} | {'Standard':<10} | {'Poly':<10} | {'LUT':<10} | {'Poly Diff%':<10}")
    print("-" * 60)
    for i in range(len(s_std)):
        diff_poly = torch.abs(s_std[i] - s_poly[i]) / s_std[i] * 100
        print(f"{i:<6} | {s_std[i]:.4f}   | {s_poly[i]:.4f}   | {s_lut[i]:.4f}   | {diff_poly:.2f}%")
    
    mse_poly = torch.mean((s_std - s_poly)**2)
    mse_lut = torch.mean((s_std - s_lut)**2)
    print(f"\nMSE (Standard vs Poly): {mse_poly:.8f}")
    print(f"MSE (Standard vs LUT):  {mse_lut:.8f}")
    
    # Visualization
    plt.figure(figsize=(12, 6))
    plt.plot(s_std.numpy(), 'bo-', label='Standard (FP32)', markersize=8)
    plt.plot(s_poly.numpy(), 'rs--', label='Integer Poly (I-BERT)')
    plt.plot(s_lut.numpy(), 'g^:', label='Integer Split-LUT')
    plt.title('Softmax Comparison: Standard vs Poly vs Split-LUT')
    plt.legend()
    plt.grid(True)
    plt.savefig('paper_assets/notes/iNLU_accuracy_test.png')
    print("\n✅ 精度对比图（包含 LUT）已更新保存至 paper_assets/notes/iNLU_accuracy_test.png")

if __name__ == "__main__":
    run_comparison()
