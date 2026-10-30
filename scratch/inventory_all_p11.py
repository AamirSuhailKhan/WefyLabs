import subprocess
import sys
import json
import os
import glob
import time

def inventory_tests():
    tests_dir = os.path.abspath("apps/api/tests")
    test_files = sorted([f for f in os.listdir(tests_dir) if f.startswith("test_") and f.endswith(".py")])
    return [os.path.join("tests", f) for f in test_files]

if __name__ == "__main__":
    files = inventory_tests()
    print(f"Total discovered test files: {len(files)}")
