import csv
import io
from datetime import datetime, timezone

from app.models import StockTransaction
from tests.conftest import auth_header, register
from tests.test_businesses import create_business


def setup(client):
    a = register(client, email="a@example.com", name="User A")
    b = register(client, email="b@example.com", name="User B")
    biz = create_business(client, a["access_token"], "ABC Electronics", default_min_stock=5)
    other = create_business(client, a["access_token"], "ABC Furniture")
    return a, b, biz, other


def product(client, user, biz, name, sku, qty, **extra):
    r = client.post(f"/businesses/{biz['id']}/products", json={"name": name, "sku": sku, "opening_quantity": qty, **extra},
                    headers=auth_header(user["access_token"]))
    assert r.status_code == 201, r.text
    return r.json()


def move(client, user, biz, kind, p, qty):
    r = client.post(f"/businesses/{biz['id']}/stock/{kind}", json={"product_id": p["id"], "quantity": qty}, headers=auth_header(user["access_token"]))
    assert r.status_code == 201, r.text


def get(client, user, biz, path, **params):
    return client.get(f"/businesses/{biz['id']}{path}", params=params, headers=auth_header(user["access_token"]))


def parse_csv(response):
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    return list(csv.reader(io.StringIO(response.text.lstrip("﻿"))))


# ---------- low stock / restock ----------

def test_low_stock_lists_low_and_out_with_suggested_order(client):
    a, _, biz, _ = setup(client)
    supplier = client.post(f"/businesses/{biz['id']}/suppliers", json={"name": "Volt"}, headers=auth_header(a["access_token"])).json()
    product(client, a, biz, "Fine", "F", 50)                                   # above the level of 5
    product(client, a, biz, "Edge", "E", 5, purchase_price="10")                # exactly at the level -> low
    product(client, a, biz, "Empty", "Z", 0, purchase_price="20", supplier_id=supplier["id"])
    product(client, a, biz, "Own level", "O", 8, min_stock=10, purchase_price="1")  # own level 10 beats default 5
    product(client, a, biz, "Zero level", "L", 0, min_stock=0, purchase_price="3")
    items = get(client, a, biz, "/reports/low-stock").json()
    assert [i["name"] for i in items] == ["Empty", "Zero level", "Edge", "Own level"]  # fewest first, ties by name
    by = {i["name"]: i for i in items}
    assert (by["Empty"]["suggested_order"], by["Empty"]["estimated_cost"], by["Empty"]["supplier_name"]) == (10, 200.0, "Volt")
    assert by["Edge"]["suggested_order"] == 5 and by["Edge"]["estimated_cost"] == 50.0
    assert by["Own level"]["alert_level"] == 10 and by["Own level"]["suggested_order"] == 12
    assert by["Zero level"]["suggested_order"] == 1  # never suggests 0


def test_low_stock_ignores_archived_and_reacts_to_stock_moves(client):
    a, _, biz, _ = setup(client)
    p = product(client, a, biz, "Cable", "C", 20)
    assert get(client, a, biz, "/reports/low-stock").json() == []
    move(client, a, biz, "out", p, 16)
    assert [i["quantity"] for i in get(client, a, biz, "/reports/low-stock").json()] == [4]
    move(client, a, biz, "in", p, 30)
    assert get(client, a, biz, "/reports/low-stock").json() == []
    move(client, a, biz, "out", p, 34)  # now 0: out of stock, so it WOULD be listed ...
    assert [i["quantity"] for i in get(client, a, biz, "/reports/low-stock").json()] == [0]
    client.delete(f"/businesses/{biz['id']}/products/{p['id']}", headers=auth_header(a["access_token"]))  # archived (has history)
    assert get(client, a, biz, "/reports/low-stock").json() == []  # ... but archived products are left out


# ---------- inventory by category ----------

