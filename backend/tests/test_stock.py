import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.models import Product, StockTransaction
from tests.conftest import auth_header, register
from tests.test_businesses import create_business


def setup(client):
    a = register(client, email="a@example.com", name="User A")
    b = register(client, email="b@example.com", name="User B")
    electronics = create_business(client, a["access_token"], "ABC Electronics", default_min_stock=5)
    furniture = create_business(client, a["access_token"], "ABC Furniture")
    return a, b, electronics, furniture


def make_product(client, user, business, name="Cable", sku="C1", qty=10):
    response = client.post(f"/businesses/{business['id']}/products", json={"name": name, "sku": sku, "opening_quantity": qty},
                           headers=auth_header(user["access_token"]))
    assert response.status_code == 201, response.text
    return response.json()


def move(client, user, business, kind, product, quantity, reason=None, expect=201):
    body = {"product_id": product["id"], "quantity": quantity}
    if reason is not None:
        body["reason"] = reason
    response = client.post(f"/businesses/{business['id']}/stock/{kind}", json=body, headers=auth_header(user["access_token"]))
    assert response.status_code == expect, response.text
    return response.json()


def adjust(client, user, business, product, new_quantity, reason="Stock count", expect=201):
    body = {"product_id": product["id"], "new_quantity": new_quantity, "reason": reason}
    response = client.post(f"/businesses/{business['id']}/stock/adjust", json=body, headers=auth_header(user["access_token"]))
    assert response.status_code == expect, response.text
    return response.json()


def quantity_of(client, user, business, product):
    products = client.get(f"/businesses/{business['id']}/products", headers=auth_header(user["access_token"]), params={"archived": "all"}).json()
    return next(p["quantity"] for p in products if p["id"] == product["id"])


def history(client, user, business, **params):
    response = client.get(f"/businesses/{business['id']}/transactions", params=params, headers=auth_header(user["access_token"]))
    assert response.status_code == 200, response.text
    return response.json()


# ---------- stock in / out ----------

def test_stock_in_increases_quantity_and_records_a_transaction(client):
    a, _, electronics, _ = setup(client)
    product = make_product(client, a, electronics, qty=10)
    t = move(client, a, electronics, "in", product, 5, reason="Supplier delivery")
    assert (t["type"], t["quantity_change"], t["quantity_after"], t["reason"], t["user_name"]) == ("in", 5, 15, "Supplier delivery", "User A")
    assert quantity_of(client, a, electronics, product) == 15
    assert history(client, a, electronics)[0]["id"] == t["id"]


def test_stock_out_decreases_quantity(client):
    a, _, electronics, _ = setup(client)
    product = make_product(client, a, electronics, qty=10)
    t = move(client, a, electronics, "out", product, 4, reason="Sale")
    assert (t["type"], t["quantity_change"], t["quantity_after"]) == ("out", -4, 6)
    assert quantity_of(client, a, electronics, product) == 6


def test_cannot_remove_more_than_available_and_nothing_is_recorded(client):
    a, _, electronics, _ = setup(client)
    product = make_product(client, a, electronics, qty=3)
    rejected = move(client, a, electronics, "out", product, 5, expect=409)
    assert "Available: 3" in rejected["detail"] and "requested: 5" in rejected["detail"]
    assert quantity_of(client, a, electronics, product) == 3
    assert len(history(client, a, electronics)) == 1  # only the opening stock


def test_removing_exactly_all_stock_is_allowed_and_marks_out_of_stock(client):
    a, _, electronics, _ = setup(client)
    product = make_product(client, a, electronics, qty=3)
    assert move(client, a, electronics, "out", product, 3)["quantity_after"] == 0
    listed = client.get(f"/businesses/{electronics['id']}/products", headers=auth_header(a["access_token"])).json()[0]
    assert listed["stock_status"] == "out"
    move(client, a, electronics, "out", product, 1, expect=409)  # and now nothing is left


