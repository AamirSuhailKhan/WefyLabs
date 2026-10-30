import os
import sys

API_DIR = os.path.abspath("apps/api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.database import Base
import app.models
if "." not in sys.path:
    sys.path.insert(0, ".")
from scratch.test_baseline_upgrade import baseline_tables, post_merge_created

# Check all foreign keys in baseline_tables
fk_pointing_to_post_merge = []

for t_name in baseline_tables:
    table = Base.metadata.tables.get(t_name)
    if table is None: continue
    for fk in table.foreign_keys:
        target_table = fk.column.table.name
        if target_table in post_merge_created:
            fk_pointing_to_post_merge.append((t_name, fk.parent.name, target_table))

print(f"Foreign keys from baseline tables pointing to post-merge tables: {len(fk_pointing_to_post_merge)}")
for item in fk_pointing_to_post_merge:
    print(f"  {item[0]}.{item[1]} -> {item[2]}")