def test_inventory_by_category(client):
    a, _, biz, _ = setup(client)
    cat = client.post(f"/businesses/{biz['id']}/categories", json={"name": "Cables"}, headers=auth_header(a["access_token"])).json()
    product(client, a, biz, "A", "A", 10, category_id=cat["id"], purchase_price="5")
    product(client, a, biz, "B", "B", 2, category_id=cat["id"], purchase_price="100")
    product(client, a, biz, "C", "C", 4, purchase_price="10")
    rows = get(client, a, biz, "/reports/inventory-by-category").json()
    assert rows == [{"category": "Cables", "product_count": 2, "units": 12, "value": 250.0},
                    {"category": "Uncategorised", "product_count": 1, "units": 4, "value": 40.0}]


def test_empty_business_reports_are_empty_not_errors(client):
    a, _, biz, _ = setup(client)
    assert get(client, a, biz, "/reports/inventory-by-category").json() == []
    m = get(client, a, biz, "/reports/movements").json()
    assert (m["units_in"], m["units_out"], m["transaction_count"], m["daily"], m["top_products"]) == (0, 0, 0, [], [])


# ---------- movement report ----------

def test_movement_totals_top_products_and_sales_value(client):
    a, _, biz, _ = setup(client)
    cable = product(client, a, biz, "Cable", "C", 100, selling_price="10")
    pen = product(client, a, biz, "Pen", "P", 50, selling_price="2")
    move(client, a, biz, "out", cable, 30)
    move(client, a, biz, "out", pen, 10)
    move(client, a, biz, "in", pen, 5)
    client.post(f"/businesses/{biz['id']}/stock/adjust", json={"product_id": pen["id"], "new_quantity": 40, "reason": "count"}, headers=auth_header(a["access_token"]))  # 45 -> 40
    m = get(client, a, biz, "/reports/movements").json()
    assert (m["units_in"], m["units_out"], m["net_adjustment"], m["transaction_count"]) == (155, 40, -5, 6)  # 150 opening + 5
    assert m["sales_value"] == 30 * 10 + 10 * 2
    assert [(t["name"], t["units_out"]) for t in m["top_products"]] == [("Cable", 30), ("Pen", 10)]
    assert len(m["daily"]) == 1 and (m["daily"][0]["units_in"], m["daily"][0]["units_out"]) == (155, 40)


def test_movement_report_buckets_days_in_the_callers_time_zone(client, db):
    a, _, biz, _ = setup(client)
    p = product(client, a, biz, "Cable", "C", 0)
    for when, change in ((datetime(2026, 11, 15, 20, 0, tzinfo=timezone.utc), 1),      # 16 Nov 01:30 in India
                         (datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc), 2)):     # 15 Nov 15:30 in India
        db.add(StockTransaction(business_id=biz["id"], product_id=p["id"], type="in", quantity_change=change,
                                quantity_after=change, created_at=when))
    db.commit()
    utc_days = {d["day"]: d["units_in"] for d in get(client, a, biz, "/reports/movements").json()["daily"]}
    assert utc_days == {"2026-11-15": 3}
    india_days = {d["day"]: d["units_in"] for d in get(client, a, biz, "/reports/movements", tz_offset_minutes=330).json()["daily"]}
    assert india_days == {"2026-11-15": 2, "2026-11-16": 1}
    assert get(client, a, biz, "/reports/movements", tz_offset_minutes=9999).status_code == 422


def test_movement_report_time_range(client, db):
    a, _, biz, _ = setup(client)
    p = product(client, a, biz, "Cable", "C", 0)
    for day in (10, 12, 14):
        db.add(StockTransaction(business_id=biz["id"], product_id=p["id"], type="out", quantity_change=-day,
                                quantity_after=0, created_at=datetime(2026, 11, day, 6, 0, tzinfo=timezone.utc)))
    db.commit()
    r = get(client, a, biz, "/reports/movements", from_time="2026-11-11T00:00:00+00:00", to_time="2026-11-14T06:00:00+00:00").json()
    assert r["units_out"] == 12  # only the 12th: 'to' is exclusive, so the 14th at 06:00 is out


# ---------- CSV exports ----------

