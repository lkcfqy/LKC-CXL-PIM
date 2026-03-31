#!/usr/bin/env python3
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os

OUTPUT_DIR = 'paper_assets/figures'
os.makedirs(OUTPUT_DIR, exist_ok=True)

def plot_ramulator_comparison():
    csv_path = 'simulation_results.csv'
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return

    df = pd.read_csv(csv_path)
    
    # Map ALL trace names to friendly context labels
    def get_context(t):
        if '128k' in t: return '128K'
        if '64k' in t: return '64K'
        if '32k' in t: return '32K'
        if '8k' in t: return '8K'
        if '2k' in t: return '2K'
        return t

    df['Context'] = df['Trace'].apply(get_context)

    # Define explicit ordering
    context_order = ['2K', '8K', '32K', '64K', '128K']

    # Pivot the dataframe for easier plotting
    pivot_lat = df.pivot_table(index='Context', columns='Scenario', values='ReadLatency', aggfunc='first') / 1e6  # Millions of Cycles
    pivot_miss = df.pivot_table(index='Context', columns='Scenario', values='RowMisses', aggfunc='first')

    # Sort by context order
    pivot_lat = pivot_lat.reindex(context_order)
    pivot_miss = pivot_miss.reindex(context_order)

    contexts = list(pivot_lat.index)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    x = np.arange(len(contexts))
    width = 0.35
    
    colors = {'Baseline': '#95a5a6', 'PIM-KV': '#9b59b6'}
    
    # Plot 1: Total Read Latency (Log Scale)
    rects1 = ax1.bar(x - width/2, pivot_lat['Baseline'], width, label='Baseline', color=colors['Baseline'], edgecolor='black', alpha=0.8)
    rects2 = ax1.bar(x + width/2, pivot_lat['PIM-KV'], width, label='PIM-KV (Ours)', color=colors['PIM-KV'], edgecolor='black', alpha=0.8)
    
    ax1.set_ylabel('Total Read Latency (Millions of Cycles)', fontsize=12)
    ax1.set_title('Read Latency Comparison (Log Scale)', fontsize=14, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(contexts, fontsize=11)
    ax1.set_xlabel('Context Length', fontsize=12)
    ax1.set_yscale('log')
    ax1.legend(fontsize=11)
    
    # Add values on top
    def autolabel_lat(rects, is_pim=False):
        for rect in rects:
            height = rect.get_height()
            if height > 0:
                label = f'{height:.1f}M' if height >= 1.0 else f'{height:.2f}M'
                ax1.annotate(label,
                            xy=(rect.get_x() + rect.get_width() / 2, height),
                            xytext=(0, 3 + (8 if is_pim else 0)),
                            textcoords="offset points",
                            ha='center', va='bottom', fontsize=8, fontweight='bold')

    autolabel_lat(rects1)
    autolabel_lat(rects2, is_pim=True)

    # Plot 2: Row Misses (Log Scale)
    rects3 = ax2.bar(x - width/2, pivot_miss['Baseline'], width, label='Baseline', color=colors['Baseline'], edgecolor='black', alpha=0.8)
    rects4 = ax2.bar(x + width/2, pivot_miss['PIM-KV'], width, label='PIM-KV (Ours)', color=colors['PIM-KV'], edgecolor='black', alpha=0.8)
    
    ax2.set_ylabel('Total Row Misses', fontsize=12)
    ax2.set_title('Row Buffer Locality (Log Scale)', fontsize=14, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(contexts, fontsize=11)
    ax2.set_xlabel('Context Length', fontsize=12)
    ax2.set_yscale('log')
    ax2.legend(fontsize=11)

    def autolabel_miss(rects, is_pim=False):
        for rect in rects:
            height = rect.get_height()
            if height > 0:
                ax2.annotate(f'{int(height):,}',
                            xy=(rect.get_x() + rect.get_width() / 2, height),
                            xytext=(0, 3 + (8 if is_pim else 0)),
                            textcoords="offset points",
                            ha='center', va='bottom', fontsize=8, fontweight='bold')

    autolabel_miss(rects3)
    autolabel_miss(rects4, is_pim=True)

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/fig7_ramulator_comparison.png', dpi=300)
    plt.savefig(f'{OUTPUT_DIR}/fig7_ramulator_comparison.pdf')
    print(f"✅ Generated grouped bar chart: {OUTPUT_DIR}/fig7_ramulator_comparison.png")

if __name__ == "__main__":
    plot_ramulator_comparison()

