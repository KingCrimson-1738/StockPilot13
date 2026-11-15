from sqlalchemy import select

from app.models import Product, StockTransaction, Supplier
from tests.conftest import auth_header, register
from tests.test_businesses import create_business


def setup(client):
    a = register(client, email="a@example.com")
    b = register(client, email="b@example.com", name="User B")
    electronics = create_business(client, a["access_token"], "ABC Electronics", default_min_stock=5)
    furniture = create_business(client, a["access_token"], "ABC Furniture")
    return a, b, electronics, furniture


def url(business, extra=""):
    return f"/businesses/{business['id']}/products{extra}"


def new_category(client, user, business, name):
    return client.post(f"/businesses/{business['id']}/categories", json={"name": name},
                       headers=auth_header(user["access_token"])).json()


def new_product(client, user, business, name="Cable", sku="CBL-1", expect=201, **extra):
    body = {"name": name, "sku": sku, "purchase_price": 10, "selling_price": 15, **extra}
    response = client.post(url(business), json=body, headers=auth_header(user["access_token"]))
    assert response.status_code == expect, response.text
    return response.json()


def listing(client, user, business, **params):
    response = client.get(url(business), params=params, headers=auth_header(user["access_token"]))
    assert response.status_code == 200, response.text
    return [p["name"] for p in response.json()]


def add_staff(client, owner, staff, business):
    client.post(f"/businesses/{business['id']}/members", json={"email": "b@example.com"}, headers=auth_header(owner["access_token"]))


# ---------- create ----------

def test_create_product_returns_names_and_status(client):
    a, _, electronics, _ = setup(client)
    cat = new_category(client, a, electronics, "Cables")
    product = new_product(client, a, electronics, category_id=cat["id"], opening_quantity=20, min_stock=8)
    assert product["category_name"] == "Cables"
    assert product["quantity"] == 20 and product["alert_level"] == 8 and product["stock_status"] == "ok"
    assert product["purchase_price"] == 10.0 and product["is_archived"] is False


def test_opening_quantity_creates_a_stock_in_transaction(client, db):
    a, _, electronics, _ = setup(client)
    product = new_product(client, a, electronics, opening_quantity=12)
    transactions = db.scalars(select(StockTransaction).where(StockTransaction.product_id == product["id"])).all()
    assert len(transactions) == 1
    t = transactions[0]
    assert (t.type, t.quantity_change, t.quantity_after, t.reason, t.user_id) == ("in", 12, 12, "Opening stock", a["user"]["id"])
    assert t.business_id == electronics["id"]


def test_zero_opening_quantity_means_out_of_stock_and_no_transaction(client, db):
    a, _, electronics, _ = setup(client)
    product = new_product(client, a, electronics)
    assert product["quantity"] == 0 and product["stock_status"] == "out"
    assert db.scalars(select(StockTransaction)).all() == []


def test_duplicate_sku_rejected_within_a_business_only(client):
    a, _, electronics, furniture = setup(client)
    new_product(client, a, electronics, sku="PEN-1")
    new_product(client, a, electronics, name="Other", sku="pen-1", expect=409)  # case-insensitive
    new_product(client, a, furniture, name="Pen", sku="PEN-1")  # other business: fine


def test_validation(client):
    a, _, electronics, _ = setup(client)
    new_product(client, a, electronics, name="  ", expect=422)
    new_product(client, a, electronics, sku="", expect=422)
    new_product(client, a, electronics, purchase_price=-1, expect=422)
    new_product(client, a, electronics, selling_price=1.999, expect=422)  # at most 2 decimals
    new_product(client, a, electronics, opening_quantity=-5, expect=422)
    new_product(client, a, electronics, min_stock=-1, expect=422)


def test_category_from_another_business_is_rejected(client):
    a, _, electronics, furniture = setup(client)
    foreign = new_category(client, a, furniture, "Chairs")
    response = client.post(url(electronics), json={"name": "Cable", "sku": "C1", "category_id": foreign["id"]},
                           headers=auth_header(a["access_token"]))
    assert response.status_code == 400
    ok = new_product(client, a, electronics)
    update = {"name": "Cable", "sku": "CBL-1", "category_id": foreign["id"]}
    assert client.put(url(electronics, f"/{ok['id']}"), json=update, headers=auth_header(a["access_token"])).status_code == 400


