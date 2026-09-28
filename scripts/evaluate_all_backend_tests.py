"""
WefyLabs Phase 0.5 — Comprehensive Backend Test Suite Evaluator
Runs all test_*.py files in apps/api/tests/, measures durations,
and captures exact counts for PHASE05_BACKEND_TEST_REPORT.md.
"""
import sys
import os
import time
import subprocess
import pathlib
import json
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "apps" / "api"
TESTS_DIR = API_DIR / "tests"

test_files = sorted(list(TESTS_DIR.glob("test_*.py")))

results = []
total_collected = 0
total_passed = 0
total_failed = 0
total_skipped = 0
total_errors = 0
start_time_all = time.time()

print(f"Starting execution of {len(test_files)} backend test files...")

passed_pattern = re.compile(r"(\d+)\s+passed")
failed_pattern = re.compile(r"(\d+)\s+failed")
skipped_pattern = re.compile(r"(\d+)\s+skipped")
error_pattern = re.compile(r"(\d+)\s+errors?")
collected_pattern = re.compile(r"collected\s+(\d+)\s+items?")

for idx, tf in enumerate(test_files, 1):
    rel_path = tf.relative_to(REPO_ROOT).as_posix()
    t0 = time.time()
    
    env = os.environ.copy()
    env["PYTHONPATH"] = str(API_DIR)
    env["ENV"] = "testing"
    
    cmd = [
        sys.executable,
        "-m", "pytest",
        str(tf),
        "-q",
        "--tb=short"
    ]
    
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(REPO_ROOT),
            env=env,
            stdin=subprocess.DEVNULL
        )
        duration = round(time.time() - t0, 2)
        out = proc.stdout + "\n" + proc.stderr
        
        # Parse counts
        p_match = passed_pattern.search(out)
        f_match = failed_pattern.search(out)
        s_match = skipped_pattern.search(out)
        e_match = error_pattern.search(out)
        c_match = collected_pattern.search(out)
        
        p = int(p_match.group(1)) if p_match else 0
        f = int(f_match.group(1)) if f_match else 0
        s = int(s_match.group(1)) if s_match else 0
        e = int(e_match.group(1)) if e_match else 0
        c = int(c_match.group(1)) if c_match else (p + f + s + e)
        
        status = "PASS" if (proc.returncode == 0 and f == 0 and e == 0) else "FAIL"
        
        total_collected += c
        total_passed += p
        total_failed += f
        total_skipped += s
        total_errors += e
        
        results.append({
            "index": idx,
            "file": tf.name,
            "path": rel_path,
            "status": status,
            "collected": c,
            "passed": p,
            "failed": f,
            "skipped": s,
            "errors": e,
            "duration": duration,
            "output_snippet": out[-300:].strip() if status == "FAIL" else ""
        })
        
        print(f"[{idx}/{len(test_files)}] {tf.name:<50} | {status} | P:{p} F:{f} S:{s} E:{e} ({duration}s)")
        sys.stdout.flush()
        
    except subprocess.TimeoutExpired:
        duration = round(time.time() - t0, 2)
        print(f"[{idx}/{len(test_files)}] {tf.name:<50} | TIMEOUT ({duration}s)")
        results.append({
            "index": idx,
            "file": tf.name,
            "path": rel_path,
            "status": "TIMEOUT",
            "collected": 0,
            "passed": 0,
            "failed": 1,
            "skipped": 0,
            "errors": 1,
            "duration": duration,
            "output_snippet": "Timed out after 120s"
        })
        total_errors += 1

total_duration = round(time.time() - start_time_all, 2)
summary = {
    "total_files": len(test_files),
    "total_collected": total_collected,
    "total_passed": total_passed,
    "total_failed": total_failed,
    "total_skipped": total_skipped,
    "total_errors": total_errors,
    "total_duration_seconds": total_duration,
    "results": results
}

output_json = REPO_ROOT / "scripts" / "test_evaluation_results.json"
output_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(f"\n==========================================")
print(f"EVALUATION COMPLETE in {total_duration}s")
print(f"Collected: {total_collected}")
print(f"Passed:    {total_passed}")
print(f"Failed:    {total_failed}")
print(f"Skipped:   {total_skipped}")
print(f"Errors:    {total_errors}")
print(f"Results saved to {output_json}")
print(f"==========================================")
