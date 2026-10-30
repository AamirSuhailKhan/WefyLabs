import os
import re
import ast

VERSIONS_DIR = os.path.abspath("apps/api/alembic/versions")

files = sorted([f for f in os.listdir(VERSIONS_DIR) if f.endswith(".py")])

operations_report = []

for f in files:
    path = os.path.join(VERSIONS_DIR, f)
    with open(path, "r", encoding="utf-8", errors="ignore") as fp:
        code = fp.read()
    
    # Extract revision and down_revision
    rev_m = re.search(r"revision\s*=\s*['\"]([^'\"]+)['\"]", code)
    down_m = re.search(r"down_revision\s*=\s*([^\n\r]+)", code)
    rev = rev_m.group(1) if rev_m else None
    down = down_m.group(1).strip() if down_m else None
    
    # Extract op calls in upgrade()
    # Find upgrade function body
    upg_match = re.search(r"def upgrade\(\).*?:(.*?)(?=def downgrade|\Z)", code, re.DOTALL)
    upg_body = upg_match.group(1) if upg_match else ""
    
    ops = re.findall(r"op\.([a-zA-Z0-9_]+)\((.*?)\)", upg_body, re.DOTALL)
    executes = re.findall(r"op\.execute\((.*?)\)", upg_body, re.DOTALL)
    raw_sqls = re.findall(r"connection\.execute\((.*?)\)", upg_body, re.DOTALL)
    
    op_counts = {}
    for op_name, op_args in ops:
        op_counts[op_name] = op_counts.get(op_name, 0) + 1
        
    operations_report.append({
        "file": f,
        "revision": rev,
        "down_revision": down,
        "op_counts": op_counts,
        "executes": executes,
        "raw_sqls": raw_sqls,
        "upgrade_len": len(upg_body.strip())
    })

print(f"Total migration files: {len(operations_report)}")
for r in operations_report:
    print(f"\n--- {r['file']} (Rev: {r['revision']}, Down: {r['down_revision']}) ---")
    print(f"  Op summary: {r['op_counts']}")
    if r['executes']:
        print(f"  op.execute statements: {len(r['executes'])}")
        for e in r['executes'][:5]:
            clean_e = re.sub(r'\s+', ' ', e[:120]).strip()
            print(f"    -> {clean_e}")
