# delete_txt_files.py
import os
from pathlib import Path

# Get the directory where the script is running
current_folder = Path(__file__).parent

print(f"Looking for .txt files in: {current_folder.resolve()}")
print("The following .txt files will be DELETED permanently:")

# Find all .txt files
txt_files = list(current_folder.glob("*.txt"))

if not txt_files:
    print("No .txt files found. Nothing to delete.")
else:
    for file in txt_files:
        print(f"  - {file.name}")

    # Double confirmation to avoid accidents
    confirm = input("\nType 'DELETE' to confirm permanent deletion: ")
    
    if confirm == "DELETE":
        deleted_count = 0
        for file in txt_files:
            try:
                file.unlink()  # Deletes the file
                print(f"Deleted: {file.name}")
                deleted_count += 1
            except Exception as e:
                print(f"Could not delete {file.name}: {e}")
        
        print(f"\nDone! {deleted_count} file(s) deleted.")
    else:
        print("Operation cancelled. No files were deleted.")
# XTools FFI Integration
import json

def process_file_ffi(file_path: str, pattern: str = "") -> str:
    """Remove lines matching pattern via FFI"""
    try:
        if not os.path.exists(file_path):
            return json.dumps({"success": False, "error": f"File not found: {file_path}"})
        
        if not pattern:
            return json.dumps({"success": False, "error": "No pattern provided"})
        
        output_file = file_path + ".removed"
        removed_count = 0
        kept_count = 0
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f_in:
            with open(output_file, 'w', encoding='utf-8') as f_out:
                for line in f_in:
                    if pattern in line:
                        removed_count += 1
                    else:
                        f_out.write(line)
                        kept_count += 1
        
        return json.dumps({
            "success": True,
            "original": removed_count + kept_count,
            "removed": removed_count,
            "kept": kept_count,
            "output": output_file
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        pattern = sys.argv[2] if len(sys.argv) > 2 else ""
        print(process_file_ffi(sys.argv[1], pattern))
