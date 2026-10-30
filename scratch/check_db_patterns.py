import re
from pathlib import Path

tests_dir = Path("apps/api/tests")
trunc_pattern = re.compile(r"\bTRUNCATE\b", re.IGNORECASE)
for p in tests_dir.rglob("*.py"):
    text = p.read_text(encoding="utf-8", errors="ignore")
    for idx, line in enumerate(text.splitlines(), 1):
        if trunc_pattern.search(line):
            print(f"{p.name}:{idx} -> {line.strip()[:80]}")
