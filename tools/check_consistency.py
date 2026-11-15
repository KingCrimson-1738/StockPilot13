"""Checks spec scenarios 19 and 20 against a running local backend.

19. The Tkinter app and the Swing app show the same data (Swing's own ApiClient lists the products; we compare them
    with what the server returns, so products created through the Tkinter screens must appear in Swing).
20. Data survives a restart: pass --restart-cmd to restart the backend between two reads (see usage).

Usage: python tools/check_consistency.py EMAIL PASSWORD GSON_JAR CLASSES_DIR [--restart "shell command that restarts the backend"]
"""
import subprocess, sys, time, requests

BASE = "http://127.0.0.1:8000"


def server_list(email, password):
    token = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password}).json()["access_token"]
    headers = {"Authorization": "Bearer " + token}
    business = requests.get(f"{BASE}/businesses", headers=headers).json()[0]
    products = requests.get(f"{BASE}/businesses/{business['id']}/products", headers=headers).json()
    return [f"BUSINESS {business['name']}"] + [f"{p['sku']}|{p['name']}|{p['category_name'] or '-'}|{p['quantity']}" for p in products]


def swing_list(email, password, jar, classes):
    out = subprocess.run(["java", "-cp", f"{classes}:{jar}", "com.stockpilot.ListProductsTest", email, password],
                         capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if "|" in line or line.startswith("BUSINESS")]


def main():
    email, password, jar, classes = sys.argv[1:5]
    before = server_list(email, password)
    swing = swing_list(email, password, jar, classes)
    ok = before == swing and len(before) > 1
    print(("PASS" if ok else "FAIL"), f"Swing shows the same {len(before) - 1} products as the server")
    if "--restart" in sys.argv:
        subprocess.run(sys.argv[sys.argv.index("--restart") + 1], shell=True, check=True)
        for _ in range(30):
            try:
                if requests.get(f"{BASE}/health", timeout=2).status_code == 200:
                    break
            except requests.RequestException:
                time.sleep(1)
        after = server_list(email, password)
        same = after == before
        print(("PASS" if same else "FAIL"), "all data is identical after the backend was restarted")
        ok = ok and same
    sys.exit(0 if ok else 1)


main()
