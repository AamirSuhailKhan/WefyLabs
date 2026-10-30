import os
import sys
import re

sys.path.insert(0, os.path.abspath("apps/api"))
from app.database import Base
import app.models

VERSIONS_DIR = os.path.abspath("apps/api/alembic/versions")
files = sorted([f for f in os.listdir(VERSIONS_DIR) if f.endswith(".py")])

print(f"Total ORM models: {len(Base.metadata.tables)} tables")

# Collect all ORM tables, columns, constraints, indexes
orm_tables = set(Base.metadata.tables.keys())
orm_columns = {}
orm_indexes = {}
orm_uniques = {}

for tname, table in Base.metadata.tables.items():
    orm_columns[tname] = set(c.name for c in table.columns)
    orm_indexes[tname] = set(idx.name for idx in table.indexes if idx.name)
    orm_uniques[tname] = set(con.name for con in table.constraints if hasattr(con, 'name') and con.name)

# Analyze migrations for operations:
# 1. create_table
# 2. add_column
# 3. create_index
# 4. create_unique_constraint
# 5. create_check_constraint
# 6. op.execute (raw SQL)

migration_audit = []

for f in files:
    path = os.path.join(VERSIONS_DIR, f)
    with open(path, "r", encoding="utf-8", errors="ignore") as fp:
        code = fp.read()
    
    rev_m = re.search(r"revision\s*=\s*['\"]([^'\"]+)['\"]", code)
    rev = rev_m.group(1) if rev_m else f
    
    # Check for raw executes
    executes = re.findall(r"op\.execute\((.*?)\)", code, re.DOTALL)
    
    # Check for indexes
    created_indexes = re.findall(r"op\.create_index\(\s*['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"]", code)
    
    # Check for unique constraints
    created_uniques = re.findall(r"op\.create_unique_constraint\(\s*['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"]", code)
    
    # Check for check constraints
    created_checks = re.findall(r"op\.create_check_constraint\(\s*['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"]", code)
    
    # Check for add_column
    added_cols = re.findall(r"op\.add_column\(\s*['\"]([^'\"]+)['\"],\s*sa\.Column\(\s*['\"]([^'\"]+)['\"]", code)
    
    # Check for batch_alter_table add_column
    batch_cols = re.findall(r"batch_op\.add_column\(\s*sa\.Column\(\s*['\"]([^'\"]+)['\"]", code)
    
    migration_audit.append({
        "file": f,
        "revision": rev,
        "executes": executes,
        "indexes": created_indexes,
        "uniques": created_uniques,
        "checks": created_checks,
        "added_cols": added_cols,
        "batch_cols": batch_cols,
    })

print("\n=== MIGRATIONS WITH RAW EXECUTES OR SPECIAL CONSTRAINTS ===")
for m in migration_audit:
    has_exec = len(m["executes"]) > 0
    has_uniques = len(m["uniques"]) > 0
    has_checks = len(m["checks"]) > 0
    if has_exec or has_uniques or has_checks:
        print(f"\nMigration: {m['file']} ({m['revision']})")
        if has_exec:
            print(f"  Raw executes ({len(m['executes'])}):")
            for e in m["executes"]:
                clean = re.sub(r'\s+', ' ', e[:150]).strip()
                print(f"    - {clean}")
        if has_uniques:
            print(f"  Unique constraints ({len(m['uniques'])}):")
            for u in m["uniques"]:
                print(f"    - {u[0]} on {u[1]}")
        if has_checks:
            print(f"  Check constraints ({len(m['checks'])}):")
            for c in m["checks"]:
                print(f"    - {c[0]} on {c[1]}")

