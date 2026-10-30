import os
import glob
import re

versions_dir = "apps/api/alembic/versions"
for f in sorted(glob.glob(os.path.join(versions_dir, "*.py"))):
    fname = os.path.basename(f)
    with open(f, "r", encoding="utf-8") as fp:
        c = fp.read()
    if "add_column" in c:
        has_check = "_column_exists" in c or "if_not_exists" in c or "column_exists" in c or "information_schema" in c
        print(f"{fname}: add_column present, has_guard={has_check}")

