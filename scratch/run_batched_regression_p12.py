import os
import sys
import subprocess
import json
import time
import xml.etree.ElementTree as ET

API_DIR = os.path.abspath("apps/api")

def run_batch_and_record(batch_idx, batch_files, xml_output_path):
    rel_paths = [os.path.join("tests", f) for f in batch_files]
    cmd = [sys.executable, "-m", "pytest"] + rel_paths + [f"--junitxml={xml_output_path}", "-q"]
    
    t0 = time.time()
    res = subprocess.run(cmd, cwd=API_DIR, capture_output=True, text=True)
    duration = time.time() - t0
    
    file_results = {f: {"collected": 0, "passed": 0, "failed": 0, "skipped": 0, "error": 0, "duration": 0.0} for f in batch_files}
    
    if os.path.exists(xml_output_path):
        tree = ET.parse(xml_output_path)
        root = tree.getroot()
        for tc in root.iter("testcase"):
            classname = tc.get("classname", "")
            tc_time = float(tc.get("time", 0.0))
            
            # Map classname to file
            # Example: classname="tests.test_ai_migration" -> "test_ai_migration.py"
            parts = classname.split(".")
            # Look for matching file in batch_files
            matched_file = None
            for f in batch_files:
                base = f.replace(".py", "")
                if base in parts or classname.startswith(f"tests.{base}"):
                    matched_file = f
                    break
            if not matched_file:
                # Fallback to matching by file attribute if present
                f_attr = tc.get("file", "")
                if f_attr:
                    matched_file = os.path.basename(f_attr)
                    
            if matched_file and matched_file in file_results:
                fr = file_results[matched_file]
                fr["collected"] += 1
                fr["duration"] += tc_time
                if tc.find("failure") is not None:
                    fr["failed"] += 1
                elif tc.find("error") is not None:
                    fr["error"] += 1
                elif tc.find("skipped") is not None:
                    fr["skipped"] += 1
                else:
                    fr["passed"] += 1
            else:
                print(f"Warning: could not map testcase {classname} to batch file")
                
    return res.returncode, duration, file_results

if __name__ == "__main__":
    with open("scratch/test_inventory_p12.json") as f:
        inv = json.load(f)
    all_files = sorted(list(inv["files"].keys()))
    print(f"Loaded {len(all_files)} files from inventory. Total expected cases: {inv['total_collected']}")
    
    # Test batch 1 with first 5 files
    test_files = all_files[:5]
    print(f"Testing runner on first 5 files: {test_files}")
    ret, dur, fr = run_batch_and_record(1, test_files, os.path.abspath("scratch/test_batch_1.xml"))
    print(f"Return code: {ret}, Duration: {dur:.2f}s")
    print("File results:", json.dumps(fr, indent=2))
