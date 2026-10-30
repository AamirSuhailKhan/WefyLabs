import os
from urllib.parse import urlparse

files = ['.env', 'apps/api/.env', '.env.production', '.env.local', '.env.pilot.example']
for path in files:
    if os.path.exists(path):
        env = {}
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
        db = env.get('DATABASE_URL')
        target_db = env.get('TARGET_DATABASE_URL')
        print(f"File: {path}")
        for key, val in [('DATABASE_URL', db), ('TARGET_DATABASE_URL', target_db)]:
            if val:
                clean = val.replace('+asyncpg', '').replace('+aiosqlite', '')
                p = urlparse(clean)
                print(f"  {key}: scheme={p.scheme}, host={p.hostname}, port={p.port}, db={p.path}")
            else:
                print(f"  {key}: None")
    else:
        print(f"File: {path} does NOT exist")