def test_quantity_must_be_a_positive_whole_number(client):
    a, _, electronics, _ = setup(client)
    product = make_product(client, a, electronics)
    for bad in (0, -5, 1.5, 1_000_001):
        move(client, a, electronics, "in", product, bad, expect=422)
        move(client, a, electronics, "out", product, bad, expect=422)
    move(client, a, electronics, "in", product, 1, reason="x" * 256, expect=422)
    assert quantity_of(client, a, electronics, product) == 10


def test_blank_reason_is_stored_as_nothing(client):
    a, _, electronics, _ = setup(client)
    product = make_product(client, a, electronics)
    assert move(client, a, electronics, "in", product, 1, reason="   ")["reason"] is None


def test_unknown_product_and_archived_product_are_rejected(client):
    a, _, electronics, _ = setup(client)
    product = make_product(client, a, electronics, qty=5)
    move(client, a, electronics, "in", {"id": 999999}, 1, expect=404)
    client.delete(f"/businesses/{electronics['id']}/products/{product['id']}", headers=auth_header(a["access_token"]))  # archives it
    for kind in ("in", "out"):
        assert "archived" in move(client, a, electronics, kind, product, 1, expect=400)["detail"]
    assert "archived" in adjust(client, a, electronics, product, 9, expect=400)["detail"]


def test_product_of_another_business_cannot_be_moved_through_this_url(client):
    a, _, electronics, furniture = setup(client)
    chair = make_product(client, a, furniture, "Chair", "CH1", qty=7)
    move(client, a, electronics, "out", chair, 1, expect=404)
    adjust(client, a, electronics, chair, 0, expect=404)
    assert quantity_of(client, a, furniture, chair) == 7


def test_login_and_membership_required(client):
    a, b, electronics, _ = setup(client)
    product = make_product(client, a, electronics)
    body = {"product_id": product["id"], "quantity": 1}
    assert client.post(f"/businesses/{electronics['id']}/stock/in", json=body).status_code == 401
    assert client.post(f"/businesses/{electronics['id']}/stock/in", json=body, headers=auth_header(b["access_token"])).status_code == 404
    assert client.get(f"/businesses/{electronics['id']}/transactions", headers=auth_header(b["access_token"])).status_code == 404


def test_staff_can_move_stock_and_is_named_in_the_history(client):
    a, b, electronics, _ = setup(client)
    client.post(f"/businesses/{electronics['id']}/members", json={"email": "b@example.com"}, headers=auth_header(a["access_token"]))
    product = make_product(client, a, electronics, qty=10)
    assert move(client, b, electronics, "out", product, 2)["user_name"] == "User B"
    assert history(client, b, electronics)[0]["user_name"] == "User B"


# ---------- adjust ----------

def test_adjust_sets_the_counted_quantity_and_records_the_difference(client):
    a, _, electronics, _ = setup(client)
    product = make_product(client, a, electronics, qty=10)
    down = adjust(client, a, electronics, product, 7, reason="Damaged in storage")
    assert (down["type"], down["quantity_change"], down["quantity_after"], down["reason"]) == ("adjust", -3, 7, "Damaged in storage")
    up = adjust(client, a, electronics, product, 12, reason="Found extra box")
    assert (up["quantity_change"], up["quantity_after"]) == (5, 12)
    assert adjust(client, a, electronics, product, 0, reason="Write off")["quantity_after"] == 0


def test_adjust_needs_a_real_reason_a_change_and_the_owner(client):
    a, b, electronics, _ = setup(client)
    client.post(f"/businesses/{electronics['id']}/members", json={"email": "b@example.com"}, headers=auth_header(a["access_token"]))
    product = make_product(client, a, electronics, qty=10)
    adjust(client, a, electronics, product, 8, reason="", expect=422)
    adjust(client, a, electronics, product, 8, reason="ab", expect=422)
    adjust(client, a, electronics, product, -1, expect=422)
    assert "nothing to adjust" in adjust(client, a, electronics, product, 10, expect=400)["detail"]
    adjust(client, b, electronics, product, 8, expect=403)  # staff may not adjust
    assert quantity_of(client, a, electronics, product) == 10


