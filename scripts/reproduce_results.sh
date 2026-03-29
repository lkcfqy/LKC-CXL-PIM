#!/bin/bash
# scripts/reproduce_results.sh
# Automated simulation runner for LKC-CXL-PIM

set -e

# Project root
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RAMULATOR_DIR="$BASE_DIR/ramulator2"
TRACES_DIR="$BASE_DIR/traces"

echo "========================================================"
echo "LKC-CXL-PIM: Automated Simulation Runner"
echo "========================================================"

# Available traces
TRACES=("real_kv_2k.trace" "real_kv_4k.trace" "extrapolated_8k.trace") # Add others as needed

# Create standardized output file
OUTPUT_CSV="$BASE_DIR/simulation_results.csv"
echo "Trace,Scenario,ReadLatency,WriteLatency,RowMisses" > $OUTPUT_CSV

run_sim() {
    local trace_name=$1
    local scenario_name=$2
    local config_file=$3
    
    local trace_path="$TRACES_DIR/$trace_name"
    
    if [ ! -f "$trace_path" ]; then
        echo "Warning: Trace $trace_name not found, skipping."
        return
    fi
     
    echo "--------------------------------------------------------"
    echo "Running: $scenario_name | Trace: $trace_name"
    echo "--------------------------------------------------------"
    
    # 1. Prepare trace for Docker (copy to mounted dir)
    cp "$trace_path" "$RAMULATOR_DIR/traces/current.trace"
    
    # 2. Run Ramulator via Docker
    # We use 'ramulator2/ramulator2' as the executable (assumed compiled)
    # Output is captured to a log file
    
    cd "$RAMULATOR_DIR"
    
    # Ensure build exists/compiled - User should have done this
    if [ ! -f "ramulator2" ]; then
        echo "Error: ramulator2 executable not found in $RAMULATOR_DIR"
        exit 1
    fi
    
    LOG_FILE="$BASE_DIR/logs/${trace_name}_${scenario_name}.log"
    mkdir -p "$(dirname "$LOG_FILE")"
    
    # Run command inside Docker
    # Note: We use 'docker compose run' to execute the binary
    # Configuration path is relative to /ramulator2 inside container
    
    if docker compose -f compose-dev.yaml run --rm --entrypoint "" --workdir /ramulator2 app ./ramulator2 -f $config_file > "$LOG_FILE" 2>&1; then
        echo "  Simulation complete."
    else
        echo "  Simulation FAILED. See $LOG_FILE"
        cat "$LOG_FILE" | tail -n 20
        return
    fi
    
    # 3. Parse Results
    # stats extraction depends on Ramulator output format
    # Looking for: 
    #   read_latency_avg_0: ...
    #   write_latency_avg_0: ... (our new stat)
    #   row_misses_0: ...
    
    local read_lat=$(awk '/^[ \t]*read_latency_0:/ {print $2}' "$LOG_FILE")
    local write_lat=$(awk '/^[ \t]*write_latency_0:/ {print $2}' "$LOG_FILE")
    
    # Properly extract row_misses_0 and row_conflicts_0
    local misses=$(awk '/^[ \t]*row_misses_0:/ {print $2}' "$LOG_FILE")
    local conflicts=$(awk '/^[ \t]*row_conflicts_0:/ {print $2}' "$LOG_FILE")
    misses=${misses:-0}
    conflicts=${conflicts:-0}
    
    # In OpenRowPolicy, total misses = page empty + page conflict
    local row_miss=$((misses + conflicts))
    
    echo "  Read Latency: $read_lat"
    echo "  Write Latency: $write_lat"
    echo "  Row Misses: $row_miss ($misses misses + $conflicts conflicts)"
    
    echo "$trace_name,$scenario_name,$read_lat,$write_lat,$row_miss" >> $OUTPUT_CSV
}

# Run for 2K trace (Real)
run_sim "real_kv_2k.trace" "Baseline" "hbm3_pim_baseline.yaml"
run_sim "real_kv_2k.trace" "PIM-KV"   "hbm3_pim_kv.yaml"

# Run for 8K trace (if available, using the one we extrapolated/found)
if [ -f "$TRACES_DIR/real_kv_8k.trace" ]; then
    run_sim "real_kv_8k.trace" "Baseline" "hbm3_pim_baseline.yaml"
    run_sim "real_kv_8k.trace" "PIM-KV"   "hbm3_pim_kv.yaml"
fi

echo "========================================================"
echo "All simulations completed."
echo "Results saved to $OUTPUT_CSV"
