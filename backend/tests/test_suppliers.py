from tests.conftest import auth_header, register
from tests.test_businesses import create_business


def setup(client):
    a = register(client, email="a@example.com", name="User A")
    b = register(client, email="b@example.com", name="User B")
    electronics = create_business(client, a["access_token"], "ABC Electronics")
    furniture = create_business(client, a["access_token"], "ABC Furniture")
    return a, b, electronics, furniture


def url(business, extra=""):
    return f"/businesses/{business['id']}/suppliers{extra}"


def add_supplier(client, user, business, name="Volt Ltd", expect=201, **extra):
    response = client.post(url(business), json={"name": name, **extra}, headers=auth_header(user["access_token"]))
    assert response.status_code == expect, response.text
    return response.json()


def test_create_list_and_new_business_starts_empty(client):
    a, _, electronics, _ = setup(client)
    header = auth_header(a["access_token"])
    assert client.get(url(electronics), headers=header).json() == []
    supplier = add_supplier(client, a, electronics, "Volt Ltd", contact_person="Ravi", email="ravi@volt.com", phone="999", address="Chennai")
    assert (supplier["contact_person"], supplier["email"], supplier["product_count"]) == ("Ravi", "ravi@volt.com", 0)
    add_supplier(client, a, electronics, "acme")
    assert [s["name"] for s in client.get(url(electronics), headers=header).json()] == ["acme", "Volt Ltd"]


def test_blank_optional_fields_become_null_and_email_is_validated(client):
    a, _, electronics, _ = setup(client)
    supplier = add_supplier(client, a, electronics, "Volt", email="", phone="  ", contact_person="")
    assert supplier["email"] is None and supplier["phone"] is None and supplier["contact_person"] is None
    add_supplier(client, a, electronics, "Bad", email="not-an-email", expect=422)
    add_supplier(client, a, electronics, "   ", expect=422)


def test_duplicate_name_rejected_per_business_case_insensitive(client):
    a, _, electronics, furniture = setup(client)
    add_supplier(client, a, electronics, "Volt Ltd")
    add_supplier(client, a, electronics, "VOLT LTD", expect=409)
    add_supplier(client, a, furniture, "Volt Ltd")  # a different business may reuse the name


def test_update(client):
    a, _, electronics, _ = setup(client)
    header = auth_header(a["access_token"])
    one = add_supplier(client, a, electronics, "One")
    add_supplier(client, a, electronics, "Two")
    updated = client.put(url(electronics, f"/{one['id']}"), json={"name": "One Co", "phone": "123"}, headers=header)
    assert updated.status_code == 200 and updated.json()["phone"] == "123"
    assert client.put(url(electronics, f"/{one['id']}"), json={"name": "One Co"}, headers=header).status_code == 200  # own name
    assert client.put(url(electronics, f"/{one['id']}"), json={"name": "two"}, headers=header).status_code == 409


def test_delete_unused_but_not_used_supplier(client):
    a, _, electronics, _ = setup(client)
    header = auth_header(a["access_token"])
    used, unused = add_supplier(client, a, electronics, "Used"), add_supplier(client, a, electronics, "Unused")
    client.post(f"/businesses/{electronics['id']}/products", json={"name": "Cable", "sku": "C1", "supplier_id": used["id"]}, headers=header)

    assert {s["name"]: s["product_count"] for s in client.get(url(electronics), headers=header).json()} == {"Used": 1, "Unused": 0}
    blocked = client.delete(url(electronics, f"/{used['id']}"), headers=header)
    assert blocked.status_code == 409 and "1 product" in blocked.json()["detail"]
    assert client.delete(url(electronics, f"/{unused['id']}"), headers=header).status_code == 204


def test_products_can_be_filtered_by_supplier(client):
    a, _, electronics, _ = setup(client)
    header = auth_header(a["access_token"])
    volt, acme = add_supplier(client, a, electronics, "Volt"), add_supplier(client, a, electronics, "Acme")
    base = f"/businesses/{electronics['id']}/products"
    client.post(base, json={"name": "Cable", "sku": "C1", "supplier_id": volt["id"]}, headers=header)
    client.post(base, json={"name": "Charger", "sku": "C2", "supplier_id": volt["id"]}, headers=header)
    client.post(base, json={"name": "Pen", "sku": "P1", "supplier_id": acme["id"]}, headers=header)
    client.post(base, json={"name": "Loose", "sku": "L1"}, headers=header)
    names = lambda sid: [p["name"] for p in client.get(base, params={"supplier_id": sid}, headers=header).json()]
    assert names(volt["id"]) == ["Cable", "Charger"] and names(acme["id"]) == ["Pen"]
    assert client.get(base, params={"supplier_id": volt["id"]}, headers=header).json()[0]["supplier_name"] == "Volt"


def test_staff_can_add_and_edit_but_not_delete(client):
    a, b, electronics, _ = setup(client)
    client.post(f"/businesses/{electronics['id']}/members", json={"email": "b@example.com"}, headers=auth_header(a["access_token"]))
    staff = auth_header(b["access_token"])
    created = client.post(url(electronics), json={"name": "Volt"}, headers=staff)
    assert created.status_code == 201
    sid = created.json()["id"]
    assert client.put(url(electronics, f"/{sid}"), json={"name": "Volt 2"}, headers=staff).status_code == 200
    assert client.delete(url(electronics, f"/{sid}"), headers=staff).status_code == 403


def test_suppliers_are_isolated(client):
    a, b, electronics, furniture = setup(client)
    header = auth_header(a["access_token"])
    supplier = add_supplier(client, a, electronics, "Volt")
    assert client.get(url(electronics), headers=auth_header(b["access_token"])).status_code == 404
    assert client.get(url(furniture), headers=header).json() == []
    assert client.put(url(furniture, f"/{supplier['id']}"), json={"name": "X"}, headers=header).status_code == 404
    assert client.delete(url(furniture, f"/{supplier['id']}"), headers=header).status_code == 404
    assert client.get(url(electronics)).status_code == 401
