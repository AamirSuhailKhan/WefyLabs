import os
import re
from urllib.parse import urlparse

def inspect_endpoint(name, url_str):
    if not url_str:
        return {"name": name, "configured": False}
    try:
        # Normalize asyncpg
        clean_url = url_str.replace("+asyncpg", "").replace("+aiosqlite", "")
        parsed = urlparse(clean_url)
        return {
            "name": name,
            "configured": True,
            "scheme": parsed.scheme,
            "host": parsed.hostname,
            "port": parsed.port,
            "database": parsed.path.lstrip("/"),
            "has_auth": bool(parsed.username or parsed.password)
        }
    except Exception as e:
        return {"name": name, "configured": True, "error": str(e)}

def parse_env_file(path):
    endpoints = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if "DATABASE_URL" in k or "DB_URL" in k or "POSTGRES" in k:
                        endpoints[k] = v
    return endpoints

def main():
    root_env = parse_env_file(".env")
    api_env = parse_env_file("apps/api/.env")
    pilot_env = parse_env_file(".env.pilot")

    all_discovered = {}
    for k, v in root_env.items():
        all_discovered[f"root_{k}"] = inspect_endpoint(f"root_{k}", v)
    for k, v in api_env.items():
        all_discovered[f"api_{k}"] = inspect_endpoint(f"api_{k}", v)
    for k, v in pilot_env.items():
        all_discovered[f"pilot_{k}"] = inspect_endpoint(f"pilot_{k}", v)

    import json
    print(json.dumps(all_discovered, indent=2))

if __name__ == "__main__":
    main()

