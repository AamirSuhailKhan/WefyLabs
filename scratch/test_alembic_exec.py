import os
import sys
from alembic.config import Config
from alembic import command

API_DIR = os.path.abspath("apps/api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.config import settings

def test_migration():
    ini_path = os.path.join(API_DIR, "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("script_location", os.path.join(API_DIR, "alembic"))
    
    # Set target schema
    os.environ["ALEMBIC_SCHEMA"] = "test_empty_upgrade_p7"
    
    print("Running alembic upgrade head on test_empty_upgrade_p7...")
    try:
        command.upgrade(cfg, "head")
        print("SUCCESS! Upgraded to head.")
    except Exception as e:
        print(f"FAILED with error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_migration()
