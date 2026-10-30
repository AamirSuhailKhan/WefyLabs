import os
import re

p = "apps/api/alembic/versions"
for f in sorted(os.listdir(p)):
    if not f.endswith(".py"): continue
    content = open(os.path.join(p, f), encoding="utf-8").read()
    
    # Check for op.add_column or batch_op.add_column
    adds = re.findall(r'add_column\(.*?\)', content)
    batches = re.findall(r'batch_alter_table\((.*?)\)', content)
    if adds or batches:
        print(f"{f}: batches={batches}, add_column count={len(adds)}")
