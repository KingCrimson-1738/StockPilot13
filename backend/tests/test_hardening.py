"""Final safety nets: every business route is guarded, and a few security details."""
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app import config
from app.deps import get_member, get_owner_member
from app.main import app
from tests.conftest import auth_header, register


def all_dependencies(dependant):
    """Every dependency function a route needs, including dependencies of dependencies."""
    found = set()
    for sub in dependant.dependencies:
        found.add(sub.call)
        found |= all_dependencies(sub)
    return found


def all_routes():
    """(methods, path, dependencies) of every route in the project's routers.
    A router's routes already carry its prefix, so path is the full URL path."""
    from app.routers import auth, businesses, categories, dashboard, products, reports, stock, suppliers
    found = []
    for module in (auth, businesses, categories, dashboard, products, reports, stock, suppliers):
        for route in module.router.routes:
            if isinstance(route, APIRoute):
                found.append((tuple(sorted(route.methods)), route.path, all_dependencies(route.dependant)))
    return found


def test_every_route_is_really_part_of_the_app():
    """The routers we inspect are the ones the app serves (so the next two tests are not checking a phantom list)."""
    served = {path for path in app.openapi()["paths"]}
    inspected = {path for _, path, _ in all_routes()}
    assert inspected <= served
    assert len(inspected) >= 25


def test_every_route_with_a_business_id_checks_membership():
    """If someone adds a new /businesses/{business_id}/... route and forgets get_member, this test fails."""
    business_routes = [(m, p, d) for m, p, d in all_routes() if "{business_id}" in p]
    assert len(business_routes) >= 29, f"only {len(business_routes)} business routes found: did the router list change?"
    unguarded = [f"{m} {p}" for m, p, d in business_routes if not ({get_member, get_owner_member} & d)]
    assert unguarded == []


def test_only_the_expected_routes_are_public():
    """Anything reachable without logging in must be on this list."""
    from app.deps import get_current_user
    public = [(m, p) for m, p, d in all_routes() if get_current_user not in d]
    assert sorted(public) == [(("POST",), "/auth/login"), (("POST",), "/auth/register")]
    assert {"/", "/health"} <= set(app.openapi()["paths"])   # the two health URLs are defined in main.py, deliberately public


def test_token_without_expiry_is_rejected(client):
    user = register(client, email="a@example.com")
    forever = jwt.encode({"sub": str(user["user"]["id"])}, config.JWT_SECRET_KEY, algorithm="HS256")
    assert client.get("/auth/me", headers=auth_header(forever)).status_code == 401
    good = jwt.encode({"sub": str(user["user"]["id"]), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                      config.JWT_SECRET_KEY, algorithm="HS256")
    assert client.get("/auth/me", headers=auth_header(good)).status_code == 200


def test_expired_and_wrongly_signed_tokens_are_rejected(client):
    user = register(client, email="a@example.com")
    sub = str(user["user"]["id"])
    expired = jwt.encode({"sub": sub, "exp": datetime.now(timezone.utc) - timedelta(seconds=5)}, config.JWT_SECRET_KEY, algorithm="HS256")
    forged = jwt.encode({"sub": sub, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, "some-other-secret-that-is-long-enough!!", algorithm="HS256")
    assert client.get("/auth/me", headers=auth_header(expired)).status_code == 401
    assert client.get("/auth/me", headers=auth_header(forged)).status_code == 401


def test_token_of_a_user_that_no_longer_exists_is_rejected(client):
    ghost = jwt.encode({"sub": "99999", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, config.JWT_SECRET_KEY, algorithm="HS256")
    assert client.get("/auth/me", headers=auth_header(ghost)).status_code == 401


def test_unknown_email_costs_as_much_work_as_a_wrong_password(client, monkeypatch):
    """Timing safety: the password check must run even when the email does not exist."""
    from app.routers import auth
    register(client, email="real@example.com")
    calls = []
    original = auth.verify_password
    monkeypatch.setattr(auth, "verify_password", lambda password, hashed: calls.append(hashed) or original(password, hashed))
    assert client.post("/auth/login", json={"email": "nobody@example.com", "password": "password123"}).status_code == 401
    assert len(calls) == 1 and calls[0] == auth.DUMMY_HASH
    assert client.post("/auth/login", json={"email": "real@example.com", "password": "wrong-password"}).status_code == 401
    assert len(calls) == 2


def test_password_hash_is_never_returned_by_the_api(client):
    user = register(client, email="a@example.com")
    assert "password" not in str(user).lower().replace("access_token", "")
    assert "password" not in client.get("/auth/me", headers=auth_header(user["access_token"])).text.lower()


# ---------- values the database cannot store: a clean 422, never a 500, and nothing saved ----------

def test_ids_too_big_for_the_database_give_422_not_500(client):
    user = register(client, email="a@example.com")
    h = auth_header(user["access_token"])
    biz = client.post("/businesses", json={"name": "Shop"}, headers=h).json()
    base = f"/businesses/{biz['id']}"
    huge = 99999999999999999999
    quiet = TestClient(app, raise_server_exceptions=False)   # a 500 must show up as a status code, not as a raised error
    h = auth_header(user["access_token"])
    for response in (
        quiet.get(f"/businesses/{huge}", headers=h),
        quiet.post(f"{base}/stock/in", json={"product_id": huge, "quantity": 1}, headers=h),
        quiet.post(f"{base}/products", json={"name": "x", "sku": "x1", "category_id": huge}, headers=h),
        quiet.get(f"{base}/products", params={"supplier_id": huge}, headers=h),
        quiet.get(f"{base}/products", params={"category_id": huge}, headers=h),
        quiet.get(f"{base}/transactions", params={"product_id": huge, "offset": huge}, headers=h),
    ):
        assert response.status_code in (404, 422), response.text
        assert "Traceback" not in response.text and "psycopg" not in response.text


def test_nul_characters_give_422_and_nothing_is_saved(client):
    user = register(client, email="a@example.com")
    h = auth_header(user["access_token"])
    biz = client.post("/businesses", json={"name": "Shop"}, headers=h).json()
    base = f"/businesses/{biz['id']}"
    quiet = TestClient(app, raise_server_exceptions=False)
    assert quiet.post(f"{base}/products", json={"name": "a\x00b", "sku": "N1"}, headers=h).status_code == 422
    assert quiet.get(f"{base}/products", params={"search": "a\x00b"}, headers=h).status_code in (200, 422)
    assert quiet.post("/auth/register", json={"email": "z@example.com", "full_name": "a\x00b", "password": "password123"}).status_code == 422
    assert client.get(f"{base}/products", headers=h).json() == []                       # no half-created product
    assert client.post("/auth/login", json={"email": "z@example.com", "password": "password123"}).status_code == 401  # no half-created user


def test_a_rejected_stock_movement_with_a_bad_reason_changes_nothing(client):
    user = register(client, email="a@example.com")
    h = auth_header(user["access_token"])
    biz = client.post("/businesses", json={"name": "Shop"}, headers=h).json()
    base = f"/businesses/{biz['id']}"
    product = client.post(f"{base}/products", json={"name": "Cable", "sku": "C1", "opening_quantity": 10}, headers=h).json()
    quiet = TestClient(app, raise_server_exceptions=False)
    bad = quiet.post(f"{base}/stock/out", json={"product_id": product["id"], "quantity": 4, "reason": "a\x00b"}, headers=h)
    assert bad.status_code == 422
    assert client.get(f"{base}/products", headers=h).json()[0]["quantity"] == 10        # the quantity was rolled back too
    assert len(client.get(f"{base}/transactions", headers=h).json()) == 1               # only the opening stock
