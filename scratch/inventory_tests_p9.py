import os
import sys

TESTS_DIR = os.path.abspath("apps/api/tests")
test_files = [f for f in os.listdir(TESTS_DIR) if f.startswith("test_") and f.endswith(".py")]
test_files.sort()

print(f"Total test files discovered: {len(test_files)}")
for i, f in enumerate(test_files, 1):
    print(f"{i:2d}. {f}")
