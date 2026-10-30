import os
import sys
import subprocess
import json
import xml.etree.ElementTree as ET

API_DIR = os.path.abspath("apps/api")
TESTS_DIR = os.path.join(API_DIR, "tests")

def inventory_test_files():
    files = sorted([f for f in os.listdir(TESTS_DIR) if f.startswith("test_") and f.endswith(".py")])
    return files

if __name__ == "__main__":
    files = inventory_test_files()
    print(f"Total discovered test files: {len(files)}")
    
    # Run pytest --collect-only with -q
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q"]
    res = subprocess.run(cmd, cwd=API_DIR, capture_output=True, text=True)
    lines = res.stdout.splitlines()
    
    test_cases_by_file = {}
    for line in lines:
        if "::" in line:
            parts = line.strip().split("::")
            fpath = parts[0].replace("\\", "/")
            fname = os.path.basename(fpath)
            test_cases_by_file.setdefault(fname, []).append(parts[-1])
            
    print(f"Total files with collected tests: {len(test_cases_by_file)}")
    total_cases = sum(len(c) for c in test_cases_by_file.values())
    print(f"Total collected test cases: {total_cases}")
    
    # Save inventory
    with open("scratch/test_inventory_p12.json", "w") as f:
        json.dump({
            "total_files": len(files),
            "total_collected": total_cases,
            "files": {f: len(test_cases_by_file.get(f, [])) for f in files}
        }, f, indent=2)
    print("Saved scratch/test_inventory_p12.json")
