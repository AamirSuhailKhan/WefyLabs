import os
import sys
import time
import json
import subprocess

SUITES = [
    {
        "id": "S1",
        "name": "Database Bootstrap & Migrations",
        "files": ["apps/api/tests/test_database_bootstrap_and_migrations.py"]
    },
    {
        "id": "S2",
        "name": "OAuth Security & Redis Rate Limiting",
        "files": [
            "apps/api/tests/test_oauth_multiworker_security.py",
            "apps/api/tests/test_redis_rate_limiter.py"
        ]
    },
    {
        "id": "S3",
        "name": "Tenant Boundary & Isolation Security",
        "files": [
            "apps/api/tests/test_tenant_isolation_security.py",
            "apps/api/tests/test_tenant_matrix_security.py",
            "apps/api/tests/test_p0_tenant_isolation_remediation.py"
        ]
    },
    {
        "id": "S4",
        "name": "Webhook Security & Signature Hardening",
        "files": [
            "apps/api/tests/test_webhook_security.py",
            "apps/api/tests/test_whatsapp_webhook_security_hardening.py"
        ]
    },
    {
        "id": "S5",
        "name": "Razorpay Production & Billing Subscriptions",
        "files": [
            "apps/api/tests/test_razorpay_production.py",
            "apps/api/tests/test_master_build_13_billing.py"
        ]
    },
    {
        "id": "S6",
        "name": "Autonomous Sales Loop & Stage 1 Pilot Safety",
        "files": [
            "apps/api/tests/test_part21_8_autonomous_sales_loop.py",
            "apps/api/tests/test_phase2c_production_pilot.py"
        ]
    },
    {
        "id": "S7",
        "name": "Sales Pipeline & Deal Lifecycle",
        "files": [
            "apps/api/tests/test_master_build_08_sales_pipeline.py",
            "apps/api/tests/test_part18_deal_lifecycle.py"
        ]
    },
    {
        "id": "S8",
        "name": "Security Architecture & High-Value Product",
        "files": [
            "apps/api/tests/test_stage_b_c_security_architecture_consolidation.py",
            "apps/api/tests/test_stage_f_high_value_product_completion.py"
        ]
    },
    {
        "id": "S9",
        "name": "Master Intelligence Graph & Telemetry Security",
        "files": [
            "apps/api/tests/test_master_build_14_intelligence.py",
            "apps/api/tests/test_master_build_14_security.py"
        ]
    }
]

def run_suite(suite):
    print(f"\n=======================================================")
    print(f"Running Suite {suite['id']}: {suite['name']}")
    print(f"Files: {', '.join(suite['files'])}")
    print(f"=======================================================")
    
    cmd = [sys.executable, "-m", "pytest"] + suite["files"] + ["-v", "--tb=short"]
    start = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    duration = time.time() - start
    
    output = proc.stdout + "\n" + proc.stderr
    print(output)
    
    # Parse results
    passed = 0
    failed = 0
    skipped = 0
    errors = 0
    collected = 0
    
    for line in output.splitlines():
        if "collected " in line and "items" in line:
            parts = line.split("collected ")
            if len(parts) > 1:
                num_str = parts[1].split()[0]
                if num_str.isdigit():
                    collected = int(num_str)
        if "=====" in line and ("passed" in line or "failed" in line or "skipped" in line or "error" in line):
            # Summary line
            tokens = line.replace("=", "").strip().split(",")
            for tok in tokens:
                tok = tok.strip()
                if "passed" in tok:
                    p = tok.split()[0]
                    if p.isdigit(): passed = int(p)
                elif "failed" in tok:
                    f = tok.split()[0]
                    if f.isdigit(): failed = int(f)
                elif "skipped" in tok:
                    s = tok.split()[0]
                    if s.isdigit(): skipped = int(s)
                elif "error" in tok:
                    e = tok.split()[0]
                    if e.isdigit(): errors = int(e)
                    
    return {
        "suite_id": suite["id"],
        "name": suite["name"],
        "files": suite["files"],
        "exit_code": proc.returncode,
        "duration_seconds": round(duration, 2),
        "collected": collected,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "errors": errors
    }

def main():
    start_total = time.time()
    results = []
    
    for s in SUITES:
        res = run_suite(s)
        results.append(res)
        if res["exit_code"] != 0:
            print(f"FAILED SUITE {s['id']} with exit code {res['exit_code']}")
            
    total_duration = time.time() - start_total
    
    total_files = sum(len(s["files"]) for s in SUITES)
    total_collected = sum(r["collected"] for r in results)
    total_passed = sum(r["passed"] for r in results)
    total_failed = sum(r["failed"] for r in results)
    total_skipped = sum(r["skipped"] for r in results)
    total_errors = sum(r["errors"] for r in results)
    
    summary = {
        "total_suites": len(SUITES),
        "total_files": total_files,
        "total_collected": total_collected,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "total_skipped": total_skipped,
        "total_errors": total_errors,
        "total_duration_seconds": round(total_duration, 2),
        "suites": results
    }
    
    artifact_path = os.path.abspath("scratch/backend_regression_results_p10.json")
    with open(artifact_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        
    print("\n" + "=" * 80)
    print("PHASE 10 FULL BACKEND REGRESSION SUMMARY")
    print("=" * 80)
    print(f"Total Suites:        {summary['total_suites']}")
    print(f"Total Files Covered: {summary['total_files']}")
    print(f"Total Collected:     {summary['total_collected']}")
    print(f"Total Passed:        {summary['total_passed']}")
    print(f"Total Failed:        {summary['total_failed']}")
    print(f"Total Skipped:       {summary['total_skipped']}")
    print(f"Total Errors:        {summary['total_errors']}")
    print(f"Total Duration:      {summary['total_duration_seconds']}s (~{round(total_duration/60, 2)}m)")
    print(f"Artifact saved:      {artifact_path}")
    print("=" * 80)

if __name__ == "__main__":
    main()