def test_supplier_from_another_business_is_rejected(client, db):
    a, _, electronics, furniture = setup(client)
    supplier = Supplier(business_id=furniture["id"], name="Wood Co")
    db.add(supplier)
    db.commit()
    new_product(client, a, electronics, supplier_id=supplier.id, expect=400)
    own = Supplier(business_id=electronics["id"], name="Volt Ltd")
    db.add(own)
    db.commit()
    assert new_product(client, a, electronics, supplier_id=own.id)["supplier_name"] == "Volt Ltd"


# ---------- list, search, filters ----------

def seed_listing(client, a, electronics):
    cables = new_category(client, a, electronics, "Cables")
    phones = new_category(client, a, electronics, "Phones")
    new_product(client, a, electronics, "USB Cable", "CBL-1", category_id=cables["id"], opening_quantity=50)   # ok
    new_product(client, a, electronics, "HDMI Cable", "CBL-2", category_id=cables["id"], opening_quantity=3)   # low (default 5)
    new_product(client, a, electronics, "Phone X", "PH-X", category_id=phones["id"], opening_quantity=8, min_stock=10)  # low (own level)
    new_product(client, a, electronics, "Charger", "CHG-1")                                                    # out
    return cables, phones


def test_list_is_sorted_and_search_matches_name_or_sku(client):
    a, _, electronics, _ = setup(client)
    seed_listing(client, a, electronics)
    assert listing(client, a, electronics) == ["Charger", "HDMI Cable", "Phone X", "USB Cable"]
    assert listing(client, a, electronics, search="cable") == ["HDMI Cable", "USB Cable"]
    assert listing(client, a, electronics, search="ph-x") == ["Phone X"]
    assert listing(client, a, electronics, search="%") == []  # '%' is searched literally, not as a wildcard


def test_filter_by_category_and_stock_level(client):
    a, _, electronics, _ = setup(client)
    cables, _ = seed_listing(client, a, electronics)
    assert listing(client, a, electronics, category_id=cables["id"]) == ["HDMI Cable", "USB Cable"]
    assert listing(client, a, electronics, stock="out") == ["Charger"]
    assert listing(client, a, electronics, stock="low") == ["HDMI Cable", "Phone X"]
    assert listing(client, a, electronics, stock="ok") == ["USB Cable"]
    assert listing(client, a, electronics, stock="low", category_id=cables["id"]) == ["HDMI Cable"]
    assert client.get(url(electronics), params={"stock": "bogus"}, headers=auth_header(a["access_token"])).status_code == 422


def test_list_only_shows_this_business(client):
    a, b, electronics, furniture = setup(client)
    new_product(client, a, electronics, "Cable", "C1")
    new_product(client, a, furniture, "Chair", "CH1")
    assert listing(client, a, electronics) == ["Cable"]
    assert listing(client, a, furniture) == ["Chair"]
    assert client.get(url(electronics), headers=auth_header(b["access_token"])).status_code == 404


# ---------- edit ----------

def test_update_changes_fields_but_never_the_quantity(client):
    a, _, electronics, _ = setup(client)
    product = new_product(client, a, electronics, opening_quantity=10)
    body = {"name": "Cable 2m", "sku": "CBL-2M", "purchase_price": 12.5, "selling_price": 20, "min_stock": 3, "quantity": 9999}
    response = client.put(url(electronics, f"/{product['id']}"), json=body, headers=auth_header(a["access_token"]))
    assert response.status_code == 200
    saved = response.json()
    assert (saved["name"], saved["sku"], saved["purchase_price"], saved["min_stock"]) == ("Cable 2m", "CBL-2M", 12.5, 3)
    assert saved["quantity"] == 10  # the 'quantity' we tried to sneak in was ignored


def test_update_keeps_own_sku_but_cannot_take_anothers(client):
    a, _, electronics, _ = setup(client)
    first = new_product(client, a, electronics, "One", "SKU-1")
    new_product(client, a, electronics, "Two", "SKU-2")
    header = auth_header(a["access_token"])
    assert client.put(url(electronics, f"/{first['id']}"), json={"name": "One!", "sku": "SKU-1"}, headers=header).status_code == 200
    assert client.put(url(electronics, f"/{first['id']}"), json={"name": "One", "sku": "sku-2"}, headers=header).status_code == 409