# ---------- the books always balance ----------

def test_every_movement_is_recorded_and_the_history_adds_up_to_the_quantity(client, db):
    a, _, electronics, _ = setup(client)
    product = make_product(client, a, electronics, qty=10)
    move(client, a, electronics, "in", product, 25)
    move(client, a, electronics, "out", product, 8)
    adjust(client, a, electronics, product, 20)
    move(client, a, electronics, "out", product, 20)
    move(client, a, electronics, "in", product, 6)
    move(client, a, electronics, "out", product, 99, expect=409)  # rejected: must leave no trace

    rows = db.scalars(select(StockTransaction).where(StockTransaction.product_id == product["id"]).order_by(StockTransaction.id)).all()
    assert len(rows) == 6  # opening + 5 successful movements
    running = 0
    for t in rows:
        running += t.quantity_change
        assert t.quantity_after == running  # each row's 'after' follows from the one before
    stored = db.get(Product, product["id"]).quantity
    assert stored == running == 6
    assert db.scalar(select(func.sum(StockTransaction.quantity_change)).where(StockTransaction.product_id == product["id"])) == stored


def test_dashboard_shows_the_new_movements(client):
    a, _, electronics, _ = setup(client)
    product = make_product(client, a, electronics, qty=10)
    move(client, a, electronics, "out", product, 4, reason="Sale")
    dash = client.get(f"/businesses/{electronics['id']}/dashboard", headers=auth_header(a["access_token"])).json()
    assert dash["total_stock"] == 6 and dash["recent_transactions"][0]["quantity_change"] == -4


def test_a_failure_in_the_middle_saves_nothing(client, db, monkeypatch):
    """Atomicity: if recording the transaction blows up, the quantity change must be rolled back too."""
    a, _, electronics, _ = setup(client)
    product = make_product(client, a, electronics, qty=10)

    def explode(*args, **kwargs):
        raise RuntimeError("simulated crash while recording the transaction")

    monkeypatch.setattr("app.routers.stock.StockTransaction", explode)
    quiet_client = TestClient(app, raise_server_exceptions=False)
    response = quiet_client.post(f"/businesses/{electronics['id']}/stock/out", json={"product_id": product["id"], "quantity": 4},
                                 headers=auth_header(a["access_token"]))
    assert response.status_code == 500
    assert db.get(Product, product["id"]).quantity == 10  # unchanged
    assert db.scalar(select(func.count(StockTransaction.id)).where(StockTransaction.reason.is_(None), StockTransaction.type == "out")) == 0


def test_simultaneous_stock_outs_never_oversell(db):
    """10 people each remove 3 units from a stock of 10 at the very same moment.
    Only 3 can succeed (9 units); the rest must be refused; the final stock must be exactly 1."""
    setup_client = TestClient(app)
    a, _, electronics, _ = setup(setup_client)
    product = make_product(setup_client, a, electronics, qty=10)
    token = a["access_token"]
    url = f"/businesses/{electronics['id']}/stock/out"
    start_together = threading.Barrier(10)

    def remove_three(_):
        own_client = TestClient(app)  # every thread gets its own client and its own database connection
        start_together.wait()
        return own_client.post(url, json={"product_id": product["id"], "quantity": 3}, headers=auth_header(token)).status_code

    with ThreadPoolExecutor(max_workers=10) as pool:
        statuses = list(pool.map(remove_three, range(10)))

    assert sorted(statuses) == [201] * 3 + [409] * 7
    assert db.get(Product, product["id"]).quantity == 1
    outs = db.scalars(select(StockTransaction).where(StockTransaction.type == "out").order_by(StockTransaction.id)).all()
    assert len(outs) == 3 and [t.quantity_after for t in outs] == [7, 4, 1]


# ---------- history ----------

