#!/usr/bin/env python3
"""
Email Parser Script - s.py
Extracts Gmail and Microsoft email accounts from combo files.
Supports country-specific domains and removes duplicates.
Processes large files in chunks for memory efficiency.
"""

import os
import re
import glob
import tempfile
from typing import Set, List, Tuple
from collections import defaultdict

def get_gmail_domains() -> Set[str]:
    """Returns a set of Gmail domain patterns (including country-specific)."""
    return {
        'gmail.com',
        'googlemail.com'
    }

def get_microsoft_domains() -> Set[str]:
    """Returns a set of Microsoft domain patterns (including country-specific)."""
    return {
        'hotmail.com', 'hotmail.co.uk', 'hotmail.fr', 'hotmail.de', 'hotmail.es',
        'hotmail.it', 'hotmail.ca', 'hotmail.com.au', 'hotmail.co.jp', 'hotmail.co.in',
        'hotmail.com.br', 'hotmail.com.mx', 'hotmail.com.ar', 'hotmail.nl', 'hotmail.be',
        'hotmail.ch', 'hotmail.at', 'hotmail.dk', 'hotmail.se', 'hotmail.no',
        'hotmail.fi', 'hotmail.pl', 'hotmail.cz', 'hotmail.hu', 'hotmail.gr',
        'hotmail.pt', 'hotmail.ru', 'hotmail.com.tr', 'hotmail.co.za', 'hotmail.sg',
        'hotmail.my', 'hotmail.ph', 'hotmail.th', 'hotmail.vn', 'hotmail.co.kr',
        'hotmail.com.tw', 'hotmail.hk', 'hotmail.co.nz', 'hotmail.ie', 'hotmail.co.il',
        'outlook.com', 'outlook.co.uk', 'outlook.fr', 'outlook.de', 'outlook.es',
        'outlook.it', 'outlook.ca', 'outlook.com.au', 'outlook.co.jp', 'outlook.co.in',
        'outlook.com.br', 'outlook.com.mx', 'outlook.com.ar', 'outlook.nl', 'outlook.be',
        'outlook.ch', 'outlook.at', 'outlook.dk', 'outlook.se', 'outlook.no',
        'outlook.fi', 'outlook.pl', 'outlook.cz', 'outlook.hu', 'outlook.gr',
        'outlook.pt', 'outlook.ru', 'outlook.com.tr', 'outlook.co.za', 'outlook.sg',
        'outlook.my', 'outlook.ph', 'outlook.th', 'outlook.vn', 'outlook.co.kr',
        'outlook.com.tw', 'outlook.hk', 'outlook.co.nz', 'outlook.ie', 'outlook.co.il',
        'live.com', 'live.co.uk', 'live.fr', 'live.de', 'live.es', 'live.it',
        'live.ca', 'live.com.au', 'live.co.jp', 'live.co.in', 'live.com.br',
        'live.com.mx', 'live.com.ar', 'live.nl', 'live.be', 'live.ch', 'live.at',
        'live.dk', 'live.se', 'live.no', 'live.fi', 'live.pl', 'live.cz',
        'live.hu', 'live.gr', 'live.pt', 'live.ru', 'live.com.tr', 'live.co.za',
        'live.sg', 'live.my', 'live.ph', 'live.th', 'live.vn', 'live.co.kr',
        'live.com.tw', 'live.hk', 'live.co.nz', 'live.ie', 'live.co.il',
        'msn.com', 'msn.co.uk', 'msn.fr', 'msn.de', 'msn.es', 'msn.it',
        'msn.ca', 'msn.com.au', 'msn.co.jp', 'msn.co.in', 'msn.com.br',
        'msn.com.mx', 'msn.com.ar', 'msn.nl', 'msn.be', 'msn.ch', 'msn.at',
        'msn.dk', 'msn.se', 'msn.no', 'msn.fi', 'msn.pl', 'msn.cz',
        'msn.hu', 'msn.gr', 'msn.pt', 'msn.ru', 'msn.com.tr', 'msn.co.za',
        'msn.sg', 'msn.my', 'msn.ph', 'msn.th', 'msn.vn', 'msn.co.kr',
        'msn.com.tw', 'msn.hk', 'msn.co.nz', 'msn.ie', 'msn.co.il'
    }

def is_valid_email_format(email: str) -> bool:
    """Check if the email has a valid format."""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_pattern, email) is not None

def is_target_email(email: str, gmail_domains: Set[str], microsoft_domains: Set[str]) -> bool:
    """Check if email is from Gmail or Microsoft domains."""
    if not is_valid_email_format(email):
        return False
    
    domain = email.split('@')[-1].lower()
    return domain in gmail_domains or domain in microsoft_domains

