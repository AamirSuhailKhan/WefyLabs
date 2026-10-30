import os
import sys
from alembic.config import Config
from alembic.script import ScriptDirectory

API_DIR = os.path.abspath("apps/api")
cfg = Config(os.path.join(API_DIR, "alembic.ini"))
cfg.set_main_option("script_location", os.path.join(API_DIR, "alembic"))

script_dir = ScriptDirectory.from_config(cfg)
try:
    heads = script_dir.get_heads()
    print(f"Heads: {heads}")
    revisions = list(script_dir.walk_revisions())
    print(f"Successfully walked {len(revisions)} revisions.")
except Exception as e:
    print(f"DAG Error: {e}")
