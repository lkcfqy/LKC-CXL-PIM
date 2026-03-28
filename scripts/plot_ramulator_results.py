#!/usr/bin/env python3
import matplotlib.pyplot as plt
import pandas as pd
import os

OUTPUT_DIR = 'paper_assets/figures'
os.makedirs(OUTPUT_DIR, exist_ok=True)

def plot_ramulator_comparison():
    csv_path = 'simulation_results.csv'
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found. Please run reproduce_results.sh space first.")
        return

    df = pd.read_csv(csv_path)
    
    # We will aggregate to compare Baseline vs PIM-KV across the board, or just take the 2k trace as default
    # Let's just group by Scenario and get the mean if multiple traces exist
    grouped = df.groupby('Scenario')[['ReadLatency', 'RowMisses']].mean().reset_index()

    if len(grouped) == 0:
        print("Error: No data in CSV")
        return

    baseline_row = grouped[grouped['Scenario'] == 'Baseline']
    pim_row = grouped[grouped['Scenario'] == 'PIM-KV']
    
    if baseline_row.empty or pim_row.empty:
        print("Error: Missing Baseline or PIM-KV data")
        return

    results = {
        'Baseline': {
            'latency': baseline_row['ReadLatency'].values[0],
            'row_misses': baseline_row['RowMisses'].values[0]
        },
        'PIM-KV (Ours)': {
            'latency': pim_row['ReadLatency'].values[0],
            'row_misses': pim_row['RowMisses'].values[0]
        }
    }

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    labels = list(results.keys())
    latencies = [results[l]['latency'] for l in labels]
    row_misses = [results[l]['row_misses'] for l in labels]
    
    # Plot 1: Average Read Latency
    colors = ['#95a5a6', '#9b59b6']
    bars1 = ax1.bar(labels, latencies, color=colors, alpha=0.8, edgecolor='black', width=0.6)
    ax1.set_ylabel('Avg Read Latency (Cycles)', fontsize=12)
    ax1.set_title('Memory Latency Comparison', fontsize=14, fontweight='bold')
    ax1.set_ylim(0, max(latencies) * 1.3)
    
    for bar in bars1:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + max(latencies)*0.05,
                f'{height:.2f}', ha='center', va='bottom', fontsize=11, fontweight='bold')

    # Plot 2: Row Misses (Log Scale for visibility)
    bars2 = ax2.bar(labels, row_misses, color=colors, alpha=0.8, edgecolor='black', width=0.6)
    ax2.set_ylabel('Total Row Misses (Misses + Conflicts)', fontsize=12)
    ax2.set_title('Row Buffer Locality (Log Scale)', fontsize=14, fontweight='bold')
    ax2.set_yscale('log')
    
    for bar in bars2:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height * 1.5,
                f'{int(height):,}', ha='center', va='bottom', fontsize=11, fontweight='bold')

    # Add reduction % text
    latency_reduction = (results['Baseline']['latency'] - results['PIM-KV (Ours)']['latency']) / results['Baseline']['latency'] * 100
    ax1.text(0.5, max(latencies)*1.15, f'Improvement: {latency_reduction:.1f}%', 
             ha='center', fontsize=11, color='#9b59b6', fontweight='bold',
             bbox=dict(facecolor='white', alpha=0.7, edgecolor='#9b59b6'))
    
    miss_reduction = (results['Baseline']['row_misses'] - results['PIM-KV (Ours)']['row_misses']) / results['Baseline']['row_misses'] * 100
    
    ax2.text(0.5, max(row_misses)*0.1, f'{miss_reduction:.2f}% Reduction!', 
             ha='center', fontsize=11, color='#e74c3c', fontweight='bold',
             bbox=dict(facecolor='white', alpha=0.7, edgecolor='#e74c3c'))

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/fig7_ramulator_comparison.png')
    plt.savefig(f'{OUTPUT_DIR}/fig7_ramulator_comparison.pdf')
    print(f"✅ Generated: {OUTPUT_DIR}/fig7_ramulator_comparison.png")

if __name__ == "__main__":
    plot_ramulator_comparison()