def test_product_of_another_business_cannot_be_touched_through_this_url(client):
    a, b, electronics, furniture = setup(client)
    chair = new_product(client, a, furniture, "Chair", "CH1")
    header = auth_header(a["access_token"])
    assert client.put(url(electronics, f"/{chair['id']}"), json={"name": "X", "sku": "X"}, headers=header).status_code == 404
    assert client.delete(url(electronics, f"/{chair['id']}"), headers=header).status_code == 404
    assert client.post(url(electronics, f"/{chair['id']}/restore"), headers=header).status_code == 404
    assert client.put(url(furniture, f"/{chair['id']}"), json={"name": "X", "sku": "X"}, headers=auth_header(b["access_token"])).status_code == 404


# ---------- archive / delete / restore ----------

def test_product_with_history_is_archived_not_deleted(client, db):
    a, _, electronics, _ = setup(client)
    product = new_product(client, a, electronics, "Cable", "C1", opening_quantity=5)
    header = auth_header(a["access_token"])
    result = client.delete(url(electronics, f"/{product['id']}"), headers=header)
    assert result.status_code == 200 and result.json()["action"] == "archived"

    assert listing(client, a, electronics) == []  # hidden from the normal list
    assert listing(client, a, electronics, archived="archived") == ["Cable"]
    assert listing(client, a, electronics, archived="all") == ["Cable"]
    assert db.scalar(select(Product).where(Product.id == product["id"])) is not None  # row still exists
    assert len(db.scalars(select(StockTransaction).where(StockTransaction.product_id == product["id"])).all()) == 1  # history kept


def test_product_without_history_is_really_deleted(client, db):
    a, _, electronics, _ = setup(client)
    product = new_product(client, a, electronics, "Typo product", "T1")
    result = client.delete(url(electronics, f"/{product['id']}"), headers=auth_header(a["access_token"]))
    assert result.json()["action"] == "deleted"
    assert db.scalar(select(Product).where(Product.id == product["id"])) is None


def test_restore_brings_an_archived_product_back(client):
    a, _, electronics, _ = setup(client)
    product = new_product(client, a, electronics, "Cable", "C1", opening_quantity=5)
    header = auth_header(a["access_token"])
    client.delete(url(electronics, f"/{product['id']}"), headers=header)
    restored = client.post(url(electronics, f"/{product['id']}/restore"), headers=header)
    assert restored.status_code == 200 and restored.json()["is_archived"] is False
    assert listing(client, a, electronics) == ["Cable"]


def test_archived_products_leave_the_dashboard_totals(client):
    a, _, electronics, _ = setup(client)
    product = new_product(client, a, electronics, "Cable", "C1", opening_quantity=5)
    new_product(client, a, electronics, "Pen", "P1", opening_quantity=7)
    header = auth_header(a["access_token"])
    assert client.get(f"/businesses/{electronics['id']}/dashboard", headers=header).json()["total_stock"] == 12
    client.delete(url(electronics, f"/{product['id']}"), headers=header)
    dashboard = client.get(f"/businesses/{electronics['id']}/dashboard", headers=header).json()
    assert dashboard["total_stock"] == 7 and dashboard["total_products"] == 1
    assert len(dashboard["recent_transactions"]) == 2  # the movement history is still there


def test_staff_can_add_and_edit_but_not_archive_or_restore(client):
    a, b, electronics, _ = setup(client)
    add_staff(client, a, b, electronics)
    staff = auth_header(b["access_token"])
    created = client.post(url(electronics), json={"name": "Cable", "sku": "C1", "opening_quantity": 4}, headers=staff)
    assert created.status_code == 201
    pid = created.json()["id"]
    assert client.put(url(electronics, f"/{pid}"), json={"name": "Cable 2", "sku": "C1"}, headers=staff).status_code == 200
    assert client.delete(url(electronics, f"/{pid}"), headers=staff).status_code == 403
    assert client.post(url(electronics, f"/{pid}/restore"), headers=staff).status_code == 403
    # the opening-stock transaction names the staff member who created the product
    dashboard = client.get(f"/businesses/{electronics['id']}/dashboard", headers=staff).json()
    assert dashboard["recent_transactions"][0]["user_name"] == "User B"


def test_login_required(client):
    a, _, electronics, _ = setup(client)
    assert client.get(url(electronics)).status_code == 401
    assert client.post(url(electronics), json={"name": "x", "sku": "x"}).status_code == 401
