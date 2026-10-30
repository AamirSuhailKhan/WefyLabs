"""
Phase 14 Complete Backend Regression Ledger Runner
===================================================
Executes the full supported backend test suite (222 files, 3,359 collected cases)
in non-overlapping sequential batches, recording:
- File name
- Batch ID
- Expected collected count
- Collected count
- Passed count
- Failed count
- Skipped count
- Error count
- Duration (seconds)
- Exit code
- Status (PASS / FAIL / SKIPPED / EMPTY)
- Failure details

Generates machine-readable ledger: scratch/backend_regression_ledger_p14.json
Raw JUnit XMLs saved to: scratch/batch_xmls_p14/batch_XX.xml
Verifies 100% of discovered supported test cases with zero gaps and zero overlaps.
"""
import os
import sys
import subprocess
import json
import time
import xml.etree.ElementTree as ET

API_DIR = os.path.abspath("apps/api")
SCRATCH_DIR = os.path.abspath("scratch")
XML_DIR = os.path.join(SCRATCH_DIR, "batch_xmls_p14")
LEDGER_PATH = os.path.join(SCRATCH_DIR, "backend_regression_ledger_p14.json")
INVENTORY_PATH = os.path.join(SCRATCH_DIR, "test_inventory_p14.json")

BATCH_SIZE = 10  # 23 batches for 222 files

def parse_junit_xml(xml_path, batch_files):
    file_results = {
        f: {
            "collected": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "error": 0,
            "duration": 0.0,
            "failures": []
        }
        for f in batch_files
    }
    
    if not os.path.exists(xml_path):
        return file_results

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for tc in root.iter("testcase"):
            classname = tc.get("classname", "")
            tc_name = tc.get("name", "")
            tc_time = float(tc.get("time", 0.0))
            
            parts = classname.split(".")
            mod = parts[1] if parts[0] == "tests" and len(parts) > 1 else parts[0]
            matched_file = f"tests/{mod}.py"
            
            if matched_file not in file_results:
                # Try fallback matching
                for bf in batch_files:
                    bf_base = os.path.basename(bf).replace(".py", "")
                    if bf_base == mod or bf.endswith(f"/{mod}.py") or bf.endswith(f"\\{mod}.py"):
                        matched_file = bf
                        break

            if matched_file in file_results:
                fr = file_results[matched_file]
                fr["collected"] += 1
                fr["duration"] += tc_time
                fail_elem = tc.find("failure")
                err_elem = tc.find("error")
                skip_elem = tc.find("skipped")
                
                if fail_elem is not None:
                    fr["failed"] += 1
                    fr["failures"].append({"test": tc_name, "message": fail_elem.get("message", "")[:200]})
                elif err_elem is not None:
                    fr["error"] += 1
                    fr["failures"].append({"test": tc_name, "error": err_elem.get("message", "")[:200]})
                elif skip_elem is not None:
                    fr["skipped"] += 1
                else:
                    fr["passed"] += 1
            else:
                print(f"Warning: could not map testcase '{classname}::{tc_name}' to batch files: {batch_files}")
    except Exception as e:
        print(f"Error parsing XML {xml_path}: {e}")

    return file_results

