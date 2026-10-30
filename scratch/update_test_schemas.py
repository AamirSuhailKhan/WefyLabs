import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("apps/api"))

from scripts.init_db import initialize_database
from app.database import engine

async def main():
    print("Updating phase7_test_disposable...")
    res1 = await initialize_database("phase7_test_disposable", check_only=False)
    print("phase7 updated:", res1["status"])
    print("Updating phase9_fresh_disposable...")
    res2 = await initialize_database("phase9_fresh_disposable", check_only=False)
    print("phase9 updated:", res2["status"])
    await engine.dispose()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
