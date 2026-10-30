import os
import sys
import ast

API_DIR = os.path.abspath("apps/api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.config import settings
from app.database import Base
import app.models

# 1. Discover all tables created by 0015..0047
VERSIONS_DIR = os.path.join(API_DIR, "alembic", "versions")
post_merge_created = set()
for fname in os.listdir(VERSIONS_DIR):
    if not fname.endswith(".py"): continue
    if fname.startswith("00") and fname[:4].isdigit() and int(fname[:4]) >= 15:
        fpath = os.path.join(VERSIONS_DIR, fname)
        with open(fpath, "r", encoding="utf-8") as fp:
            tree = ast.parse(fp.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
                if fn == "create_table" and node.args and isinstance(node.args[0], ast.Constant):
                    post_merge_created.add(node.args[0].value)

# Baseline tables
all_orm_tables = Base.metadata.tables
baseline_tables = [table for name, table in all_orm_tables.items() if name not in post_merge_created]

print(f"Total ORM tables: {len(all_orm_tables)}")
print(f"Post-merge migration tables: {len(post_merge_created)}")
print(f"Baseline tables to be provisioned by 9999 on fresh DB: {len(baseline_tables)}")
