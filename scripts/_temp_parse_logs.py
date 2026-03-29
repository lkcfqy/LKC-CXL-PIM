import os
import re
import csv

log_dir = "/home/fqy/lkcproject/LKC-CXL-PIM/logs"
csv_path = "/home/fqy/lkcproject/LKC-CXL-PIM/simulation_results.csv"

traces = ["real_kv_2k.trace", "real_kv_8k.trace"]
scenarios = ["Baseline", "PIM-KV"]

results = []

for t in traces:
    for s in scenarios:
        log_path = os.path.join(log_dir, f"{t}_{s}.log")
        if not os.path.exists(log_path):
            continue
        
        with open(log_path, 'r') as f:
            content = f.read()
            
            read_lat = re.search(r'^[ \t]*read_latency_0:\s*([\d\.]+)', content, re.M)
            write_lat = re.search(r'^[ \t]*write_latency_0:\s*([\d\.]+)', content, re.M)
            misses = re.search(r'^[ \t]*row_misses_0:\s*([\d\.]+)', content, re.M)
            conflicts = re.search(r'^[ \t]*row_conflicts_0:\s*([\d\.]+)', content, re.M)
            
            read_val = read_lat.group(1) if read_lat else "0"
            write_val = write_lat.group(1) if write_lat else "0"
            m_val = misses.group(1) if misses else "0"
            c_val = conflicts.group(1) if conflicts else "0"
            
            row_misses = int(m_val) + int(c_val)
            
            results.append([t, s, read_val, write_val, str(row_misses)])

with open(csv_path, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["Trace", "Scenario", "ReadLatency", "WriteLatency", "RowMisses"])
    writer.writerows(results)

print("Updated CSV directly from logs!")
