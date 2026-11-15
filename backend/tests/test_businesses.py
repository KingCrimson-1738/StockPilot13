"""Multi-business tests through the real endpoints.

Scenario used throughout:
  User A owns 'ABC Electronics' and 'ABC Furniture'. User B owns 'XYZ Supermarket'.
"""
from tests.conftest import auth_header, register

NEW_BUSINESS = {"name": "ABC Electronics", "currency": "INR", "default_min_stock": 5}


def create_business(client, token, name="ABC Electronics", **extra):
    response = client.post("/businesses", json={**NEW_BUSINESS, "name": name, **extra}, headers=auth_header(token))
    assert response.status_code == 201, response.text
    return response.json()


def setup_two_users(client):
    a = register(client, email="a@example.com", name="User A")
    b = register(client, email="b@example.com", name="User B")
    electronics = create_business(client, a["access_token"], "ABC Electronics")
    furniture = create_business(client, a["access_token"], "ABC Furniture")
    supermarket = create_business(client, b["access_token"], "XYZ Supermarket")
    return a, b, electronics, furniture, supermarket


# ---------- create and list ----------

def test_create_business_makes_creator_the_owner(client):
    token = register(client)["access_token"]
    business = create_business(client, token, address="Chennai", description="Gadgets")
    assert business["my_role"] == "owner"
    assert business["address"] == "Chennai"


def test_create_requires_login(client):
    assert client.post("/businesses", json=NEW_BUSINESS).status_code == 401
    assert client.get("/businesses").status_code == 401


def test_create_validation(client):
    token = register(client)["access_token"]
    header = auth_header(token)
    assert client.post("/businesses", json={"name": ""}, headers=header).status_code == 422
    assert client.post("/businesses", json={"name": "   "}, headers=header).status_code == 422
    assert client.post("/businesses", json={"name": "Shop", "default_min_stock": -1}, headers=header).status_code == 422


def test_one_account_can_have_multiple_businesses(client):
    a, _, _, _, _ = setup_two_users(client)
    names = [b["name"] for b in client.get("/businesses", headers=auth_header(a["access_token"])).json()]
    assert names == ["ABC Electronics", "ABC Furniture"]


def test_list_shows_only_my_businesses(client):
    a, b, _, _, _ = setup_two_users(client)
    b_names = [x["name"] for x in client.get("/businesses", headers=auth_header(b["access_token"])).json()]
    assert b_names == ["XYZ Supermarket"]


def test_new_user_starts_with_no_businesses(client):
    token = register(client)["access_token"]
    assert client.get("/businesses", headers=auth_header(token)).json() == []


# ---------- isolation ----------

def test_user_cannot_read_or_edit_another_users_business(client):
    a, b, electronics, _, supermarket = setup_two_users(client)
    a_header, b_header = auth_header(a["access_token"]), auth_header(b["access_token"])

    assert client.get(f"/businesses/{electronics['id']}", headers=b_header).status_code == 404
    assert client.get(f"/businesses/{supermarket['id']}", headers=a_header).status_code == 404
    assert client.put(f"/businesses/{electronics['id']}", json={"name": "Hacked"}, headers=b_header).status_code == 404
    assert client.get(f"/businesses/{electronics['id']}/members", headers=b_header).status_code == 404

    # and nothing changed
    assert client.get(f"/businesses/{electronics['id']}", headers=a_header).json()["name"] == "ABC Electronics"


def test_outsider_cannot_tell_real_business_from_missing_one(client):
    _, b, electronics, _, _ = setup_two_users(client)
    header = auth_header(b["access_token"])
    real = client.get(f"/businesses/{electronics['id']}", headers=header)
    missing = client.get("/businesses/999999", headers=header)
    assert real.status_code == missing.status_code == 404
    assert real.json() == missing.json()


def test_get_business_requires_login(client):
    a, _, electronics, _, _ = setup_two_users(client)
    assert client.get(f"/businesses/{electronics['id']}").status_code == 401


# ---------- edit ----------

def test_owner_can_edit_business_and_change_persists(client):
    a, _, electronics, _, _ = setup_two_users(client)
    header = auth_header(a["access_token"])
    update = {"name": "ABC Electronics Pvt", "currency": "USD", "default_min_stock": 10, "phone": "12345"}
    response = client.put(f"/businesses/{electronics['id']}", json=update, headers=header)
    assert response.status_code == 200
    saved = client.get(f"/businesses/{electronics['id']}", headers=header).json()
    assert saved["name"] == "ABC Electronics Pvt"
    assert saved["currency"] == "USD"
    assert saved["default_min_stock"] == 10
    assert saved["phone"] == "12345"


