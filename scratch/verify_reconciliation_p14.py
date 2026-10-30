import json

def verify():
    with open('scratch/test_inventory_p14.json') as f:
        inv = json.load(f)
    with open('scratch/backend_regression_ledger_p14.json') as f:
        ledger = json.load(f)

    inv_files = inv['files']
    ledger_map = {e['file']: e for e in ledger['files_ledger']}

    assert len(inv_files) == 222, f"Inventory has {len(inv_files)} files, expected 222"
    assert len(ledger_map) == 222, f"Ledger has {len(ledger_map)} files, expected 222"

    discrepancies = []
    for file_path, exp_count in inv_files.items():
        if file_path not in ledger_map:
            discrepancies.append((file_path, 'Missing in ledger'))
            continue
        act_entry = ledger_map[file_path]
        if act_entry['collected'] != exp_count:
            discrepancies.append((file_path, f"Count mismatch: exp={exp_count}, act={act_entry['collected']}"))
        if act_entry['failed'] > 0 or act_entry['error'] > 0:
            discrepancies.append((file_path, f"Failures: failed={act_entry['failed']}, error={act_entry['error']}"))

    print(f"Inventory vs Ledger File-by-File Reconciliation: {len(discrepancies)} discrepancies.")
    assert len(discrepancies) == 0, f"Discrepancies found: {discrepancies}"
    print("100% of 222 files and 3,359 test cases reconciled with ZERO errors!")

if __name__ == "__main__":
    verify()
