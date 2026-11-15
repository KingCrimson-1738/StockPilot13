from datetime import datetime, timedelta, timezone

from app.models import Product, StockTransaction
from tests.conftest import auth_header, register
from tests.test_businesses import create_business


def add_product(db, business_id, name, quantity, price, min_stock=None, archived=False):
    product = Product(
        business_id=business_id, name=name, sku=name.upper(), quantity=quantity,
        purchase_price=price, selling_price=price * 2, min_stock=min_stock, is_archived=archived,
    )
    db.add(product)
    db.commit()
    return product


def get_dashboard(client, token, business_id):
    return client.get(f"/businesses/{business_id}/dashboard", headers=auth_header(token))


def test_empty_business_has_zero_everything(client):
    token = register(client)["access_token"]
    business = create_business(client, token)
    data = get_dashboard(client, token, business["id"]).json()
    assert data == {
        "currency": "INR", "total_products": 0, "total_stock": 0, "inventory_value": 0.0,
        "low_stock_count": 0, "out_of_stock_count": 0, "recent_transactions": [],
    }


def test_numbers_are_calculated_from_real_rows(client, db):
    token = register(client)["access_token"]
    business = create_business(client, token, default_min_stock=5)
    bid = business["id"]
    add_product(db, bid, "Cable", 20, 10)                # healthy:     value 200
    add_product(db, bid, "Mouse", 3, 100)                # low (3 <= 5): value 300
    add_product(db, bid, "Laptop", 0, 5000)              # out of stock: value 0
    add_product(db, bid, "Phone", 8, 1000, min_stock=10) # low via its own limit (8 <= 10): value 8000
    add_product(db, bid, "Old", 50, 1, archived=True)    # archived: ignored everywhere

    data = get_dashboard(client, token, bid).json()
    assert data["total_products"] == 4
    assert data["total_stock"] == 31
    assert data["inventory_value"] == 8500.0
    assert data["low_stock_count"] == 2
    assert data["out_of_stock_count"] == 1


def test_recent_transactions_newest_first_and_limited_to_ten(client, db):
    owner = register(client, name="Asha Owner")
    business = create_business(client, owner["access_token"])
    product = add_product(db, business["id"], "Cable", 100, 10)
    start = datetime.now(timezone.utc) - timedelta(hours=1)
    for i in range(12):
        db.add(StockTransaction(
            business_id=business["id"], product_id=product.id, user_id=owner["user"]["id"],
            type="in", quantity_change=1, quantity_after=i + 1, reason=f"batch {i}",
            created_at=start + timedelta(minutes=i),
        ))
    db.commit()

    recent = get_dashboard(client, owner["access_token"], business["id"]).json()["recent_transactions"]
    assert len(recent) == 10
    assert recent[0]["reason"] == "batch 11"
    assert recent[0]["product_name"] == "Cable"
    assert recent[0]["user_name"] == "Asha Owner"


def test_dashboard_only_counts_its_own_business(client, db):
    token = register(client)["access_token"]
    electronics = create_business(client, token, "ABC Electronics")
    furniture = create_business(client, token, "ABC Furniture")
    add_product(db, electronics["id"], "Cable", 10, 10)
    add_product(db, furniture["id"], "Chair", 4, 500)

    assert get_dashboard(client, token, electronics["id"]).json()["total_stock"] == 10
    assert get_dashboard(client, token, furniture["id"]).json()["inventory_value"] == 2000.0


def test_dashboard_access_rules(client, db):
    a = register(client, email="a@example.com")
    b = register(client, email="b@example.com")
    business = create_business(client, a["access_token"])
    assert get_dashboard(client, b["access_token"], business["id"]).status_code == 404
    assert client.get(f"/businesses/{business['id']}/dashboard").status_code == 401
    # staff may view it
    client.post(f"/businesses/{business['id']}/members", json={"email": "b@example.com"},
                headers=auth_header(a["access_token"]))
    assert get_dashboard(client, b["access_token"], business["id"]).status_code == 200


def test_changing_default_threshold_changes_low_stock_count(client, db):
    token = register(client)["access_token"]
    business = create_business(client, token, default_min_stock=5)
    add_product(db, business["id"], "Mouse", 8, 100)
    assert get_dashboard(client, token, business["id"]).json()["low_stock_count"] == 0
    client.put(f"/businesses/{business['id']}", json={"name": "ABC Electronics", "default_min_stock": 10},
               headers=auth_header(token))
    assert get_dashboard(client, token, business["id"]).json()["low_stock_count"] == 1
