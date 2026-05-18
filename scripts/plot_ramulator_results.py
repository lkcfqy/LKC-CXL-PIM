#!/usr/bin/env python3
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os
from figure_style import COLORS, HATCHES, apply_conference_style, clean_axis, save_pdf_png

OUTPUT_DIR = 'paper_assets/figures'
os.makedirs(OUTPUT_DIR, exist_ok=True)

def plot_ramulator_comparison():
    apply_conference_style()

    csv_path = 'simulation_results.csv'
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return

    df = pd.read_csv(csv_path)

    def get_context(t):
        if '128k' in t: return '128K'
        if '64k' in t: return '64K'
        if '32k' in t: return '32K'
        if '8k' in t: return '8K'
        if '2k' in t: return '2K'
        return t

    df['Context'] = df['Trace'].apply(get_context)
    context_order = ['2K', '8K', '32K', '64K', '128K']

    pivot_lat = df.pivot_table(index='Context', columns='Scenario', values='ReadLatency', aggfunc='first') / 1e6
    pivot_miss = df.pivot_table(index='Context', columns='Scenario', values='RowMisses', aggfunc='first')

    pivot_lat = pivot_lat.reindex(context_order)
    pivot_miss = pivot_miss.reindex(context_order)

    contexts = list(pivot_lat.index)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.45))

    x = np.arange(len(contexts))
    width = 0.35

    rects1 = ax1.bar(x - width/2, pivot_lat['Baseline'], width, label='Baseline',
                     color=COLORS['baseline'], edgecolor='black', hatch=HATCHES['baseline'])
    rects2 = ax1.bar(x + width/2, pivot_lat['PIM-KV'], width, label='PIM-KV (Ours)',
                     color=COLORS['ours'], edgecolor='black', hatch=HATCHES['ours'])

    ax1.set_ylabel('Read Latency (M Cycles)')
    ax1.set_title('Read Latency')
    ax1.set_xticks(x)
    ax1.set_xticklabels(contexts)
    ax1.set_yscale('log')
    ax1.legend(loc='upper left', frameon=False)

    rects3 = ax2.bar(x - width/2, pivot_miss['Baseline'], width, label='Baseline',
                     color=COLORS['baseline'], edgecolor='black', hatch=HATCHES['baseline'])
    rects4 = ax2.bar(x + width/2, pivot_miss['PIM-KV'], width, label='PIM-KV (Ours)',
                     color=COLORS['ours'], edgecolor='black', hatch=HATCHES['ours'])

    ax2.set_ylabel('Total Row Misses')
    ax2.set_title('Row Buffer Locality')
    ax2.set_xticks(x)
    ax2.set_xticklabels(contexts)
    ax2.set_yscale('log')
    ax2.legend(loc='upper left', frameon=False)

    for ax in (ax1, ax2):
        clean_axis(ax)

    plt.tight_layout()
    save_pdf_png(fig, OUTPUT_DIR, 'fig7_ramulator_comparison')
    print(f"✅ Generated grouped bar chart: {OUTPUT_DIR}/fig7_ramulator_comparison.png")

if __name__ == "__main__":
    plot_ramulator_comparison()
