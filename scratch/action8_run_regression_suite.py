import asyncio
import subprocess
import sys
import os
import json
import time

def run_cmd(name: str, cmd: list, db_target: str, env_vars: dict = None, cwd: str = None):
    print(f"\n=======================================================")
    print(f"RUNNING: {name}")
    print(f"TARGET:  {db_target}")
    print(f"CMD:     {' '.join(cmd)}")
    print(f"=======================================================")
    
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)
        
    start_time = time.time()
    res = subprocess.run(cmd, env=env, cwd=cwd, capture_output=True, text=True)
    duration = time.time() - start_time
    
    print(f"EXIT CODE: {res.returncode} (Duration: {duration:.2f}s)")
    if res.stdout:
        print("STDOUT TAIL:\n" + res.stdout[-600:])
    if res.stderr:
        print("STDERR TAIL:\n" + res.stderr[-600:])
        
    return {
        "test_name": name,
        "database_target": db_target,
        "command": " ".join(cmd),
        "exit_code": res.returncode,
        "duration_seconds": round(duration, 2),
        "stdout": res.stdout,
        "stderr": res.stderr
    }

def main():
    ledger = []

    # -------------------------------------------------------------
    # SUITE 1: Tests Against Schema 0048 (Disposable Clone of leadscore 0048)
    # Demonstrates unmigrated production compatibility status
    # -------------------------------------------------------------
    r1 = run_cmd(
        name="Reproduction of 0048 Type Divergence on Disposable PostgreSQL",
        cmd=[sys.executable, "scratch/action3_reproduce_on_disposable_0048.py"],
        db_target="PostgreSQL (test_disposable_0048, Revision 0048)"
    )
    ledger.append(r1)

    # -------------------------------------------------------------
    # SUITE 2: Tests Against Schema 0049 (PostgreSQL + asyncpg)
    # Proves revised application works natively against 0049
    # -------------------------------------------------------------
    r2 = run_cmd(
        name="Real PostgreSQL 0049 + asyncpg End-to-End Validation",
        cmd=[sys.executable, "scratch/action4_prove_revised_app_on_0049_postgres.py"],
        db_target="PostgreSQL (leadscore_pilot, Revision 0049)"
    )
    ledger.append(r2)

    # -------------------------------------------------------------
    # SUITE 3: Migration 0049 Upgrade & Verification
    # Proves migration converts columns, preserves data, establishes FKs
    # -------------------------------------------------------------
    r3 = run_cmd(
        name="Migration 0049 Upgrade, Conversion & Invariant Verification",
        cmd=[sys.executable, "scratch/action7_confirm_migration_0049.py"],
        db_target="PostgreSQL (test_disposable_migration_0049, 0048 -> 0049)"
    )
    ledger.append(r3)

    # -------------------------------------------------------------
    # SUITE 4: SourceAttribution Dedicated Regression Suite (12 tests)
    # -------------------------------------------------------------
    r4 = run_cmd(
        name="SourceAttribution Dedicated Regression Suite (12 tests)",
        cmd=[sys.executable, "-m", "pytest", "apps/api/tests/test_source_attribution_regression.py", "-v"],
        db_target="SQLite isolated memory engine + ORM validation",
        env_vars={"PYTHONPATH": "apps/api"}
    )
    ledger.append(r4)

    # -------------------------------------------------------------
    # SUITE 5: Part 21 Lead Acquisition Suite (73 tests)
    # -------------------------------------------------------------
    r5 = run_cmd(
        name="Part 21 Lead Acquisition Suite (73 tests)",
        cmd=[sys.executable, "-m", "pytest", "apps/api/tests/test_part21_lead_acquisition.py", "-q"],
        db_target="SQLite isolated memory engine",
        env_vars={"PYTHONPATH": "apps/api"}
    )
    ledger.append(r5)

    # -------------------------------------------------------------
    # SUITE 6: Database Safety Guards Suite (14 tests)
    # -------------------------------------------------------------
    r6 = run_cmd(
        name="Database Safety Guards Suite (14 tests)",
        cmd=[sys.executable, "-m", "pytest", "apps/api/tests/test_database_safety_guards.py", "-q"],
        db_target="PostgreSQL / Alembic Safety Harness",
        env_vars={"PYTHONPATH": "apps/api"}
    )
    ledger.append(r6)

    # -------------------------------------------------------------
    # SUITE 7: Part 8 Final Integration Suite (64 tests)
    # -------------------------------------------------------------
    r7 = run_cmd(
        name="Part 8 Final Integration Suite (64 tests)",
        cmd=[sys.executable, "-m", "pytest", "apps/api/tests/test_part8_final_integration.py", "-q"],
        db_target="Application FastAPITestClient + In-memory DB",
        env_vars={"PYTHONPATH": "apps/api"}
    )
    ledger.append(r7)

    # Save ledger
    with open("scratch/action8_regression_ledger.json", "w") as f:
        json.dump(ledger, f, indent=2)
    print("\nAction 8 Execution Complete. Full ledger saved to scratch/action8_regression_ledger.json")

if __name__ == "__main__":
    main()

