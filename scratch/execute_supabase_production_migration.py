import os
import subprocess
from dotenv import load_dotenv

load_dotenv("apps/api/.env", override=False)
raw_url = os.environ.get("DATABASE_URL", "").replace("+asyncpg", "")

cmd = [
    "python", "apps/api/scripts/release_migration.py"
]
env = os.environ.copy()
env["TARGET_DATABASE_URL"] = raw_url

print("Executing production migration against hosted Supabase...")
res = subprocess.run(cmd, env=env, capture_output=True, text=True)
print(f"Exit code: {res.returncode}")
print(f"STDOUT:\n{res.stdout}")
print(f"STDERR:\n{res.stderr}")

