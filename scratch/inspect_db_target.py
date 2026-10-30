import os, sys
sys.path.insert(0, os.path.abspath("apps/api"))
from app.config import settings
from urllib.parse import urlparse

parsed = urlparse(settings.DATABASE_URL)
print(f"Driver: {parsed.scheme}")
print(f"Host: {parsed.hostname}")
print(f"Port: {parsed.port}")
print(f"Database: {parsed.path}")
print(f"Username: {parsed.username}")
