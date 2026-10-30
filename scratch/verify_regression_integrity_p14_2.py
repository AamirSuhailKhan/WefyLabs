import os
import glob
import json
import xml.etree.ElementTree as ET

def verify_regression_integrity():
    print("=== PHASE 14.2 REGRESSION EVIDENCE INTEGRITY AUDIT ===")
    
    # 1. Inspect Inventory
    with open("scratch/test_inventory_p14.json", "r", encoding="utf-8") as f:
        inv = json.load(f)
    inv_files = inv["files"]
    inv_total_tests = inv["total_tests"]
    assert len(inv_files) == 222, f"Expected 222 inventory files, got {len(inv_files)}"
    assert inv_total_tests == 3359, f"Expected 3,359 tests in inventory, got {inv_total_tests}"
    print(f"1. Inventory: 222 files, 3,359 test cases verified.")

    # 2. Inspect 23 XML batches
    xml_files = sorted(glob.glob("scratch/batch_xmls_p14/batch_*.xml"))
    assert len(xml_files) == 23, f"Expected 23 batch XMLs, got {len(xml_files)}"
    
    total_parsed_tests = 0
    total_passed = 0
    total_skipped = 0
    total_failed = 0
    total_error = 0
    
    identities_map = {}
    duplicates = []
    skips_list = []

    for xf in xml_files:
        batch_id = os.path.basename(xf)
        tree = ET.parse(xf)
        root = tree.getroot()
        testcases = root.findall(".//testcase")
        for tc in testcases:
            total_parsed_tests += 1
            classname = tc.get("classname", "")
            name = tc.get("name", "")
            time_val = float(tc.get("time", 0.0))
            
            fail_el = tc.find("failure")
            err_el = tc.find("error")
            skip_el = tc.find("skipped")
            
            if fail_el is not None:
                status = "FAIL"
                total_failed += 1
            elif err_el is not None:
                status = "ERROR"
                total_error += 1
            elif skip_el is not None:
                status = "SKIPPED"
                total_skipped += 1
                skips_list.append({
                    "batch": batch_id,
                    "classname": classname,
                    "name": name,
                    "reason": skip_el.get("message", "")
                })
            else:
                status = "PASS"
                total_passed += 1

            # Build reconstructed node ID preserving parametrization
            parts = classname.split(".")
            mod = parts[1] if parts[0] == "tests" else parts[0]
            classes = parts[2:] if parts[0] == "tests" else parts[1:]
            
            file_path = f"tests/{mod}.py"
            if classes:
                node_id = f"{file_path}::{'::'.join(classes)}::{name}"
            else:
                node_id = f"{file_path}::{name}"
                
            if node_id in identities_map:
                duplicates.append({
                    "node_id": node_id,
                    "batch1": identities_map[node_id]["batch"],
                    "batch2": batch_id
                })
            else:
                identities_map[node_id] = {
                    "batch": batch_id,
                    "status": status,
                    "time": time_val
                }

    print(f"2. XML Batches: 23/23 valid. Total testcases parsed: {total_parsed_tests}")
    print(f"   Passed:  {total_passed}")
    print(f"   Skipped: {total_skipped}")
    print(f"   Failed:  {total_failed}")
    print(f"   Error:   {total_error}")
    print(f"   Duplicates across batches: {len(duplicates)}")

    assert total_parsed_tests == 3359
    assert total_passed == 3357
    assert total_skipped == 2
    assert total_failed == 0
    assert total_error == 0
    assert len(duplicates) == 0

    # 3. Load authoritative collected pytest node IDs
    with open("scratch/pytest_current_node_ids.txt", "r", encoding="utf-16") as f:
        collected_ids = [line.strip() for line in f if line.strip() and "::" in line and not line.startswith("===")]

    assert len(collected_ids) == 3359
    collected_set = set(collected_ids)
    xml_set = set(identities_map.keys())

    missing = collected_set - xml_set
    unexpected = xml_set - collected_set

    print(f"3. 1-to-1 Node ID Match: {len(collected_set.intersection(xml_set))} / {len(collected_set)}")
    print(f"   Missing: {len(missing)}, Unexpected: {len(unexpected)}")
    assert len(missing) == 0
    assert len(unexpected) == 0

    # 4. Compare against ledger
    with open("scratch/backend_regression_ledger_p14.json", "r", encoding="utf-8") as f:
        ledger = json.load(f)

    assert ledger["total_files_reconciled"] == 222
    assert ledger["total_tests_collected"] == 3359
    assert ledger["total_tests_passed"] == 3357
    assert ledger["total_tests_skipped"] == 2
    assert ledger["total_tests_failed"] == 0
    assert ledger["total_tests_error"] == 0
    assert ledger["verdict"] == "PASS"

    audit_result = {
        "phase": "PHASE_14.2",
        "authoritative_files": 222,
        "authoritative_cases": 3359,
        "xml_batches_parsed": 23,
        "xml_cases_parsed": total_parsed_tests,
        "passed": total_passed,
        "skipped": total_skipped,
        "failed": total_failed,
        "error": total_error,
        "duplicate_identities": len(duplicates),
        "exact_matches": len(collected_set.intersection(xml_set)),
        "skips": skips_list,
        "ledger_verified": True,
        "verdict": "VERIFIED_PASS"
    }

    with open("scratch/regression_evidence_audit_p14_2.json", "w", encoding="utf-8") as f:
        json.dump(audit_result, f, indent=2)

    print("Phase 14.2 Regression Evidence Audit Result: VERIFIED_PASS")
    print("Saved artifact: scratch/regression_evidence_audit_p14_2.json")

if __name__ == "__main__":
    verify_regression_integrity()
