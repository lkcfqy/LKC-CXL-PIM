#!/usr/bin/env python3
"""
plot_paper_figures.py - Phase 5.5
Generates the 'Big Four' Matplotlib figures for the DisaggKV system evaluation.
Uses high-quality academic aesthetics suitable for top-tier systems conferences.
"""
import os
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from figure_style import COLORS, HATCHES, apply_conference_style, clean_axis, save_pdf_png

apply_conference_style()

OUTPUT_DIR = "paper_assets/figures"
DATA_FILE = "paper_assets/data/paper_metrics.json"

def load_data():
    with open(DATA_FILE, 'r') as f:
        return json.load(f)


def style_axis(ax, grid_axis='y', hide_right=True):
    clean_axis(ax, grid_axis=grid_axis, hide_right=hide_right)

def plot_throughput_latency(data):
    fig, ax = plt.subplots(figsize=(6.6, 4.3))

    d = data['throughput_latency']
    x = d['x_throughput']

    ax.plot(x, d['y_lat_host'], label='Host-Agg (Baseline)',
            linestyle='--', marker='o', markersize=4.5, color=COLORS['baseline'], alpha=0.9)

    ax.plot(x, d['y_lat_ours'], label='DisaggKV (Ours)',
            linestyle='-', marker='s', markersize=4.5, color=COLORS['ours'])

    ax.axhline(y=d['sla_ms'], color='black', linestyle=':', linewidth=1.5, alpha=0.5, label='50ms SLA boundary')

    ax.text(x[-1] - 800, d['sla_ms'] + 5, '50ms SLA Limit', color='black', fontsize=9.5)

    ax.set_ylim(0, 150)
    ax.set_ylabel('99% Tail Latency (ms)')
    ax.set_xlabel('System Throughput (Requests / second)')

    ax.legend(loc='upper left', frameon=False)
    style_axis(ax)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig1_throughput_latency.png'), dpi=300)
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig1_throughput_latency.pdf'), format='pdf', bbox_inches='tight')
    plt.close()

def plot_scalability(data):
    fig, ax = plt.subplots(figsize=(6.6, 4.3))

    d = data['scalability']
    x = d['x_nodes']

    ax.plot(x, d['y_ideal'], label='Ideal Linear', linestyle=':', color=COLORS['ideal'], alpha=0.55)
    ax.plot(x, d['y_host'], label='Host-Agg', marker='o', markersize=4.5, linestyle='--', color=COLORS['baseline'])
    ax.plot(x, d['y_ours'], label='DisaggKV (Ours)', marker='s', markersize=4.5, linestyle='-', color=COLORS['ours'])

    ax.set_xticks(x)
    ax.set_ylabel('Max Throughput (Req/s) under SLA')
    ax.set_xlabel('Number of CXL-PIM Nodes')
    ax.legend(loc='upper left', frameon=False)
    style_axis(ax)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig2_scalability.png'), dpi=300)
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig2_scalability.pdf'), format='pdf', bbox_inches='tight')
    plt.close()

def plot_traffic_breakdown(data):
    fig, ax = plt.subplots(figsize=(6.6, 4.3))

    d = data['traffic_breakdown']
    cats = d['categories']
    display_cats = [
        'Local HBM\nAccess' if c == 'Local HBM Access'
        else 'CXL P2P\nData' if c == 'CXL P2P Data'
        else 'CXL-to-Host\nTraffic' if c == 'CXL-to-Host Traffic'
        else c
        for c in cats
    ]
    host = d['host_agg']
    ours = d['disaggkv']

    x = np.arange(len(cats))
    width = 0.35

    bars1 = ax.bar(x - width/2, host, width, label='Host-Agg',
                   color=COLORS['baseline'], edgecolor='black', linewidth=0.7, alpha=0.9, hatch=HATCHES['baseline'])
    bars2 = ax.bar(x + width/2, ours, width, label='DisaggKV (Ours)',
                   color=COLORS['ours'], edgecolor='black', linewidth=0.7, hatch=HATCHES['ours'])

    max_val = max(max(host), max(ours))
    ax.set_ylim(0, max_val * 1.25)

    ax.set_ylabel('Data Traffic (GB) per 1M Tokens')
    ax.set_xticks(x)
    ax.set_xticklabels(display_cats)
    ax.legend(loc='upper right', frameon=False)

    for bar in bars1:
        yval = bar.get_height()
        if yval > 0.005:
            ax.text(bar.get_x() + bar.get_width()/2, yval + (max_val * 0.02), f'{yval:.2f}', ha='center', va='bottom', fontsize=9)
    for bar in bars2:
        yval = bar.get_height()
        if yval >= 0.005:
            ax.text(bar.get_x() + bar.get_width()/2, yval + (max_val * 0.02), f'{yval:.2f}', ha='center', va='bottom', fontsize=9)

    style_axis(ax)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig3_network_breakdown.png'), dpi=300)
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig3_network_breakdown.pdf'), format='pdf', bbox_inches='tight')
    plt.close()