def parse_combo_line(line: str) -> Tuple[str, str]:
    """Parse a combo line and return email and password."""
    line = line.strip()
    if ':' not in line:
        return '', ''
    
    parts = line.split(':', 1)  # Split only on first colon
    if len(parts) != 2:
        return '', ''
    
    email, password = parts
    return email.strip(), password.strip()

def find_combo_files() -> List[str]:
    """Find all files with 'combos' in the name."""
    combo_files = []
    
    # Search for files with 'combos' in the name (case insensitive)
    patterns = [
        '*combos*',
        '*Combos*',
        '*COMBOS*'
    ]
    
    for pattern in patterns:
        combo_files.extend(glob.glob(pattern))
    
    # Remove duplicates and return sorted list
    return sorted(list(set(combo_files)))

def get_file_size(file_path: str) -> int:
    """Get file size in bytes."""
    try:
        return os.path.getsize(file_path)
    except OSError:
        return 0

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

def extract_valid_combos_from_file(combo_file: str, chunk_size: int = 50000) -> tuple:
    """Extract valid combos from a file and return them along with statistics."""
    gmail_domains = get_gmail_domains()
    microsoft_domains = get_microsoft_domains()
    
    file_size = get_file_size(combo_file)
    print(f"  File size: {format_file_size(file_size)}")
    
    if not os.path.exists(combo_file):
        print(f"  Error: File {combo_file} not found!")
        return set(), 0, 0
    
    valid_combos = set()  # Use set to automatically remove duplicates
    total_lines = 0
    valid_lines = 0
    chunks_processed = 0
    
    try:
        # Process file in chunks
        with open(combo_file, 'r', encoding='utf-8', errors='ignore') as f:
            chunk_lines = []
            
            for line in f:
                total_lines += 1
                chunk_lines.append(line)
                
                # Process chunk when it reaches the specified size
                if len(chunk_lines) >= chunk_size:
                    chunk_valid = process_chunk(chunk_lines, gmail_domains, microsoft_domains)
                    valid_combos.update(chunk_valid)
                    valid_lines += len(chunk_valid)
                    chunks_processed += 1
                    
                    # Progress update
                    print(f"  Processed chunk {chunks_processed} ({len(chunk_lines):,} lines) - "
                          f"Found {len(chunk_valid):,} valid combos - "
                          f"Total processed: {total_lines:,} lines")
                    
                    chunk_lines = []  # Clear chunk
            
            # Process remaining lines
            if chunk_lines:
                chunk_valid = process_chunk(chunk_lines, gmail_domains, microsoft_domains)
                valid_combos.update(chunk_valid)
                valid_lines += len(chunk_valid)
                chunks_processed += 1
                
                print(f"  Processed final chunk {chunks_processed} ({len(chunk_lines):,} lines) - "
                      f"Found {len(chunk_valid):,} valid combos")
        
        print(f"  ✓ Total lines processed: {total_lines:,}")
        print(f"  ✓ Valid Gmail/Microsoft combos found: {valid_lines:,}")
        print(f"  ✓ Unique combos from this file: {len(valid_combos):,}")
        
        if len(valid_combos) == 0:
            print(f"  ⚠️  No valid Gmail/Microsoft combos found in this file!")
        
        # File reduction info
        reduction_percent = ((total_lines - len(valid_combos)) / total_lines * 100) if total_lines > 0 else 0
        print(f"  ✓ File reduction: {reduction_percent:.1f}%")
        
        return valid_combos, total_lines, valid_lines
        
    except Exception as e:
        print(f"  ✗ Error processing {combo_file}: {str(e)}")
        return set(), 0, 0

def process_chunk(chunk_lines: List[str], gmail_domains: Set[str], microsoft_domains: Set[str]) -> Set[str]:
    """Process a chunk of lines and return valid combos."""
    valid_combos = set()
    
    for line in chunk_lines:
        email, password = parse_combo_line(line)
        
        if email and password and is_target_email(email, gmail_domains, microsoft_domains):
            valid_combos.add(f"{email}:{password}")
    
    return valid_combos

