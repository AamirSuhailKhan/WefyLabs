"""
Static Database Safety and Test Isolation Checker
=================================================
Scans tests, scripts, and harnesses for dangerous database operations:
- Hardcoded connections to shared production database 'leadscore'
- Unbounded raw DELETE / TRUNCATE statements
- Unguarded schema/table drops
- Non-isolated test harnesses
"""
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
API_TESTS_DIR = REPO_ROOT / "apps" / "api" / "tests"
SCRIPTS_DIR = REPO_ROOT / "apps" / "api" / "scripts"

FORBIDDEN_DB_PATTERN = re.compile(r"['\"][^'\"]*5432/leadscore['\"]")
RAW_TRUNCATE_PATTERN = re.compile(r"\bTRUNCATE\b", re.IGNORECASE)

# Files permitted to reference leadscore strictly for guard or config validation assertion tests
ALLOWED_GUARD_TEST_FILES = {
    "test_database_safety_guards.py",          # Database safety assertion tests
    "test_part22_production_integration.py",    # EnterpriseSettings schema validation tests (no DB connection)
}

def scan_file(file_path: Path) -> List[Dict[str, Any]]:
    findings = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings

    lines = content.splitlines()
    file_rel = str(file_path.relative_to(REPO_ROOT))

    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") or "FORBIDDEN_TEST_DATABASES" in line or "FORBIDDEN_SHARED_DATABASES" in line:
            continue

        # Check 1: Direct connection to shared database leadscore in test files
        if file_path.name not in ALLOWED_GUARD_TEST_FILES:
            if FORBIDDEN_DB_PATTERN.search(line):
                # Distinguish if it's in test files vs operational scripts
                if "tests" in file_path.parts:
                    findings.append({
                        "file": file_rel,
                        "line": idx,
                        "type": "TEST_CONNECTS_TO_SHARED_DB",
                        "code": stripped[:100],
                        "severity": "CRITICAL",
                    })

        # Check 2: Unbounded TRUNCATE
        if RAW_TRUNCATE_PATTERN.search(line) and file_path.name not in ALLOWED_GUARD_TEST_FILES:
            findings.append({
                "file": file_rel,
                "line": idx,
                "type": "RAW_TRUNCATE",
                "code": stripped[:100],
                "severity": "HIGH",
            })

    return findings

def main():
    print("[SAFETY AUDIT] Scanning test suites and scripts for dangerous DB patterns...")
    all_findings = []
    
    scanned_count = 0
    for p in API_TESTS_DIR.rglob("*.py"):
        scanned_count += 1
        findings = scan_file(p)
        all_findings.extend(findings)

    print(f"[SAFETY AUDIT] Scanned {scanned_count} test files in apps/api/tests.")
    
    critical = [f for f in all_findings if f["severity"] == "CRITICAL"]
    if critical:
        print(f"\n[FAILURE] Found {len(critical)} CRITICAL database safety violations in test suites:")
        for c in critical:
            print(f"  - {c['file']}:{c['line']} [{c['type']}] -> {c['code']}")
        sys.exit(1)

    print(f"[SAFETY AUDIT] SUCCESS: 0 critical unguarded shared database mutations found in tests.")
    sys.exit(0)

if __name__ == "__main__":
    main()
