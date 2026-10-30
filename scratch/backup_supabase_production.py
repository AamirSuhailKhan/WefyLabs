import os
import subprocess
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv

load_dotenv("apps/api/.env", override=False)
raw_url = os.environ.get("DATABASE_URL", "").replace("+asyncpg", "")

backup_dir = os.path.abspath("backups")
os.makedirs(backup_dir, exist_ok=True)
dump_filename = "supabase_prod_backup_pre_resolution.dump"
dump_path = os.path.join(backup_dir, dump_filename)

p = urlparse(raw_url)
user = unquote(p.username or "")
password = unquote(p.password or "")
host = p.hostname
port = str(p.port or 5432)
dbname = p.path.lstrip('/')

cmd = [
    "docker", "run", "--rm",
    "-e", f"PGPASSWORD={password}",
    "-v", f"{backup_dir}:/backups",
    "postgres:17-alpine",
    "pg_dump",
    "-h", host,
    "-p", port,
    "-U", user,
    "-d", dbname,
    "-Fc", "-v",
    "-f", f"/backups/{dump_filename}"
]

res = subprocess.run(cmd, capture_output=True, text=True)
print(f"Exit code: {res.returncode}")
if res.returncode == 0:
    print(f"SUCCESS! Backup size: {os.path.getsize(dump_path)} bytes")
else:
    print(f"STDERR: {res.stderr}")
    print(f"STDOUT: {res.stdout}")
