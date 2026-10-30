"""
Phase 9 Uvicorn Staging Server Runner
====================================
Runs FastAPI service against isolated disposable schema 'phase9_fresh_disposable'.
"""
import os
import sys

os.environ["DB_SCHEMA"] = "phase9_fresh_disposable"
API_DIR = os.path.abspath("apps/api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

import uvicorn
from app.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8009, log_level="info")
