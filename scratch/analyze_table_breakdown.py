import json

with open("scratch/migration_inventory_p7.json", "r", encoding="utf-8") as f:
    data = json.load(f)

orm_tables = set(data["orm_tables"])

pre_merge_tables = set()
post_merge_tables = set()

post_merge = False
for m in data["migrations"]:
    if m["revision"] == "0015_sales_loop_orchestration":
        post_merge = True
    if post_merge:
        post_merge_tables.update(m["tables_created"])
    else:
        pre_merge_tables.update(m["tables_created"])

print(f"Total ORM tables: {len(orm_tables)}")
print(f"Pre-merge migration tables (001-0014): {len(pre_merge_tables)}")
print(f"Post-merge migration tables (0015-0047): {len(post_merge_tables)}")

# Baseline tables needed by 9999 = ORM tables that are NOT created by post-merge migrations
baseline_needed = orm_tables - post_merge_tables
print(f"Baseline tables needed (ORM minus post-merge): {len(baseline_needed)}")

# How many of these baseline tables are already created by 001-0014?
already_created_in_001_0014 = baseline_needed.intersection(pre_merge_tables)
print(f"Already created in 001-0014: {len(already_created_in_001_0014)}")

untracked_in_baseline = baseline_needed - pre_merge_tables
print(f"Untracked baseline tables (need creation in 9999 if not exists): {len(untracked_in_baseline)}")
print(f"Sample untracked: {sorted(list(untracked_in_baseline))[:15]}")