def plot_fault_recovery(data):
    fig, ax = plt.subplots(figsize=(6.6, 4.4))

    d = data['fault_recovery']
    methods = d['methods']
    display_methods = [
        'PIM XOR\nParity' if m.startswith('PIM XOR')
        else 'Host RDMA\nBackup' if m.startswith('Host RDMA')
        else 'Checkpoint\nRestart' if m.startswith('Checkpoint')
        else m
        for m in methods
    ]
    latencies = d['latencies']

    bars = ax.bar(display_methods, latencies, color=[COLORS['ours'], COLORS['baseline'], COLORS['lut']],
                  edgecolor='black', linewidth=0.8, hatch=[HATCHES['ours'], HATCHES['baseline'], HATCHES['lut']], width=0.6)

    ax.set_yscale('log')
    ax.set_ylim(top=max(latencies) * 10)

    ax.set_ylabel('Recovery Latency (ms) [Log Scale]')
    ax.tick_params(axis='x', labelsize=9.5)

    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, yval * 1.3, f'{yval:,.0f} ms', ha='center', va='bottom', fontsize=10, fontweight='bold')

    style_axis(ax)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig4_fault_recovery.png'), dpi=300)
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig4_fault_recovery.pdf'), format='pdf', bbox_inches='tight')
    plt.close()

def plot_latency_sensitivity(sens_data):
    fig, ax = plt.subplots(figsize=(6.6, 4.3))

    d = sens_data['cxl_latency']
    x = d['x_cxl_latency']

    ax.plot(x, d['y_throughput_baseline'], label='Host-Agg (Baseline)',
            linestyle='--', marker='o', markersize=4.5, color=COLORS['baseline'], alpha=0.9)
    ax.plot(x, d['y_throughput_ours'], label='DisaggKV (Ours)',
            linestyle='-', marker='s', markersize=4.5, color=COLORS['ours'])

    ax.set_xlabel('CXL Link Latency (ns)')
    ax.set_ylabel('Max Throughput (Req/s)')
    ax.legend(loc='upper right', frameon=False)
    style_axis(ax)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig5_sensitivity_latency.png'), dpi=300)
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig5_sensitivity_latency.pdf'), format='pdf', bbox_inches='tight')
    plt.close()

def plot_outlier_sensitivity(sens_data):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.1, 3.25), sharex=True)

    d = sens_data['outlier_buffer']
    x = d['x_entries']

    ax1.plot(x, d['y_accuracy'], color=COLORS['ours'], marker='s', markersize=4.5, linestyle='-')
    ax1.set_xlabel('Outlier Buffer Entries')
    ax1.set_ylabel('Relative Accuracy (vs. FP32)')
    ax1.set_ylim(0.75, 1.05)
    ax1.axhline(y=0.975, color=COLORS['ideal'], linestyle=':', linewidth=1.0, alpha=0.7)
    ax1.text(1.5, 0.982, '0.975 target', fontsize=8.2, color=COLORS['ideal'])
    ax1.set_title('Accuracy')

    ax2.plot(x, d['y_area_ours'], color=COLORS['area'], marker='o', markersize=4.5, linestyle='-')
    ax2.axhline(y=1.0, color=COLORS['baseline'], linestyle=':', linewidth=1.0)
    ax2.text(1.5, 1.006, 'Standard PIM area', fontsize=8.2, color=COLORS['baseline'])
    ax2.set_xlabel('Outlier Buffer Entries')
    ax2.set_ylabel('Relative Logic Area')
    ax2.set_ylim(0.7, 1.1)
    ax2.set_title('Area')

    style_axis(ax1)
    style_axis(ax2)

    plt.tight_layout()
    save_pdf_png(fig, OUTPUT_DIR, 'fig10_sensitivity_outliers')
    plt.close()

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(DATA_FILE):
        print(f"Error: {DATA_FILE} not found. Run generate_paper_data.py first.")
        return

    print("Generating High-Quality Figures for Paper Expansion...")
    data = load_data()

    # Base figures
    plot_throughput_latency(data)
    print("  -> Created fig1_throughput_latency.png / .pdf")
    plot_scalability(data)
    print("  -> Created fig2_scalability.png / .pdf")
    plot_traffic_breakdown(data)
    print("  -> Created fig3_network_breakdown.png / .pdf")
    plot_fault_recovery(data)
    print("  -> Created fig4_fault_recovery.png / .pdf")

    # Sensitivity figures
    sens_file = "paper_assets/data/sensitivity_metrics.json"
    if os.path.exists(sens_file):
        with open(sens_file, 'r') as f:
            sens_data = json.load(f)
        plot_latency_sensitivity(sens_data)
        print("  -> Created fig5_sensitivity_latency.png / .pdf")
        plot_outlier_sensitivity(sens_data)
        print("  -> Created fig10_sensitivity_outliers.png / .pdf")

    print("All figures successfully generated in paper_assets/figures/")

if __name__ == "__main__":
    main()
