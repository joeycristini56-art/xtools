#!/usr/bin/env python3
"""
File Filter Utility
Removes duplicate lines from files
"""

import os
import json

def filter_duplicates(input_file: str, output_file: str = None) -> str:
    """
    Remove duplicate lines from a file
    
    Args:
        input_file: Path to input file
        output_file: Path to output file (optional, defaults to input_file + .filtered)
    
    Returns:
        JSON string with results
    """
    try:
        if not os.path.exists(input_file):
            return json.dumps({
                "success": False,
                "error": f"File not found: {input_file}"
            })
        
        if output_file is None:
            output_file = input_file + ".filtered"
        
        unique_lines = set()
        
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                unique_lines.add(line.strip())
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for line in unique_lines:
                f.write(line + '\n')
        
        return json.dumps({
            "success": True,
            "original": sum(1 for _ in open(input_file)),
            "unique": len(unique_lines),
            "output": output_file
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = filter_duplicates(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
        print(result)

# FFI-compatible function
def process_file_ffi(file_path: str) -> str:
    """Filter file - remove duplicates (FFI)"""
    return filter_duplicates(file_path)
