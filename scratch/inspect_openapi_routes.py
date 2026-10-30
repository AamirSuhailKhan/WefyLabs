"""
Scratch Script: Audit OpenAPI Operations and Security Schemes
"""
import sys
sys.path.insert(0, "apps/api")

from app.main import app

openapi = app.openapi()
paths = openapi.get("paths", {})

total_paths = len(paths)
total_ops = 0
secured_ops = 0
unsecured_ops = 0

unsecured_list = []

for path, methods in paths.items():
    for method, op_info in methods.items():
        total_ops += 1
        security = op_info.get("security", [])
        tags = op_info.get("tags", [])
        summary = op_info.get("summary", "")
        
        # Check security definition
        if security:
            secured_ops += 1
        else:
            unsecured_ops += 1
            unsecured_list.append((method.upper(), path, tags, summary))

print(f"Total Unique Paths: {total_paths}")
print(f"Total API Operations: {total_ops}")
print(f"Secured Operations (OAuth2 / Bearer / Security Scheme): {secured_ops}")
print(f"Unsecured/Public Operations: {unsecured_ops}")

print("\n--- Breakdown of Unsecured Operations by Tag ---")
from collections import Counter
tag_counts = Counter(tag for _, _, tags, _ in unsecured_list for tag in (tags or ["Untagged"]))
for tag, count in tag_counts.most_common(20):
    print(f"  {tag}: {count}")

print("\n--- First 20 Unsecured Endpoints ---")
for method, path, tags, summary in unsecured_list[:20]:
    print(f"[{method}] {path} | tags={tags} | summary={summary}")

