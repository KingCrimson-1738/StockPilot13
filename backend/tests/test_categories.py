from app.models import Product
from tests.conftest import auth_header, register
from tests.test_businesses import create_business


def setup(client):
    a = register(client, email="a@example.com")
    b = register(client, email="b@example.com")
    electronics = create_business(client, a["access_token"], "ABC Electronics")
    furniture = create_business(client, a["access_token"], "ABC Furniture")
    return a, b, electronics, furniture


def url(business, extra=""):
    return f"/businesses/{business['id']}/categories{extra}"


def add_category(client, user, business, name):
    response = client.post(url(business), json={"name": name}, headers=auth_header(user["access_token"]))
    assert response.status_code == 201, response.text
    return response.json()


def test_create_and_list_categories_sorted(client):
    a, _, electronics, _ = setup(client)
    add_category(client, a, electronics, "Phones")
    add_category(client, a, electronics, "accessories")
    names = [c["name"] for c in client.get(url(electronics), headers=auth_header(a["access_token"])).json()]
    assert names == ["accessories", "Phones"]


def test_new_business_starts_with_no_categories(client):
    a, _, electronics, _ = setup(client)
    assert client.get(url(electronics), headers=auth_header(a["access_token"])).json() == []


def test_name_is_trimmed_and_cannot_be_blank(client):
    a, _, electronics, _ = setup(client)
    header = auth_header(a["access_token"])
    assert add_category(client, a, electronics, "  Cables  ")["name"] == "Cables"
    assert client.post(url(electronics), json={"name": "   "}, headers=header).status_code == 422


def test_duplicate_name_rejected_case_insensitive_within_one_business(client):
    a, _, electronics, furniture = setup(client)
    add_category(client, a, electronics, "Snacks")
    response = client.post(url(electronics), json={"name": "snacks"}, headers=auth_header(a["access_token"]))
    assert response.status_code == 409
    add_category(client, a, furniture, "Snacks")  # a different business may reuse the name


def test_rename(client):
    a, _, electronics, _ = setup(client)
    header = auth_header(a["access_token"])
    cat = add_category(client, a, electronics, "Cables")
    other = add_category(client, a, electronics, "Phones")
    assert client.put(url(electronics, f"/{cat['id']}"), json={"name": "Wires"}, headers=header).json()["name"] == "Wires"
    assert client.put(url(electronics, f"/{cat['id']}"), json={"name": "WIRES"}, headers=header).status_code == 200  # own name, new case
    assert client.put(url(electronics, f"/{cat['id']}"), json={"name": "phones"}, headers=header).status_code == 409
    assert other["id"] != cat["id"]


def test_delete_unused_category_but_not_a_used_one(client, db):
    a, _, electronics, _ = setup(client)
    header = auth_header(a["access_token"])
    used = add_category(client, a, electronics, "Used")
    unused = add_category(client, a, electronics, "Unused")
    db.add(Product(business_id=electronics["id"], category_id=used["id"], name="Pen", sku="PEN"))
    db.commit()

    listing = {c["name"]: c["product_count"] for c in client.get(url(electronics), headers=header).json()}
    assert listing == {"Used": 1, "Unused": 0}

    blocked = client.delete(url(electronics, f"/{used['id']}"), headers=header)
    assert blocked.status_code == 409 and "1 product" in blocked.json()["detail"]
    assert client.delete(url(electronics, f"/{unused['id']}"), headers=header).status_code == 204
    assert [c["name"] for c in client.get(url(electronics), headers=header).json()] == ["Used"]


def test_staff_can_add_and_rename_but_not_delete(client):
    a, b, electronics, _ = setup(client)
    client.post(f"/businesses/{electronics['id']}/members", json={"email": "b@example.com"}, headers=auth_header(a["access_token"]))
    staff = auth_header(b["access_token"])
    cat = client.post(url(electronics), json={"name": "Cables"}, headers=staff)
    assert cat.status_code == 201
    assert client.put(url(electronics, f"/{cat.json()['id']}"), json={"name": "Wires"}, headers=staff).status_code == 200
    assert client.delete(url(electronics, f"/{cat.json()['id']}"), headers=staff).status_code == 403


def test_categories_are_isolated_between_businesses_and_users(client):
    a, b, electronics, furniture = setup(client)
    header = auth_header(a["access_token"])
    cat = add_category(client, a, electronics, "Cables")
    # outsider
    assert client.get(url(electronics), headers=auth_header(b["access_token"])).status_code == 404
    assert client.post(url(electronics), json={"name": "X"}, headers=auth_header(b["access_token"])).status_code == 404
    # same owner, other business: the id of Electronics' category is invisible from Furniture's URLs
    assert client.get(url(furniture), headers=header).json() == []
    assert client.put(url(furniture, f"/{cat['id']}"), json={"name": "Hacked"}, headers=header).status_code == 404
    assert client.delete(url(furniture, f"/{cat['id']}"), headers=header).status_code == 404
    assert client.get(url(electronics), headers=header).json()[0]["name"] == "Cables"


def test_login_required(client):
    a, _, electronics, _ = setup(client)
    assert client.get(url(electronics)).status_code == 401