def process_combo_files(custom_chunk_size: int = None) -> None:
    """Main function to process all combo files and consolidate into combos.txt."""
    combo_files = find_combo_files()
    
    if not combo_files:
        print("No combo files found!")
        return
    
    print(f"Found {len(combo_files)} combo file(s):")
    total_size = 0
    for file in combo_files:
        file_size = get_file_size(file)
        total_size += file_size
        print(f"  - {file} ({format_file_size(file_size)})")
    
    print(f"\nTotal size to process: {format_file_size(total_size)}")
    
    # Determine chunk size
    if custom_chunk_size:
        chunk_size = custom_chunk_size
        print(f"Using custom chunk size: {chunk_size:,} lines")
    else:
        # Automatic chunk size based on file sizes
        chunk_size = 50000  # Default chunk size
        if total_size > 100 * 1024 * 1024:  # > 100MB
            chunk_size = 100000  # Larger chunks for very large files
            print(f"Using larger chunk size ({chunk_size:,} lines) for large files")
        elif total_size < 10 * 1024 * 1024:  # < 10MB
            chunk_size = 25000  # Smaller chunks for smaller files
            print(f"Using smaller chunk size ({chunk_size:,} lines) for smaller files")
        else:
            print(f"Using default chunk size ({chunk_size:,} lines)")
    
    # Collect all valid combos from all files
    all_valid_combos = set()
    total_lines_processed = 0
    total_valid_found = 0
    files_to_remove = []
    
    for combo_file in combo_files:
        print(f"\nProcessing: {combo_file}")
        valid_combos, lines_processed, valid_found = extract_valid_combos_from_file(combo_file, chunk_size)
        
        all_valid_combos.update(valid_combos)
        total_lines_processed += lines_processed
        total_valid_found += valid_found
        
        # Mark file for removal if it's not the target combos.txt
        if combo_file != "combos.txt":
            files_to_remove.append(combo_file)
    
    # Write all valid combos to combos.txt
    print(f"\n" + "="*50)
    print("CONSOLIDATING ALL COMBOS")
    print("="*50)
    print(f"Total valid combos collected: {len(all_valid_combos):,}")
    print(f"Writing all combos to: combos.txt")
    
    with open("combos.txt", 'w', encoding='utf-8') as f:
        if all_valid_combos:
            for combo in sorted(all_valid_combos):
                f.write(combo + '\n')
    
    # Remove other combo files
    if files_to_remove:
        print(f"\nRemoving {len(files_to_remove)} other combo file(s):")
        for file_to_remove in files_to_remove:
            try:
                os.remove(file_to_remove)
                print(f"  ✓ Removed: {file_to_remove}")
            except OSError as e:
                print(f"  ✗ Failed to remove {file_to_remove}: {e}")
    
    # Final summary
    print(f"\n" + "="*50)
    print("CONSOLIDATION COMPLETE")
    print("="*50)
    print(f"✓ Total lines processed: {total_lines_processed:,}")
    print(f"✓ Total valid combos found: {total_valid_found:,}")
    print(f"✓ Unique combos after deduplication: {len(all_valid_combos):,}")
    print(f"✓ All combos consolidated into: combos.txt")
    
    if files_to_remove:
        print(f"✓ Removed {len(files_to_remove)} other combo files")
    
    reduction_percent = ((total_lines_processed - len(all_valid_combos)) / total_lines_processed * 100) if total_lines_processed > 0 else 0
    print(f"✓ Overall size reduction: {reduction_percent:.1f}%")

def main():
    """Main entry point."""
    import sys
    
    print("=" * 60)
    print("Email Parser - Gmail & Microsoft Account Extractor")
    print("=" * 60)
    print("Searching for combo files and extracting Gmail/Microsoft accounts...")
    print("Supported domains include country-specific variants.")
    print("Processing files in chunks for memory efficiency.")
    print()
    
    # Check for custom chunk size argument
    custom_chunk_size = None
    if len(sys.argv) > 1:
        try:
            custom_chunk_size = int(sys.argv[1])
        except ValueError:
            print("Invalid chunk size argument. Using automatic chunk sizing.")
    
    process_combo_files(custom_chunk_size)
    
    print("\n" + "=" * 60)
    print("Processing complete!")
    print("=" * 60)
    print("\nUsage: python s.py [chunk_size]")
    print("  chunk_size: Optional number of lines to process per chunk (default: auto)")
    print("  Example: python s.py 100000  # Process 100,000 lines per chunk")

if __name__ == "__main__":
    main()
# XTools FFI Integration
import json

def process_file_ffi(file_path: str) -> str:
    """Parse emails via FFI"""
    try:
        if not os.path.exists(file_path):
            return json.dumps({"success": False, "error": f"File not found: {file_path}"})
        
        gmail_domains = get_gmail_domains()
        microsoft_domains = get_microsoft_domains()
        
        gmail_count = 0
        microsoft_count = 0
        total = 0
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                total += 1
                email, password = parse_combo_line(line)
                if email and is_target_email(email, gmail_domains, microsoft_domains):
                    domain = email.split('@')[-1].lower()
                    if domain in gmail_domains:
                        gmail_count += 1
                    elif domain in microsoft_domains:
                        microsoft_count += 1
        
        return json.dumps({
            "success": True,
            "total": total,
            "gmail": gmail_count,
            "microsoft": microsoft_count
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(process_file_ffi(sys.argv[1]))
