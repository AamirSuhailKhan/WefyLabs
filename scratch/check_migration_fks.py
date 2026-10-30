import os
import sys
import ast

API_DIR = os.path.abspath("apps/api")
VERSIONS_DIR = os.path.join(API_DIR, "alembic", "versions")

files = sorted([f for f in os.listdir(VERSIONS_DIR) if f.endswith(".py")])

all_created = set()
all_fk_targets = set()
migration_details = []

for f in files:
    with open(os.path.join(VERSIONS_DIR, f), "r", encoding="utf-8") as fp:
        content = fp.read()
    tree = ast.parse(content)
    rev = f
    created_here = []
    fks_here = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = ""
            if isinstance(node.func, ast.Attribute):
                fn = node.func.attr
            elif isinstance(node.func, ast.Name):
                fn = node.func.id
            if fn == "create_table" and node.args:
                if isinstance(node.args[0], ast.Constant):
                    created_here.append(node.args[0].value)
            elif fn in ("ForeignKey", "ForeignKeyConstraint"):
                if node.args:
                    if isinstance(node.args[0], ast.Constant):
                        fks_here.append(str(node.args[0].value).split(".")[0])
                    elif isinstance(node.args[0], (ast.List, ast.Tuple)) and len(node.args) > 1:
                        if isinstance(node.args[1], (ast.List, ast.Tuple)) and node.args[1].elts:
                            first = node.args[1].elts[0]
                            if isinstance(first, ast.Constant):
                                fks_here.append(str(first.value).split(".")[0])
    all_created.update(created_here)
    all_fk_targets.update(fks_here)
    migration_details.append({
        "file": f,
        "created": created_here,
        "fks": fks_here
    })

print(f"Total tables created across all migrations: {len(all_created)}")
print(f"Total FK target tables: {len(all_fk_targets)}")
missing_fks = all_fk_targets - all_created
print(f"FK target tables NEVER created in any migration: {sorted(list(missing_fks))}")
