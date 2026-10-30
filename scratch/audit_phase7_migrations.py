import os
import sys
import ast
import json
import importlib.util

API_DIR = os.path.abspath("apps/api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

VERSIONS_DIR = os.path.join(API_DIR, "alembic", "versions")

def analyze_migration_file(filepath):
    filename = os.path.basename(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    tree = ast.parse(content, filename=filepath)

    revision = None
    down_revision = None
    branch_labels = None
    depends_on = None

    def get_const_val(node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, (ast.Tuple, ast.List)):
            return [get_const_val(elt) for elt in node.elts]
        return None

    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    if target.id == "revision":
                        revision = get_const_val(stmt.value)
                    elif target.id == "down_revision":
                        down_revision = get_const_val(stmt.value)
                    elif target.id == "branch_labels":
                        branch_labels = get_const_val(stmt.value)
                    elif target.id == "depends_on":
                        depends_on = get_const_val(stmt.value)
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            if stmt.target.id == "revision":
                revision = get_const_val(stmt.value)
            elif stmt.target.id == "down_revision":
                down_revision = get_const_val(stmt.value)
            elif stmt.target.id == "branch_labels":
                branch_labels = get_const_val(stmt.value)
            elif stmt.target.id == "depends_on":
                depends_on = get_const_val(stmt.value)

    # Extract function calls and operations inside upgrade() and downgrade()
    tables_created = []
    tables_dropped = []
    columns_added = []
    columns_dropped = []
    indexes_created = []
    constraints_added = []
    raw_sqls = []
    downgrade_has_pass = False
    downgrade_ops = []

    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef):
            if stmt.name == "upgrade":
                for node in ast.walk(stmt):
                    if isinstance(node, ast.Call):
                        # op.create_table(...)
                        func_name = ""
                        if isinstance(node.func, ast.Attribute):
                            func_name = node.func.attr
                        elif isinstance(node.func, ast.Name):
                            func_name = node.func.id
                        
                        if func_name == "create_table" and node.args:
                            if isinstance(node.args[0], ast.Constant):
                                tables_created.append(node.args[0].value)
                        elif func_name == "drop_table" and node.args:
                            if isinstance(node.args[0], ast.Constant):
                                tables_dropped.append(node.args[0].value)
                        elif func_name == "add_column" and len(node.args) >= 2:
                            t_name = node.args[0].value if isinstance(node.args[0], ast.Constant) else "?"
                            c_name = node.args[1].attr if isinstance(node.args[1], ast.Attribute) else "?"
                            columns_added.append(f"{t_name}.{c_name}")
                        elif func_name == "drop_column" and len(node.args) >= 2:
                            t_name = node.args[0].value if isinstance(node.args[0], ast.Constant) else "?"
                            c_name = node.args[1].value if isinstance(node.args[1], ast.Constant) else "?"
                            columns_dropped.append(f"{t_name}.{c_name}")
                        elif func_name == "create_index" and node.args:
                            idx_name = node.args[0].value if isinstance(node.args[0], ast.Constant) else "?"
                            t_name = node.args[1].value if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else "?"
                            indexes_created.append(f"{idx_name} on {t_name}")
                        elif func_name in ("execute", "execute_sql"):
                            sql_text = ""
                            if node.args and isinstance(node.args[0], ast.Constant):
                                sql_text = str(node.args[0].value)[:80]
                            elif node.args and isinstance(node.args[0], ast.Call):
                                sql_text = "dynamic SQL"
                            raw_sqls.append(sql_text)
            elif stmt.name == "downgrade":
                for node in stmt.body:
                    if isinstance(node, ast.Pass):
                        downgrade_has_pass = True
                    elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                        fn = node.value.func.attr if isinstance(node.value.func, ast.Attribute) else "call"
                        downgrade_ops.append(fn)

    return {
        "file": filename,
        "revision": revision,
        "down_revision": down_revision,
        "branch_labels": branch_labels,
        "depends_on": depends_on,
        "tables_created": tables_created,
        "tables_dropped": tables_dropped,
        "columns_added": columns_added,
        "columns_dropped": columns_dropped,
        "indexes_created": indexes_created,
        "raw_sqls": raw_sqls,
        "downgrade_has_pass": downgrade_has_pass,
        "downgrade_ops_count": len(downgrade_ops)
    }

def main():
    files = sorted([f for f in os.listdir(VERSIONS_DIR) if f.endswith(".py")])
    inventory = []
    rev_map = {}
    down_map = {}

    for f in files:
        data = analyze_migration_file(os.path.join(VERSIONS_DIR, f))
        inventory.append(data)
        rev = data["revision"]
        rev_map[rev] = data
        down = data["down_revision"]
        if isinstance(down, list):
            for d in down:
                down_map.setdefault(d, []).append(rev)
        elif down:
            down_map.setdefault(down, []).append(rev)

    # Reconcile with SQLAlchemy models
    from app.database import Base
    import app.models  # All 401 models registered

    orm_tables = sorted(list(Base.metadata.tables.keys()))
    all_migrated_tables = set()
    for item in inventory:
        all_migrated_tables.update(item["tables_created"])

    print(f"Total Alembic migration files: {len(inventory)}")
    print(f"Total ORM registered tables: {len(orm_tables)}")
    print(f"Total tables created by migrations: {len(all_migrated_tables)}")

    # Roots and heads
    roots = [item["revision"] for item in inventory if item["down_revision"] is None]
    heads = [item["revision"] for item in inventory if item["revision"] not in down_map]

    print(f"DAG Roots: {roots}")
    print(f"DAG Heads: {heads}")

    # Output detailed JSON
    with open("scratch/migration_inventory_p7.json", "w", encoding="utf-8") as out:
        json.dump({
            "total_files": len(inventory),
            "roots": roots,
            "heads": heads,
            "orm_table_count": len(orm_tables),
            "migration_table_count": len(all_migrated_tables),
            "orm_tables": orm_tables,
            "migrations": inventory
        }, out, indent=2)

    print("Detailed inventory written to scratch/migration_inventory_p7.json")

if __name__ == "__main__":
    main()
