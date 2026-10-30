import os
import re

VERSIONS_DIR = os.path.abspath("apps/api/alembic/versions")
files = sorted([f for f in os.listdir(VERSIONS_DIR) if f.endswith(".py")])

print(f"Scanning {len(files)} migration files for all statements...")

for f in files:
    path = os.path.join(VERSIONS_DIR, f)
    with open(path, "r", encoding="utf-8", errors="ignore") as fp:
        code = fp.read()
    
    # Find upgrade function
    m = re.search(r"def upgrade\(\).*?:(.*?)(?=def downgrade|\Z)", code, re.DOTALL)
    if not m:
        continue
    body = m.group(1)
    
    # Check for anything interesting: execute, raw sql, create_index, add_column, etc.
    # Look for op.execute
    for match in re.finditer(r"op\.execute\((.*?)\)", body, re.DOTALL):
        sql = match.group(1).strip()
        print(f"[{f}] op.execute: {sql[:100]}...")
        
    # Look for insert / seed statements
    for match in re.finditer(r"insert\b.*", body, re.IGNORECASE):
        print(f"[{f}] INSERT: {match.group(0)[:100]}")
        
    # Look for triggers, functions, views, extensions
    for keyword in ["CREATE EXTENSION", "CREATE TRIGGER", "CREATE FUNCTION", "CREATE VIEW", "ALTER TABLE"]:
        for match in re.finditer(rf"{keyword}.*", body, re.IGNORECASE):
            print(f"[{f}] {keyword}: {match.group(0)[:100]}")
