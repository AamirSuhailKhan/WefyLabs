import os
import sys
import ast
import json

API_DIR = os.path.abspath("apps/api")
VERSIONS_DIR = os.path.join(API_DIR, "alembic", "versions")

post_merge_created = set()
for fname in sorted(os.listdir(VERSIONS_DIR)):
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

with open("scratch/post_merge_tables.json", "w", encoding="utf-8") as f:
    json.dump(sorted(list(post_merge_created)), f, indent=2)

print(f"Generated scratch/post_merge_tables.json with {len(post_merge_created)} tables.")
