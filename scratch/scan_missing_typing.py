import os
import ast

TYPING_NAMES = {"Optional", "Union", "List", "Dict", "Tuple", "Any", "Callable", "Set"}
API_DIR = os.path.abspath("apps/api/app")

issues = []

for root, _, files in os.walk(API_DIR):
    for f in files:
        if not f.endswith(".py"):
            continue
        filepath = os.path.join(root, f)
        with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
            source = fh.read()
        try:
            tree = ast.parse(source, filename=filepath)
        except Exception:
            continue
        
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)

        # Look for Name nodes used in annotations or code
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id in TYPING_NAMES and node.id not in imported_names:
                    issues.append((os.path.relpath(filepath), node.lineno, node.id))

print(f"Found {len(issues)} issues:")
for p, l, n in issues:
    print(f"  {p}:{l} -> missing {n}")
