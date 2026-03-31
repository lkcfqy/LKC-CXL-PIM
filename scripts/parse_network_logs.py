#!/usr/bin/env python3
"""
parse_network_logs.py - Phase 5.5
Parses JSON output from Python simulators into aggregated CSV 
files for external evaluation and tracing.
"""
import sys
import json
import csv
import os

def parse_scheduler_log(json_path, output_csv):
    """
    Parses output from host_os_scheduler.py
    Extracts utilization metrics, imbalance ratios, and migration tracking.
    """
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    print(f"Parsing scheduler log: {json_path}")
    
    with open(json_path, 'r') as f:
        data = json.load(f)

    # We will output Paper Metrics
    metrics = data.get('paper_metrics', {})
    lb = data.get('load_balance', {})
    
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    with open(output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Utilization_STD', metrics.get('utilization_std', 0)])
        writer.writerow(['Peak_Utilization', metrics.get('peak_utilization', 0)])
        writer.writerow(['Imbalance_Ratio', lb.get('imbalance_ratio', 0)])
        writer.writerow(['Total_Migrations', metrics.get('total_migrations', 0)])
        writer.writerow(['Migration_Overhead_ms', metrics.get('migration_overhead_ms', 0)])
        
    print(f"  -> Extracted Metrics to {output_csv}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: parse_network_logs.py <input_json> <output_csv>")
        sys.exit(1)
        
    parse_scheduler_log(sys.argv[1], sys.argv[2])
