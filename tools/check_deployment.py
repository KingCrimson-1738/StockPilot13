"""Smoke test for a DEPLOYED StockPilot backend (or a local one). Needs only Python 3, no extra packages.

    python tools/check_deployment.py https://your-project.vercel.app

It creates a throw-away user and business (names start with "deploycheck") and then proves the things that matter:
database reachable, login works, wrong password refused, token required, stock can't go negative, and one user
cannot see another user's business. It leaves that small test data behind, so run it against a real
database only when you are happy with that.
"""
import json
import secrets
import sys
import time
import urllib.error
import urllib.request

failures = 0


def check(ok, text):
    global failures
    print(("PASS  " if ok else "FAIL  ") + text)
    if not ok:
        failures += 1


def call(base, method, path, body=None, token=None, timeout=60):
    """Returns (status, parsed JSON or None). Never raises for HTTP errors."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + path, data=data, method=method)
    if data:
        request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            return error.code, json.loads(raw)
        except ValueError:
            return error.code, None


def main(base):
    base = base.strip().rstrip("/")
    if "://" not in base:
        base = "https://" + base
    print(f"Checking {base}\n")
    check(base.startswith("https://") or base.startswith("http://127.0.0.1") or base.startswith("http://localhost"),
          "address uses HTTPS (or is this computer)")

    started = time.time()
    try:
        status, body = call(base, "GET", "/health")
    except (urllib.error.URLError, OSError) as problem:
        print(f"FAIL  cannot reach the server: {problem}")
        return 1
    check(status == 200 and body == {"status": "ok", "database": "ok"}, f"/health says the database is reachable ({time.time() - started:.1f}s, the first call may be slow)")
    if status != 200:
        print("      -> If this is 503: DATABASE_URL on Vercel is wrong or the database is asleep/unreachable. If 500: JWT_SECRET_KEY or DATABASE_URL is missing.")
        return 1

    tag = secrets.token_hex(4)
    email, password = f"deploycheck-{tag}@example.com", secrets.token_urlsafe(12)
    other_email = f"deploycheck-{tag}-b@example.com"
    status, user = call(base, "POST", "/auth/register", {"email": email, "full_name": "Deploy Check", "password": password})
    check(status == 201 and user and "access_token" in user, "register works")
    status, _ = call(base, "POST", "/auth/login", {"email": email, "password": "definitely-wrong"})
    check(status == 401, "wrong password is refused (401)")
    status, login = call(base, "POST", "/auth/login", {"email": email, "password": password})
    check(status == 200, "login works")
    token = login["access_token"]
    check(call(base, "GET", "/businesses")[0] == 401, "a request without a token is refused (401)")
    check(call(base, "GET", "/businesses", token="not.a.real.token")[0] == 401, "a forged token is refused (401)")

    status, business = call(base, "POST", "/businesses", {"name": f"Deploy check {tag}"}, token)
    check(status == 201, "business created")
    bid = business["id"]
    status, products = call(base, "GET", f"/businesses/{bid}/products", token=token)
    check(status == 200 and products == [], "a new business starts empty (nothing is hard-coded)")
    status, product = call(base, "POST", f"/businesses/{bid}/products",
                           {"name": "Check item", "sku": f"CHK-{tag}", "opening_quantity": 5}, token)
    check(status == 201 and product["quantity"] == 5, "product created with opening stock 5")
    status, moved = call(base, "POST", f"/businesses/{bid}/stock/out", {"product_id": product["id"], "quantity": 3}, token)
    check(status == 201 and moved["quantity_after"] == 2, "stock out 3 -> 2 left")
    status, _ = call(base, "POST", f"/businesses/{bid}/stock/out", {"product_id": product["id"], "quantity": 9}, token)
    check(status == 409, "taking 9 when 2 are left is refused (409): stock can never go negative")
    status, products = call(base, "GET", f"/businesses/{bid}/products", token=token)
    check(products and products[0]["quantity"] == 2, "quantity is still 2 after the refused request")
    status, history = call(base, "GET", f"/businesses/{bid}/transactions", token=token)
    check(status == 200 and len(history) == 2, "history has exactly the 2 recorded movements (opening + out)")

    status, other = call(base, "POST", "/auth/register", {"email": other_email, "full_name": "Other User", "password": password})
    other_token = other["access_token"] if status == 201 else None
    check(other_token is not None, "second user registered")
    if other_token:
        check(call(base, "GET", f"/businesses/{bid}/dashboard", token=other_token)[0] == 404,
              "a user who is not a member cannot see the business (404)")
        check(call(base, "POST", f"/businesses/{bid}/stock/in", {"product_id": product["id"], "quantity": 1}, other_token)[0] == 404,
              "...and cannot change its stock either (404)")

    print()
    print("ALL CHECKS PASSED" if failures == 0 else f"{failures} CHECK(S) FAILED")
    print(f"(Test data left behind: users {email} and {other_email}, business 'Deploy check {tag}'.)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
