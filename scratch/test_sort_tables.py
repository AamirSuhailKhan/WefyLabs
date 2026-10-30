import os
import sys

API_DIR = os.path.abspath("apps/api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.database import Base
import app.models
import json
with open("scratch/post_merge_tables.json", "r", encoding="utf-8") as f:
    POST_MERGE_TABLES = set(json.load(f))

print("Testing sort_tables...")
try:
    tables = [t for name, t in Base.metadata.tables.items() if name not in POST_MERGE_TABLES]
    print(f"Total baseline tables: {len(tables)}")
    sorted_tables = Base.metadata.sort_tables_and_constraints(tables)
    print("sort_tables_and_constraints SUCCESS!")
except Exception as e:
    print(f"sort_tables ERROR: {e}")
