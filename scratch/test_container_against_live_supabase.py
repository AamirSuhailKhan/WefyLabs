import os
import subprocess
from dotenv import load_dotenv

load_dotenv("apps/api/.env", override=False)
raw_url = os.environ.get("DATABASE_URL", "").replace("+asyncpg", "")

cmd = [
    "docker", "run", "--rm",
    "-e", "ENV=production",
    "-e", f"DATABASE_URL={raw_url}",
    "-e", "SECRET_KEY=test_production_secret_key_12345",
    "-e", "SUPABASE_JWT_SECRET=test_jwt_secret_12345",
    "-e", "DRY_RUN_VALIDATION_ONLY=true",
    "wefylabs-api:rc-0050"
]

print("Running candidate container startup verification against live hosted Supabase...")
res = subprocess.run(cmd, capture_output=True, text=True)
print(f"Exit code: {res.returncode}")
print(f"STDOUT:\n{res.stdout}")
print(f"STDERR:\n{res.stderr}")

