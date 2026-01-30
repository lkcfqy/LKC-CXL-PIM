#!/usr/bin/env python3
"""
convert_trace_for_ramulator.py - Convert KV trace to Ramulator format

Ramulator trace format:
  <bubble_count> <addr> [<addr2>]
  
Where bubble_count is:
  0-4: Load (Read)
  5: Store (Write)
  
Our custom format:
  RK addr ch,pc,bg,ba,row,col  -> Read Key
  RV addr ch,pc,bg,ba,row,col  -> Read Value
  K addr ...                    -> Write Key (PIM)
  V addr ...                    -> Write Value (PIM)
"""

import argparse
import os


def convert_trace(input_path: str, output_path: str, max_lines: int = 100000):
    """Convert custom KV trace to Ramulator format"""
    
    with open(input_path, 'r') as f_in:
        lines = f_in.readlines()
    
    converted = []
    bubble = 0  # Bubble count (simulates compute between accesses)
    
    for i, line in enumerate(lines):
        if i >= max_lines:
            break
            
        parts = line.strip().split()
        if len(parts) < 2:
            continue
            
        op = parts[0]
        addr = int(parts[1])
        
        if op in ['RK', 'RV', 'R']:
            # Read operation: use bubble count 0-4 (round robin)
            converted.append(f"{bubble % 5} {addr}")
            bubble += 1
        elif op in ['K', 'V', 'WK', 'WV', 'W']:
            # Write operation: use code 5
            converted.append(f"5 {addr}")
    
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    
    with open(output_path, 'w') as f_out:
        f_out.write('\n'.join(converted))
        f_out.write('\n')
    
    return len(converted)


def main():
    parser = argparse.ArgumentParser(description="Convert KV trace to Ramulator format")
    parser.add_argument("--input", "-i", required=True, help="Input trace file")
    parser.add_argument("--output", "-o", required=True, help="Output Ramulator trace")
    parser.add_argument("--max_lines", "-n", type=int, default=100000, 
                        help="Max lines to convert (default: 100000)")
    
    args = parser.parse_args()
    
    print(f"Converting {args.input} to Ramulator format...")
    count = convert_trace(args.input, args.output, args.max_lines)
    print(f"✅ Converted {count} trace entries to {args.output}")


if __name__ == "__main__":
    main()
