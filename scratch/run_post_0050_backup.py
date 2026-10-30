import os
import subprocess
from dotenv import load_dotenv

load_dotenv("apps/api/.env", override=False)
raw_url = os.environ.get("DATABASE_URL", "").replace("+asyncpg", "")

backup_file = "supabase_prod_post_0050_20261030_072000.dump"
cmd = [
    "docker", "run", "--rm",
    "-v", f"{os.getcwd()}/backups:/backups",
    "postgres:17-alpine",
    "pg_dump",
    "-F", "c",
    "-b",
    "-v",
    "-d", raw_url,
    "-f", f"/backups/{backup_file}"
]

print("Executing post-migration pg_dump via URI...")
res = subprocess.run(cmd, capture_output=True, text=True)
print("Return code:", res.returncode)
if res.returncode != 0:
    print("Stderr:", res.stderr[-500:] if len(res.stderr) > 500 else res.stderr)
else:
    dump_path = os.path.join(os.getcwd(), "backups", backup_file)
    size = os.path.getsize(dump_path)
    print(f"Success! Captured {backup_file}: {size} bytes.")
