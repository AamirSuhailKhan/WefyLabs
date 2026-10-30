import subprocess
import sys
import os
import json
import time

def run_test_item(title, category, cmd, target_db, target_rev, env_vars=None, cwd=None):
    print(f"\n=======================================================")
    print(f"[{category}] {title}")
    print(f"Target DB:  {target_db} (Revision: {target_rev})")
    print(f"Command:    {' '.join(cmd)}")
    print(f"=======================================================")
    
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)
        
    start_time = time.time()
    res = subprocess.run(cmd, env=env, cwd=cwd, capture_output=True, text=True)
    duration = time.time() - start_time
    
    # Parse pytest output for counts if pytest
    passed = 0
    failed = 0
    skipped = 0
    total = 0
    
    stdout = res.stdout
    stderr = res.stderr
    
    if "pytest" in " ".join(cmd):
        for line in stdout.splitlines():
            if "passed" in line or "failed" in line:
                import re
                p_match = re.search(r"(\d+)\s+passed", line)
                f_match = re.search(r"(\d+)\s+failed", line)
                s_match = re.search(r"(\d+)\s+skipped", line)
                if p_match: passed = int(p_match.group(1))
                if f_match: failed = int(f_match.group(1))
                if s_match: skipped = int(s_match.group(1))
                total = passed + failed + skipped

    print(f"Exit Code: {res.returncode} | Duration: {duration:.2f}s | Passed: {passed}, Failed: {failed}")
    if res.stdout:
        print("STDOUT TAIL:\n" + res.stdout[-400:])
    if res.stderr:
        print("STDERR TAIL:\n" + res.stderr[-400:])

    return {
        "title": title,
        "category": category,
        "database_target": target_db,
        "alembic_revision": target_rev,
        "command": " ".join(cmd),
        "exit_code": res.returncode,
        "duration_seconds": round(duration, 2),
        "test_counts": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped
        },
        "stdout_tail": stdout[-800:] if stdout else "",
        "stderr_tail": stderr[-800:] if stderr else ""
    }

def main():
    ledger = []

    # 1. Deliberate 0048 Failure Reproduction
    r1 = run_test_item(
        title="Deliberate 0048 Type Divergence Reproduction",
        category="REPRODUCTION_UNMIGRATED_0048",
        cmd=[sys.executable, "scratch/action3_reproduce_on_disposable_0048.py"],
        target_db="PostgreSQL (test_disposable_0048)",
        target_rev="0048_schema_reconciliation_parity"
    )
    ledger.append(r1)

    # 2. Phase 4 Full Migration Readiness Proof (PostgreSQL + asyncpg)
    r2 = run_test_item(
        title="PostgreSQL 0050 Full Operational Readiness Proof",
        category="POSTGRESQL_POST_MIGRATION_0050",
        cmd=[sys.executable, "scratch/phase4_full_migration_readiness_proof.py"],
        target_db="PostgreSQL (test_disposable_phase4)",
        target_rev="0050_broker_subscription_constraint_parity"
    )
    ledger.append(r2)

    # 3. Migration Chain 0048 -> 0050 & Modern Constraint Proof
    r3 = run_test_item(
        title="Migration Chain 0048 -> 0050 & Modern Constraint Validation",
        category="MIGRATION_CHAIN_VALIDATION",
        cmd=[sys.executable, "scratch/test_disposable_chain_0048_to_0050.py"],
        target_db="PostgreSQL (test_disposable_chain_0050)",
        target_rev="0050_broker_subscription_constraint_parity"
    )
    ledger.append(r3)

    # 4. Downgrade Safeguard Verification
    r4 = run_test_item(
        title="Migration 0050 Downgrade Fail-Closed Safeguard Proof",
        category="DOWNGRADE_SAFEGUARD_VERIFICATION",
        cmd=[sys.executable, "scratch/test_downgrade_safeguards_0050.py"],
        target_db="PostgreSQL (test_disposable_downgrade_0050)",
        target_rev="0049_source_attribution_uuid_parity"
    )
    ledger.append(r4)

    # 5. Dedicated SourceAttribution & GUID Validation Suite (12 tests)
    r5 = run_test_item(
        title="SourceAttribution & GUID TypeDecorator Regression Suite",
        category="ORM_TYPE_REGRESSION",
        cmd=[sys.executable, "-m", "pytest", "apps/api/tests/test_source_attribution_regression.py", "-v"],
        target_db="SQLite in-memory + TypeDecorator unit testing",
        target_rev="N/A (Schema models verified)",
        env_vars={"PYTHONPATH": "apps/api"}
    )
    ledger.append(r5)

    # 6. Part 21 Lead Acquisition Suite (73 tests)
    r6 = run_test_item(
        title="Part 21 Lead Acquisition Suite",
        category="CRM_DOMAIN_INTEGRITY",
        cmd=[sys.executable, "-m", "pytest", "apps/api/tests/test_part21_lead_acquisition.py", "-q"],
        target_db="SQLite in-memory engine",
        target_rev="N/A (Model constraints verified)",
        env_vars={"PYTHONPATH": "apps/api"}
    )
    ledger.append(r6)

    # 7. Database Safety Guards Suite (14 tests)
    r7 = run_test_item(
        title="Database Safety Guards Suite",
        category="SAFETY_GUARDS_VERIFICATION",
        cmd=[sys.executable, "-m", "pytest", "apps/api/tests/test_database_safety_guards.py", "-q"],
        target_db="PostgreSQL / Alembic Safety Harness",
        target_rev="Multi-head inspection",
        env_vars={"PYTHONPATH": "apps/api"}
    )
    ledger.append(r7)

    # 8. Part 8 Final Integration Suite (64 tests)
    r8 = run_test_item(
        title="Part 8 Final Integration Suite",
        category="INTEGRATION_SUITE",
        cmd=[sys.executable, "-m", "pytest", "apps/api/tests/test_part8_final_integration.py", "-q"],
        target_db="FastAPI TestClient + In-memory DB",
        target_rev="0050_broker_subscription_constraint_parity",
        env_vars={"PYTHONPATH": "apps/api"}
    )
    ledger.append(r8)

    # 9. Part 11 Revenue Intelligence Suite (73 tests)
    r9 = run_test_item(
        title="Part 11 Revenue Intelligence Suite",
        category="REVENUE_INTELLIGENCE",
        cmd=[sys.executable, "-m", "pytest", "apps/api/tests/test_part11_revenue_intelligence.py", "-q"],
        target_db="Revenue Intelligence Simulation Engine",
        target_rev="N/A (Calculations verified)",
        env_vars={"PYTHONPATH": "apps/api"}
    )
    ledger.append(r9)

    with open("scratch/phase6_regression_ledger.json", "w") as f:
        json.dump(ledger, f, indent=2)
    print("\nPhase 6 Regression Execution Complete. Ledger saved to scratch/phase6_regression_ledger.json")

if __name__ == "__main__":
    main()

