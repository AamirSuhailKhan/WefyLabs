import os
import sys
import time
import subprocess
import httpx

STANDALONE_DIR = os.path.abspath("apps/web/.next/standalone")
SERVER_SCRIPT = os.path.join("apps", "web", "server.js")
PORT = 3006
URL = f"http://127.0.0.1:{PORT}"

print(f"Launching standalone Next.js server on port {PORT} from {STANDALONE_DIR}...")
env = os.environ.copy()
env["PORT"] = str(PORT)
env["HOSTNAME"] = "127.0.0.1"

proc = subprocess.Popen(
    ["node", SERVER_SCRIPT],
    cwd=STANDALONE_DIR,
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

try:
    print("Waiting for standalone server to listen...")
    connected = False
    start_time = time.time()
    
    for _ in range(30):
        time.sleep(0.5)
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(URL)
                print(f"Standalone server responded with HTTP {res.status_code} in {round((time.time() - start_time)*1000, 1)}ms")
                assert res.status_code == 200, f"Expected 200 OK, got {res.status_code}"
                connected = True
                break
        except Exception:
            pass
            
    assert connected, "Failed to connect to standalone Next.js server within timeout."
    print("STANDALONE SERVER VERIFICATION PASSED (HTTP 200 OK)!")

finally:
    print("Terminating standalone server process...")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("Standalone server cleanly terminated.")