def test_history_filters_by_product_and_type_and_is_newest_first(client):
    a, _, electronics, _ = setup(client)
    cable = make_product(client, a, electronics, "Cable", "C1", qty=10)
    pen = make_product(client, a, electronics, "Pen", "P1", qty=20)
    move(client, a, electronics, "out", cable, 1)
    move(client, a, electronics, "in", pen, 5)
    adjust(client, a, electronics, cable, 3)

    everything = history(client, a, electronics)
    assert [(t["product_name"], t["type"]) for t in everything] == [("Cable", "adjust"), ("Pen", "in"), ("Cable", "out"), ("Pen", "in"), ("Cable", "in")]
    assert [t["type"] for t in history(client, a, electronics, product_id=cable["id"])] == ["adjust", "out", "in"]
    assert [t["product_name"] for t in history(client, a, electronics, type="in")] == ["Pen", "Pen", "Cable"]  # newest first
    assert len(history(client, a, electronics, type="in")) == 3  # the two opening stocks + Pen's stock-in
    assert len(history(client, a, electronics, type="adjust")) == 1
    assert history(client, a, electronics, product_id=cable["id"], type="out")[0]["quantity_change"] == -1
    assert client.get(f"/businesses/{electronics['id']}/transactions", params={"type": "bogus"}, headers=auth_header(a["access_token"])).status_code == 422


def test_history_limit_and_offset(client):
    a, _, electronics, _ = setup(client)
    product = make_product(client, a, electronics, qty=1)
    for _ in range(5):
        move(client, a, electronics, "in", product, 1)
    ids = [t["id"] for t in history(client, a, electronics)]
    assert [t["id"] for t in history(client, a, electronics, limit=2)] == ids[:2]
    assert [t["id"] for t in history(client, a, electronics, limit=2, offset=2)] == ids[2:4]
    assert client.get(f"/businesses/{electronics['id']}/transactions", params={"limit": 501}, headers=auth_header(a["access_token"])).status_code == 422


def test_history_time_range_uses_exact_utc_times(client, db):
    a, _, electronics, _ = setup(client)
    product = make_product(client, a, electronics, qty=0)
    base = datetime(2026, 11, 15, 20, 0, tzinfo=timezone.utc)  # = 16 Nov 01:30 in India
    for hours in (0, 5, 30):
        db.add(StockTransaction(business_id=electronics["id"], product_id=product["id"], type="in", quantity_change=1,
                                quantity_after=1, reason=f"+{hours}h", created_at=base + timedelta(hours=hours)))
    db.commit()

    def reasons(**params):
        return sorted(t["reason"] for t in history(client, a, electronics, **params))

    # "16 November" for a user in India (UTC+5:30) is 2026-11-15T18:30Z up to 2026-11-16T18:30Z
    day = {"from_time": "2026-11-15T18:30:00+00:00", "to_time": "2026-11-16T18:30:00+00:00"}
    assert reasons(**day) == ["+0h", "+5h"]
    assert reasons(from_time="2026-11-15T20:00:00+00:00") == ["+0h", "+30h", "+5h"]       # 'from' is inclusive
    assert reasons(to_time="2026-11-15T20:00:00+00:00") == []                             # 'to' is exclusive
    assert reasons(from_time="2026-11-15T20:00:01+00:00", to_time="2026-11-16T02:00:00+00:00") == ["+5h"]
    assert reasons(from_time="2026-11-16T00:00:00") == ["+30h", "+5h"]                    # no zone given: taken as UTC


def test_history_is_isolated_between_businesses(client):
    a, b, electronics, furniture = setup(client)
    make_product(client, a, electronics, "Cable", "C1", qty=10)
    make_product(client, a, furniture, "Chair", "CH1", qty=3)
    assert [t["product_name"] for t in history(client, a, electronics)] == ["Cable"]
    assert [t["product_name"] for t in history(client, a, furniture)] == ["Chair"]
    assert client.get(f"/businesses/{furniture['id']}/transactions", headers=auth_header(b["access_token"])).status_code == 404
