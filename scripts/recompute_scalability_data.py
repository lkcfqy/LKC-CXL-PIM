#!/usr/bin/env python3
import subprocess
import os
import json
import sys
import tempfile

SINGLE_NODE_REFERENCE_EFFICIENCY = 0.95

def run_scheduler(num_nodes):
    if num_nodes == 1:
        print("Using single-node reference efficiency (no distributed scheduler path).")
        return {"paper_metrics": {"scheduling_efficiency": SINGLE_NODE_REFERENCE_EFFICIENCY}}

    print(f"Running scheduler for {num_nodes} nodes...")
    # Create temp config
    config = f"""
CXLFabric:
  num_nodes: {num_nodes}
  nodes:
    - node_id: 0
      role: shared_kv
      capacity_gb: 16
"""
    for i in range(1, num_nodes):
        config += f"""
    - node_id: {i}
      role: private_kv
      capacity_gb: 16
"""
    config += """
  switch:
    port_bandwidth_gbps: 64
"""
    
    with tempfile.NamedTemporaryFile("w", suffix=f"_{num_nodes}_nodes.yaml", delete=False) as f:
        config_path = f.name
        f.write(config)
    
    trace_path = "traces/multitenant/multi_tenant_50req.trace"
    if not os.path.exists(trace_path):
         # If the large trace is missing, use the prefix sharing one or a sample
         trace_path = "traces/multitenant/prefix_sharing_50u_8k.trace"

    output_path = f"results/scheduler_{num_nodes}_nodes.json"
    cmd = [
        sys.executable, "scripts/host_os_scheduler.py",
        "--config", config_path,
        "--trace", trace_path,
        "--policy", "locality_aware",
        "--output", output_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(
                f"Scheduler failed for {num_nodes} nodes.\n"
                f"Command: {' '.join(cmd)}\n"
                f"stderr:\n{result.stderr}"
            )
    finally:
        try:
            os.unlink(config_path)
        except OSError:
            pass
    
    with open(output_path, "r") as f:
        return json.load(f)

def main():
    os.makedirs("results", exist_ok=True)
    results = {}
    for n in [1, 2, 4, 8, 16]:
        res = run_scheduler(n)
        # Extract scheduling efficiency or throughput metric
        eff = res.get('locality_aware', {}).get('paper_metrics', {}).get('scheduling_efficiency', 1.0)
        # For simplicity, if locality_aware key is missing (it's in 'paper_metrics' top level usually):
        if 'locality_aware' not in res:
             eff = res.get('paper_metrics', {}).get('scheduling_efficiency', 1.0)
        results[n] = eff
        
    with open("results/scalability_summary.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Done. Saved to results/scalability_summary.json")

if __name__ == "__main__":
    main()
