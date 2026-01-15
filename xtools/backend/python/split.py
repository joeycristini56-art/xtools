#!/usr/bin/env python3
"""
CC/PayPal Filter Utility
Filters valid*.txt files to keep only accounts with credit cards or PayPal
"""

import os
import re
import json
import glob

def has_cc_or_paypal(line):
    """Check if line contains CC or PayPal info"""
    return bool(re.search(r'(Visa|MasterCard|Amex|Discover|Maestro).*••••|Paypal?\s*:\s*\S+@\S+', line, re.I))

def filter_cc_paypal(input_dir: str = ".", output_file: str = "valid.txt") -> str:
    """
    Filter valid*.txt files for CC/PayPal accounts
    
    Args:
        input_dir: Directory containing valid*.txt files
        output_file: Output file path
    
    Returns:
        JSON string with results
    """
    try:
        # Find all valid*.txt files
        pattern = os.path.join(input_dir, "valid*.txt")
        files = glob.glob(pattern)
        
        if not files:
            return json.dumps({
                "success": False,
                "error": "No valid*.txt files found"
            })
        
        premium_hits = []
        
        # Read all files
        for file in files:
            try:
                with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if line and has_cc_or_paypal(line):
                            premium_hits.append(line)
            except Exception as e:
                pass  # Skip files that can't be read
        
        if not premium_hits:
            return json.dumps({
                "success": False,
                "error": "No CC/PayPal accounts found"
            })
        
        # Delete output file if exists
        if os.path.exists(output_file):
            os.remove(output_file)
        
        # Write filtered results
        with open(output_file, "w", encoding="utf-8", newline="\n") as f:
            for hit in premium_hits:
                f.write(hit + "\n")
        
        # Delete old valid*.txt files (except output)
        files_deleted = []
        for file in files:
            if os.path.exists(file) and os.path.basename(file) != os.path.basename(output_file):
                try:
                    os.remove(file)
                    files_deleted.append(os.path.basename(file))
                except:
                    pass
        
        return json.dumps({
            "success": True,
            "total_files": len(files),
            "premium_accounts": len(premium_hits),
            "output_file": output_file,
            "files_deleted": files_deleted
        })
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })

# FFI-compatible function
def process_file_ffi(file_path: str) -> str:
    """Filter file for CC/PayPal (FFI)"""
    # file_path is actually the directory
    return filter_cc_paypal(file_path)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = filter_cc_paypal(sys.argv[1] if len(sys.argv) > 1 else ".", sys.argv[2] if len(sys.argv) > 2 else "valid.txt")
        print(result)
