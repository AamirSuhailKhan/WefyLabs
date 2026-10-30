"""Run the current supported API pytest suite in non-overlapping JUnit-backed batches."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "api"
OUT = ROOT / "scratch"
XML = OUT / "batch_xmls_p14"
PYTHON = Path(os.environ.get("P14_PYTHON", sys.executable))
BATCH_SIZE = 10


def command(args):
    return [str(PYTHON), "-m", "pytest", *args]


def collected_inventory():
    result = subprocess.run(command(["--collect-only", "-q"]), cwd=API, text=True, capture_output=True)
    (OUT / "pytest_collect_p14_raw.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
    paths = []
    for line in result.stdout.splitlines():
        if "::" in line and line.startswith("tests/") or line.startswith("tests\\"):
            paths.append(line.split("::", 1)[0].replace("\\", "/"))
    return result, Counter(paths)


def parse_junit(path):
    results = defaultdict(lambda: Counter(collected=0, passed=0, failed=0, skipped=0, error=0))
    root = ET.parse(path).getroot()
    for node in root.iter("testcase"):
        classname = (node.get("classname") or "").replace("\\", "/")
        file_name = classname.replace(".", "/") + ".py"
        # Pytest's classname omits the test method and matches test module paths.
        stats = results[file_name]
        stats["collected"] += 1
        stats["skipped" if node.find("skipped") is not None else "error" if node.find("error") is not None else "failed" if node.find("failure") is not None else "passed"] += 1
    return results


def main():
    XML.mkdir(exist_ok=True)
    collect, inventory = collected_inventory()
    test_files = sorted(inventory)
    batches = [test_files[i:i + BATCH_SIZE] for i in range(0, len(test_files), BATCH_SIZE)]
    git = lambda args: subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True).stdout.strip()
    records, executed = [], Counter()
    suite_start = time.monotonic()
    for number, batch in enumerate(batches, 1):
        xml_path = XML / f"batch_{number:03d}.xml"
        started = time.monotonic()
        proc = subprocess.run(command([*batch, f"--junitxml={xml_path}", "-q"]), cwd=API, text=True, capture_output=True)
        (XML / f"batch_{number:03d}.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
        parsed = parse_junit(xml_path) if xml_path.exists() else {}
        records.append({"batch": number, "files": batch, "command": command([*batch, f"--junitxml={xml_path}", "-q"]), "exit_code": proc.returncode, "duration_seconds": round(time.monotonic() - started, 3), "junit_xml": str(xml_path.relative_to(ROOT)), "results": {k: dict(v) for k, v in parsed.items()}})
        executed.update({name: values["collected"] for name, values in parsed.items()})
        print(f"batch {number}/{len(batches)} exit={proc.returncode} cases={sum(v['collected'] for v in parsed.values())}", flush=True)
    totals = Counter()
    for batch in records:
        for values in batch["results"].values():
            totals.update(values)
    coverage_gaps = {name: count for name, count in inventory.items() if executed[name] != count}
    overlap = [name for name, count in Counter(f for batch in batches for f in batch).items() if count != 1]
    ledger = {
        "phase": "PHASE_14", "environment": {"python": str(PYTHON), "platform": sys.platform, "command": command(["--collect-only", "-q"])},
        "source_revision": git(["rev-parse", "HEAD"]), "working_tree_short": git(["status", "--short"]),
        "collection": {"exit_code": collect.returncode, "files": dict(inventory), "total_collected": sum(inventory.values())},
        "batches": records, "totals": dict(totals), "coverage_gaps": coverage_gaps, "batch_overlap": overlap,
        "duration_seconds": round(time.monotonic() - suite_start, 3),
        "verdict": "PASS" if collect.returncode == 0 and not coverage_gaps and not overlap and totals["failed"] == totals["error"] == 0 and totals["collected"] == sum(inventory.values()) else "FAIL",
    }
    (OUT / "backend_regression_ledger_p14.json").write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    print(json.dumps({"totals": ledger["totals"], "gaps": coverage_gaps, "verdict": ledger["verdict"]}, indent=2))


if __name__ == "__main__":
    main()
