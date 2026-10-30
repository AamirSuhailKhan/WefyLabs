import os
import glob
import json
import xml.etree.ElementTree as ET

def audit_node_identities():
    print("=== INDIVIDUAL TEST IDENTITY RECONCILIATION AUDIT ===")
    
    # 1. Load authoritative node IDs
    with open('scratch/pytest_current_node_ids.txt', encoding='utf-16') as f:
        collected_node_ids = [line.strip() for line in f if line.strip() and '::' in line and not line.startswith('===')]

    collected_set = set(collected_node_ids)
    print(f"1. Total collected node IDs from pytest: {len(collected_node_ids)} (Unique: {len(collected_set)})")

    # 2. Extract from all 23 JUnit XMLs
    xml_files = sorted(glob.glob('scratch/batch_xmls_p14/batch_*.xml'))
    assert len(xml_files) == 23, f"Expected 23 XML files, found {len(xml_files)}"

    xml_records = []
    xml_by_id = {}
    duplicates = []
    
    total_xml_cases = 0
    passed_cases = 0
    failed_cases = 0
    skipped_cases = 0
    error_cases = 0
    skips_detail = []

    for xf in xml_files:
        batch_name = os.path.basename(xf)
        tree = ET.parse(xf)
        root = tree.getroot()
        for tc in root.findall('.//testcase'):
            total_xml_cases += 1
            classname = tc.get('classname', '')
            name = tc.get('name', '')
            time_sec = float(tc.get('time', 0.0))
            
            # Check outcome
            fail_elem = tc.find('failure')
            err_elem = tc.find('error')
            skip_elem = tc.find('skipped')
            
            if fail_elem is not None:
                status = "FAIL"
                failed_cases += 1
            elif err_elem is not None:
                status = "ERROR"
                error_cases += 1
            elif skip_elem is not None:
                status = "SKIPPED"
                skipped_cases += 1
                skips_detail.append({
                    "batch": batch_name,
                    "classname": classname,
                    "name": name,
                    "reason": skip_elem.get("message", "")
                })
            else:
                status = "PASS"
                passed_cases += 1

            # Map classname and name to reconstructed pytest node ID
            parts = classname.split('.')
            if parts[0] == 'tests':
                mod = parts[1]
                classes = parts[2:]
            else:
                mod = parts[0]
                classes = parts[1:]
                
            file_part = f"tests/{mod}.py"
            if classes:
                reconstructed_id = f"{file_part}::{'::'.join(classes)}::{name}"
            else:
                reconstructed_id = f"{file_part}::{name}"
                
            record = {
                "batch": batch_name,
                "reconstructed_id": reconstructed_id,
                "classname": classname,
                "name": name,
                "status": status,
                "duration": time_sec
            }
            xml_records.append(record)
            
            if reconstructed_id in xml_by_id:
                duplicates.append({
                    "id": reconstructed_id,
                    "first": xml_by_id[reconstructed_id]["batch"],
                    "second": batch_name
                })
            else:
                xml_by_id[reconstructed_id] = record

    print(f"2. Total XML testcases parsed: {total_xml_cases}")
    print(f"   Passed:  {passed_cases}")
    print(f"   Skipped: {skipped_cases}")
    print(f"   Failed:  {failed_cases}")
    print(f"   Error:   {error_cases}")

    # 3. Individual test matching
    xml_id_set = set(xml_by_id.keys())
    exact_matches = collected_set.intersection(xml_id_set)
    missing_in_xml = collected_set - xml_id_set
    unexpected_in_xml = xml_id_set - collected_set

    print(f"\n3. Reconciliation Results:")
    print(f"   Exact Identity Matches: {len(exact_matches)} / {len(collected_set)}")
    print(f"   Duplicates Across Batches: {len(duplicates)}")
    print(f"   Missing in XML: {len(missing_in_xml)}")
    print(f"   Unexpected in XML: {len(unexpected_in_xml)}")

    if missing_in_xml:
        print("Sample missing in XML:", list(missing_in_xml)[:10])
    if unexpected_in_xml:
        print("Sample unexpected in XML:", list(unexpected_in_xml)[:10])

    print(f"\n4. Accepted Skips ({len(skips_detail)}):")
    for s in skips_detail:
        print(f"   - [{s['batch']}] {s['classname']}::{s['name']} -> {s['reason']}")

    # Save artifact
    audit_artifact = {
        "phase": "PHASE_14.1",
        "authoritative_collected_total": len(collected_node_ids),
        "xml_parsed_total": total_xml_cases,
        "exact_identity_matches": len(exact_matches),
        "duplicates_count": len(duplicates),
        "missing_in_xml_count": len(missing_in_xml),
        "unexpected_in_xml_count": len(unexpected_in_xml),
        "passed_cases": passed_cases,
        "skipped_cases": skipped_cases,
        "failed_cases": failed_cases,
        "error_cases": error_cases,
        "skips": skips_detail,
        "verdict": "CERTIFIED_IDENTITY_RECONCILIATION" if len(exact_matches) == len(collected_set) == total_xml_cases and len(duplicates) == 0 else "FAIL"
    }

    with open("scratch/test_identity_reconciliation_p14.json", "w", encoding="utf-8") as f:
        json.dump(audit_artifact, f, indent=2)

    print(f"\nAudit artifact saved to scratch/test_identity_reconciliation_p14.json")
    print(f"Audit Verdict: {audit_artifact['verdict']}")

    return audit_artifact

if __name__ == "__main__":
    audit_node_identities()