def run_regression():
    os.makedirs(XML_DIR, exist_ok=True)
    
    with open(INVENTORY_PATH, "r", encoding="utf-8") as f:
        inv = json.load(f)
        
    all_files = sorted(list(inv["files"].keys()))
    total_files = len(all_files)
    total_expected_cases = inv["total_tests"]
    
    print(f"============================================================")
    print(f"PHASE 14 BACKEND REGRESSION EXECUTION")
    print(f"Total Discovered Files: {total_files}")
    print(f"Total Expected Tests:   {total_expected_cases}")
    print(f"Batch Size:             {BATCH_SIZE} files/batch")
    print(f"============================================================")

    # Partition files into non-overlapping batches
    batches = []
    for i in range(0, total_files, BATCH_SIZE):
        batches.append(all_files[i:i + BATCH_SIZE])
        
    print(f"Partitioned into {len(batches)} non-overlapping batches.\n")

    # Load existing ledger if present to support resume
    ledger = {}
    if os.path.exists(LEDGER_PATH):
        try:
            with open(LEDGER_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                for entry in data.get("files_ledger", []):
                    ledger[entry["file"]] = entry
        except Exception:
            ledger = {}

    batch_timings = []
    total_start_time = time.time()

    for idx, batch_files in enumerate(batches, 1):
        batch_id = f"batch_{idx:02d}"
        xml_path = os.path.join(XML_DIR, f"{batch_id}.xml")
        
        # Check if all files in this batch already have recorded results and XML exists
        if os.path.exists(xml_path) and all(f in ledger and ledger[f].get("status") in ("PASS", "FAIL", "SKIPPED") for f in batch_files):
            print(f"[{batch_id} - {idx}/{len(batches)}] Already completed with valid XML. Skipping re-run.")
            continue
            
        print(f"[{batch_id} - {idx}/{len(batches)}] Executing {len(batch_files)} files...")
        t0 = time.time()
        # batch_files are already "tests/test_xxx.py"
        cmd = [sys.executable, "-m", "pytest"] + batch_files + [f"--junitxml={xml_path}", "-q"]
        
        proc = subprocess.run(cmd, cwd=API_DIR, capture_output=True, text=True)
        dur = time.time() - t0
        batch_timings.append((batch_id, dur))
        
        file_stats = parse_junit_xml(xml_path, batch_files)
        
        batch_passed = 0
        batch_failed = 0
        batch_skipped = 0
        batch_error = 0
        batch_collected = 0
        
        for fname in batch_files:
            stats = file_stats[fname]
            expected_c = inv["files"].get(fname, 0)
            collected_c = stats["collected"]
            
            entry_status = "PASS" if stats["failed"] == 0 and stats["error"] == 0 else "FAIL"
            if collected_c == 0 and expected_c == 0:
                entry_status = "EMPTY"
            elif stats["skipped"] == collected_c and collected_c > 0:
                entry_status = "SKIPPED"
                
            entry = {
                "file": fname,
                "batch": batch_id,
                "expected_collected": expected_c,
                "collected": collected_c,
                "passed": stats["passed"],
                "failed": stats["failed"],
                "skipped": stats["skipped"],
                "error": stats["error"],
                "duration": round(stats["duration"], 4),
                "exit_code": proc.returncode if (stats["failed"] > 0 or stats["error"] > 0) else 0,
                "status": entry_status,
                "failures": stats["failures"]
            }
            ledger[fname] = entry
            
            batch_passed += stats["passed"]
            batch_failed += stats["failed"]
            batch_skipped += stats["skipped"]
            batch_error += stats["error"]
            batch_collected += collected_c

        print(f"   -> Result: {batch_collected} tests in {dur:.2f}s | Passed: {batch_passed}, Failed: {batch_failed}, Skipped: {batch_skipped}, Error: {batch_error} | Code: {proc.returncode}")

        # Progressively persist ledger
        _save_ledger(ledger, total_files, total_expected_cases, time.time() - total_start_time)

    total_duration = time.time() - total_start_time
    final_artifact = _save_ledger(ledger, total_files, total_expected_cases, total_duration)

    print("\n============================================================")
    print("BACKEND REGRESSION RECONCILIATION SUMMARY")
    print(f"Total Discovered Files:  {final_artifact['total_files_discovered']}")
    print(f"Total Files in Ledger:   {final_artifact['total_files_reconciled']}")
    print(f"Total Collected Tests:   {final_artifact['total_tests_collected']}")
    print(f"Total Tests Passed:      {final_artifact['total_tests_passed']}")
    print(f"Total Tests Failed:      {final_artifact['total_tests_failed']}")
    print(f"Total Tests Skipped:     {final_artifact['total_tests_skipped']}")
    print(f"Total Tests Error:       {final_artifact['total_tests_error']}")
    print(f"Overall Duration:        {final_artifact['total_duration_seconds']:.2f}s (~{final_artifact['total_duration_seconds']/60:.2f}m)")
    print(f"Overall Suite Verdict:   {final_artifact['verdict']}")
    print(f"Ledger File Saved:       {LEDGER_PATH}")
    print("============================================================")
    return final_artifact

def _save_ledger(ledger, total_files, total_expected_cases, elapsed_sec):
    files_list = [ledger[f] for f in sorted(list(ledger.keys()))]
    total_col = sum(e["collected"] for e in files_list)
    total_pas = sum(e["passed"] for e in files_list)
    total_fai = sum(e["failed"] for e in files_list)
    total_ski = sum(e["skipped"] for e in files_list)
    total_err = sum(e["error"] for e in files_list)
    
    verdict = "PASS" if total_fai == 0 and total_err == 0 and len(files_list) == total_files and total_col == total_expected_cases else "FAIL"
    
    artifact = {
        "phase": "PHASE_14",
        "total_files_discovered": total_files,
        "total_files_reconciled": len(files_list),
        "total_tests_collected": total_col,
        "total_expected_cases": total_expected_cases,
        "total_tests_passed": total_pas,
        "total_tests_failed": total_fai,
        "total_tests_skipped": total_ski,
        "total_tests_error": total_err,
        "total_duration_seconds": round(elapsed_sec, 2),
        "verdict": verdict,
        "files_ledger": files_list
    }
    
    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
        
    return artifact

if __name__ == "__main__":
    run_regression()
