"""Phase 0 — System Reconstruction: Settings & Environment Check"""
import sys, os
sys.path.insert(0, '.')
os.environ['ENV'] = 'test'
from app.common.config.validated_settings import load_settings
s = load_settings()
print(f"ENV: {s.ENV}")
print(f"DATABASE_URL prefix: {str(s.DATABASE_URL)[:40] if s.DATABASE_URL else 'MISSING'}")
print(f"API_V1_STR: {s.API_V1_STR}")
print(f"PROJECT_NAME: {getattr(s, 'PROJECT_NAME', 'N/A')}")
print(f"VERSION: {getattr(s, 'VERSION', 'N/A')}")
print(f"CORS_ORIGINS: {getattr(s, 'CORS_ORIGINS', 'N/A')}")
print(f"REDIS_URL: {str(getattr(s, 'REDIS_URL', 'N/A'))[:30]}")
BOOL_KEYS = ['DEBUG', 'TESTING']
for k in BOOL_KEYS:
    print(f"{k}: {getattr(s, k, 'N/A')}")
