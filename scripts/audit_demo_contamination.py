import os
import re
import json

search_dir = r"apps/web/src"
patterns = [
    (r'\b(mock|mockData|mockLeads|mockProperties|mockDeals)\b', "MOCK_IDENTIFIER"),
    (r'\b(demoData|sampleData|fakeData|dummyData)\b', "DEMO_DATA_IDENTIFIER"),
    (r'\b(fixture|seedData)\b', "FIXTURE_IDENTIFIER"),
    (r'\[\s*\{\s*["\']id["\']\s*:\s*["\']demo-', "HARDCODED_DEMO_ARRAY"),
    (r'Math\.random\(', "SYNTHETIC_RANDOM_GENERATION"),
]

results = []

for root, dirs, files in os.walk(search_dir):
    for f in files:
        if f.endswith((".tsx", ".ts", ".js", ".jsx")):
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, search_dir).replace("\\", "/")
            try:
                with open(full_path, "r", encoding="utf-8") as fp:
                    content = fp.read()
                
                for pat, label in patterns:
                    matches = list(re.finditer(pat, content, re.I))
                    if matches:
                        results.append({
                            "file": rel_path,
                            "type": label,
                            "count": len(matches),
                            "lines": [content[:m.start()].count("\n") + 1 for m in matches[:5]]
                        })
            except Exception as e:
                pass

print(f"Total files with demo/fixture flags: {len(results)}")
with open("scripts/demo_contamination_findings.json", "w", encoding="utf-8") as out:
    json.dump(results, out, indent=2)

print("Saved scripts/demo_contamination_findings.json")
