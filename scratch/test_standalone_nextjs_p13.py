import subprocess
import time
import urllib.request
import os
import sys

def test_standalone():
    standalone_dir = os.path.abspath("apps/web/.next/standalone")
    server_path = os.path.join(standalone_dir, "apps", "web", "server.js")
    if not os.path.exists(server_path):
        print(f"ERROR: {server_path} not found")
        sys.exit(1)
        
    env = os.environ.copy()
    env["PORT"] = "3013"
    env["HOSTNAME"] = "127.0.0.1"
    
    print(f"Starting standalone server from {standalone_dir} on port 3013...")
    proc = subprocess.Popen(
        ["node", "apps/web/server.js"],
        cwd=standalone_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    time.sleep(3)
    try:
        url = "http://127.0.0.1:3013"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
            content = resp.read(200).decode('utf-8', errors='ignore')
            print(f"Standalone server HTTP Status: {status}")
            print(f"Content preview: {content[:100]}...")
            assert status == 200, f"Expected 200, got {status}"
            print("STANDALONE SERVER VERIFIED SUCCESSFULLY ON PORT 3013")
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        print("Standalone server cleanly terminated.")

if __name__ == "__main__":
    test_standalone()