def test_products_csv(client):
    a, _, biz, _ = setup(client)
    cat = client.post(f"/businesses/{biz['id']}/categories", json={"name": "Cables"}, headers=auth_header(a["access_token"])).json()
    product(client, a, biz, 'Cable, "long"', "C1", 7, category_id=cat["id"], purchase_price="12.5", selling_price="20")
    rows = parse_csv(get(client, a, biz, "/exports/products.csv"))
    assert rows[0][:3] == ["SKU", "Name", "Category"]
    assert rows[1] == ["C1", 'Cable, "long"', "Cables", "", "12.50", "20.00", "7", "5", "87.50", "active"]  # commas/quotes survive


def test_csv_cells_cannot_run_as_formulas(client):
    a, _, biz, _ = setup(client)
    product(client, a, biz, "=HYPERLINK(\"http://evil\")", "S1", 1)
    product(client, a, biz, "+cmd", "S2", 1)
    rows = parse_csv(get(client, a, biz, "/exports/products.csv"))
    names = sorted(r[1] for r in rows[1:])
    assert all(n.startswith("'") for n in names)


def test_transactions_csv_uses_callers_zone_and_range(client, db):
    a, _, biz, _ = setup(client)
    p = product(client, a, biz, "Cable", "C", 0)
    db.add(StockTransaction(business_id=biz["id"], product_id=p["id"], user_id=a["user"]["id"], type="in", quantity_change=4,
                            quantity_after=4, reason="Delivery", created_at=datetime(2026, 11, 15, 20, 0, tzinfo=timezone.utc)))
    db.commit()
    rows = parse_csv(get(client, a, biz, "/exports/transactions.csv", tz_offset_minutes=330))
    assert rows[0][0] == "Date and time"
    assert rows[-1] == ["2026-11-16 01:30", "C", "Cable", "in", "4", "4", "Delivery", "User A"]
    none = parse_csv(get(client, a, biz, "/exports/transactions.csv", from_time="2026-11-16T00:00:00+00:00"))
    assert len(none) == 1  # header only


def test_low_stock_csv(client):
    a, _, biz, _ = setup(client)
    product(client, a, biz, "Empty", "Z", 0, purchase_price="20")
    rows = parse_csv(get(client, a, biz, "/exports/low-stock.csv"))
    assert rows[1] == ["Z", "Empty", "", "0", "5", "10", "200.00"]


# ---------- security ----------

def test_reports_and_exports_are_isolated_and_need_login(client):
    a, b, biz, other = setup(client)
    secret = product(client, a, biz, "Secret", "S", 0)
    move(client, a, biz, "in", secret, 3)
    paths = ["/reports/low-stock", "/reports/inventory-by-category", "/reports/movements",
             "/exports/products.csv", "/exports/transactions.csv", "/exports/low-stock.csv"]
    for path in paths:
        assert client.get(f"/businesses/{biz['id']}{path}").status_code == 401, path
        assert get(client, b, biz, path).status_code == 404, path                 # not a member: cannot even tell it exists
    assert get(client, a, other, "/reports/low-stock").json() == []              # own other business: none of ABC Electronics' data
    assert "Secret" not in get(client, a, other, "/exports/products.csv").text
    # every report, asked for the OTHER business, must show none of ABC Electronics' data
    assert get(client, a, other, "/reports/inventory-by-category").json() == []
    m = get(client, a, other, "/reports/movements").json()
    assert (m["transaction_count"], m["daily"], m["top_products"]) == (0, [], [])
    assert len(parse_csv(get(client, a, other, "/exports/transactions.csv"))) == 1
    assert len(parse_csv(get(client, a, other, "/exports/low-stock.csv"))) == 1


def test_staff_can_read_reports(client):
    a, b, biz, _ = setup(client)
    client.post(f"/businesses/{biz['id']}/members", json={"email": "b@example.com"}, headers=auth_header(a["access_token"]))
    assert get(client, b, biz, "/reports/low-stock").status_code == 200
    assert get(client, b, biz, "/exports/products.csv").status_code == 200