def test_editing_one_business_does_not_change_the_other(client):
    a, _, electronics, furniture, _ = setup_two_users(client)
    header = auth_header(a["access_token"])
    client.put(f"/businesses/{electronics['id']}", json={"name": "Renamed"}, headers=header)
    assert client.get(f"/businesses/{furniture['id']}", headers=header).json()["name"] == "ABC Furniture"


# ---------- members and roles ----------

def test_members_list_has_no_password_data(client):
    a, _, electronics, _, _ = setup_two_users(client)
    response = client.get(f"/businesses/{electronics['id']}/members", headers=auth_header(a["access_token"]))
    members = response.json()
    assert len(members) == 1
    assert members[0]["role"] == "owner"
    assert members[0]["email"] == "a@example.com"
    assert "hash" not in str(members).lower()


def test_owner_adds_staff_and_staff_gets_limited_access(client):
    a, b, electronics, _, _ = setup_two_users(client)
    a_header, b_header = auth_header(a["access_token"]), auth_header(b["access_token"])
    base = f"/businesses/{electronics['id']}"

    added = client.post(f"{base}/members", json={"email": "B@example.com"}, headers=a_header)
    assert added.status_code == 201
    assert added.json()["role"] == "staff"

    # B now sees ABC Electronics in their list, with the staff role
    mine = {x["name"]: x["my_role"] for x in client.get("/businesses", headers=b_header).json()}
    assert mine == {"XYZ Supermarket": "owner", "ABC Electronics": "staff"}

    # staff can view, but cannot edit settings or manage members
    assert client.get(base, headers=b_header).status_code == 200
    assert client.get(f"{base}/members", headers=b_header).status_code == 200
    assert client.put(base, json={"name": "Mine now"}, headers=b_header).status_code == 403
    assert client.post(f"{base}/members", json={"email": "a@example.com"}, headers=b_header).status_code == 403

    # access to B's own business, and to A's other business, is unaffected
    assert client.get("/businesses", headers=a_header).json()[0]["name"] == "ABC Electronics"


def test_staff_access_is_per_business(client):
    a, b, electronics, furniture, _ = setup_two_users(client)
    client.post(f"/businesses/{electronics['id']}/members", json={"email": "b@example.com"},
                headers=auth_header(a["access_token"]))
    # B was added to Electronics only: Furniture is still off limits
    assert client.get(f"/businesses/{furniture['id']}", headers=auth_header(b["access_token"])).status_code == 404


def test_add_member_errors(client):
    a, _, electronics, _, _ = setup_two_users(client)
    header = auth_header(a["access_token"])
    url = f"/businesses/{electronics['id']}/members"
    assert client.post(url, json={"email": "nobody@example.com"}, headers=header).status_code == 404
    assert client.post(url, json={"email": "a@example.com"}, headers=header).status_code == 409  # already the owner
    assert client.post(url, json={"email": "not-an-email"}, headers=header).status_code == 422
    client.post(url, json={"email": "b@example.com"}, headers=header)
    assert client.post(url, json={"email": "b@example.com"}, headers=header).status_code == 409  # twice


def test_owner_removes_staff_and_access_is_lost(client):
    a, b, electronics, _, _ = setup_two_users(client)
    a_header, b_header = auth_header(a["access_token"]), auth_header(b["access_token"])
    base = f"/businesses/{electronics['id']}"
    member_id = client.post(f"{base}/members", json={"email": "b@example.com"}, headers=a_header).json()["id"]

    assert client.delete(f"{base}/members/{member_id}", headers=b_header).status_code == 403  # staff can't remove
    assert client.delete(f"{base}/members/{member_id}", headers=a_header).status_code == 204
    assert client.get(base, headers=b_header).status_code == 404  # B is locked out again


def test_owner_cannot_be_removed(client):
    a, _, electronics, _, _ = setup_two_users(client)
    header = auth_header(a["access_token"])
    base = f"/businesses/{electronics['id']}"
    owner_member_id = client.get(f"{base}/members", headers=header).json()[0]["id"]
    assert client.delete(f"{base}/members/{owner_member_id}", headers=header).status_code == 400


def test_owner_cannot_remove_members_of_another_business(client):
    """A owns Electronics and Furniture. A staff member of Furniture must not be removable via the Electronics URL."""
    a, b, electronics, furniture, _ = setup_two_users(client)
    header = auth_header(a["access_token"])
    furniture_member_id = client.post(
        f"/businesses/{furniture['id']}/members", json={"email": "b@example.com"}, headers=header
    ).json()["id"]

    wrong_url = f"/businesses/{electronics['id']}/members/{furniture_member_id}"
    assert client.delete(wrong_url, headers=header).status_code == 404
    # B is still a member of Furniture
    assert client.get(f"/businesses/{furniture['id']}", headers=auth_header(b["access_token"])).status_code == 200
