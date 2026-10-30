import os
import re

p = "apps/api/alembic/versions"
for f in sorted(os.listdir(p)):
    if not f.endswith(".py"):
        continue
    content = open(os.path.join(p, f), encoding="utf-8").read()
    
    # Find all Column(..., index=True)
    col_matches = re.findall(r'Column\(\s*["\'](\w+)["\'].*?index=True', content, re.DOTALL)
    for col in set(col_matches):
        # Check if create_index exists for this col
        idx_matches = re.findall(r'create_index\(\s*["\'](\w+)["\'],\s*["\'](\w+)["\'],\s*\[["\']' + col + r'["\']\]', content)
        if idx_matches:
            print(f"{f}: Column '{col}' in has index=True and explicit create_index: {idx_matches}")

    # Also check if same index name created twice
    all_indices = re.findall(r'create_index\(\s*["\'](\w+)["\']', content)
    counts = {idx: all_indices.count(idx) for idx in all_indices}
    for idx, c in counts.items():
        if c > 1:
            print(f"{f}: Index '{idx}' created multiple times ({c}) in file")
