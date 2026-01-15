#!/usr/bin/env python3
"""
Tool to consolidate and deduplicate email:password combinations from files containing 'valid' in their names.
"""

import os
import re
import glob
from pathlib import Path

def find_valid_files():
    """Find all files with 'valid' in their names."""
    valid_files = set()  # Use set to avoid duplicates
    
    # Search for files with 'valid' in the name (case insensitive)
    for pattern in ['*valid*', '*Valid*', '*VALID*']:
        for file in glob.glob(pattern, recursive=False):
            # Convert to absolute path to avoid duplicates
            abs_path = os.path.abspath(file)
            if '.git' not in abs_path:
                valid_files.add(abs_path)
    
    # Also search in subdirectories
    for root, dirs, files in os.walk('.'):
        for file in files:
            if 'valid' in file.lower():
                file_path = os.path.join(root, file)
                abs_path = os.path.abspath(file_path)
                # Skip git hooks and other system files
                if '.git' not in abs_path:
                    valid_files.add(abs_path)
    
    return list(valid_files)

def extract_email_pass_combos(file_path):
    """Extract email:password combinations with all additional data from a file."""
    combos = set()
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
                
            # Look for lines that contain email:password pattern
            # The format appears to be: email:password | additional_data
            if ':' in line and '@' in line:
                # Check if it looks like an email:password combination
                email_pass_match = re.match(r'^([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}):(.+)', line)
                if email_pass_match:
                    # Keep the entire line with all the additional data (CC, PayPal, Country, etc.)
                    combos.add(line)
                else:
                    # Fallback: if it contains @ and : but doesn't match strict pattern
                    # Still try to capture it in case of edge cases
                    if re.search(r'[^@\s]+@[^@\s]+\.[^@\s]+:', line):
                        combos.add(line)
                    
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    
    return combos

def main():
    """Main function to process valid files."""
    print("Looking for files with 'valid' in their names...")
    
    # Find all valid files
    valid_files = find_valid_files()
    
    if not valid_files:
        print("No files with 'valid' in their names found.")
        return
    
    print(f"Found {len(valid_files)} files with 'valid' in their names:")
    for file in valid_files:
        print(f"  - {file}")
    
    # Collect all email:password combinations
    all_combos = set()
    
    for file_path in valid_files:
        print(f"Processing {file_path}...")
        combos = extract_email_pass_combos(file_path)
        all_combos.update(combos)
        print(f"  Found {len(combos)} combinations")
    
    print(f"\nTotal unique combinations found: {len(all_combos)}")
    
    # Clear valid.txt if it exists and write all deduplicated combinations
    output_file = 'valid.txt'
    
    # Remove existing valid.txt content
    if os.path.exists(output_file):
        print(f"Clearing existing {output_file}...")
        open(output_file, 'w').close()
    
    # Write all deduplicated combinations to valid.txt
    print(f"Writing {len(all_combos)} unique combinations to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        for combo in sorted(all_combos):  # Sort for consistent output
            f.write(combo + '\n')
    
    # Remove the other valid files (but not the output file)
    files_to_remove = [f for f in valid_files if os.path.abspath(f) != os.path.abspath(output_file)]
    
    if files_to_remove:
        print(f"\nRemoving {len(files_to_remove)} processed files:")
        for file_path in files_to_remove:
            try:
                os.remove(file_path)
                print(f"  Removed: {file_path}")
            except Exception as e:
                print(f"  Error removing {file_path}: {e}")
    
    print(f"\nDone! All unique email:password combinations are now in {output_file}")
    print(f"Total combinations written: {len(all_combos)}")

if __name__ == "__main__":
    main()
# XTools FFI Integration
import json

def process_file_ffi(file_path: str) -> str:
    """Deduplicate file via FFI"""
    try:
        if not os.path.exists(file_path):
            return json.dumps({"success": False, "error": f"File not found: {file_path}"})
        
        unique_lines = set()
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                unique_lines.add(line.strip())
        
        output = file_path + ".dedup"
        with open(output, 'w', encoding='utf-8') as f:
            for line in unique_lines:
                f.write(line + '\n')
        
        return json.dumps({
            "success": True,
            "original": sum(1 for _ in open(file_path)),
            "deduplicated": len(unique_lines),
            "output": output
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(process_file_ffi(sys.argv[1]))
