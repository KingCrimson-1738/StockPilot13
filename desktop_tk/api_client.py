"""How the Tkinter app talks to the backend.

Every screen calls a method here (e.g. api.login(...)). Each method sends an HTTPS request
with `requests`, sends the JWT in the Authorization header, and returns the decoded JSON.
If anything goes wrong it raises ApiError with a message that is safe to show to the user.
"""
import requests

import config


class ApiError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.message = message
        self.status = status  # HTTP status code, or None if the server was never reached


def _error_message(response):
    if response.status_code >= 500:
        return "Something went wrong on the server. Please try again in a moment."
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:  # validation errors (422) come as a list
        first = detail[0]
        field = str(first.get("loc", ["input"])[-1]).replace("_", " ")
        return f"Please check the {field}: {first.get('msg', 'invalid value')}"
    return f"The request failed (error {response.status_code})."


class ApiClient:
    def __init__(self):
        self.token = None  # set after login/register, sent with every request

    def request(self, method, path, json=None, params=None):
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            response = requests.request(
                method, config.API_URL + path, json=json, params=params, headers=headers,
                timeout=config.REQUEST_TIMEOUT_SECONDS,
            )
        except requests.exceptions.Timeout:
            raise ApiError("The server took too long to respond. Please try again.")
        except requests.exceptions.ConnectionError:
            raise ApiError("Cannot reach the server. Check your internet connection and the server address.")
        except requests.exceptions.RequestException:
            raise ApiError("Could not complete the request. Please try again.")

        if response.status_code == 204:
            return None
        if response.ok:
            return response.json()
        raise ApiError(_error_message(response), response.status_code)

    def download(self, path, params=None):
        """Fetches a file (the CSV exports). Returns (suggested file name, bytes)."""
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            response = requests.get(config.API_URL + path, params=params, headers=headers,
                                    timeout=config.REQUEST_TIMEOUT_SECONDS)
        except requests.exceptions.Timeout:
            raise ApiError("The server took too long to respond. Please try again.")
        except requests.exceptions.RequestException:
            raise ApiError("Cannot reach the server. Check your internet connection and the server address.")
        if not response.ok:
            raise ApiError(_error_message(response), response.status_code)
        disposition = response.headers.get("Content-Disposition", "")
        name = disposition.split('filename="')[1].rstrip('"') if 'filename="' in disposition else "export.csv"
        return name, response.content

    # ----- authentication -----
    def register(self, email, full_name, password):
        data = self.request("POST", "/auth/register", {"email": email, "full_name": full_name, "password": password})
        self.token = data["access_token"]
        return data["user"]

    def login(self, email, password):
        data = self.request("POST", "/auth/login", {"email": email, "password": password})
        self.token = data["access_token"]
        return data["user"]

    # ----- businesses -----
    def list_businesses(self):
        return self.request("GET", "/businesses")

    def create_business(self, values):
        return self.request("POST", "/businesses", values)

    def get_business(self, business_id):
        return self.request("GET", f"/businesses/{business_id}")

    def update_business(self, business_id, values):
        return self.request("PUT", f"/businesses/{business_id}", values)

    def list_members(self, business_id):
        return self.request("GET", f"/businesses/{business_id}/members")

    def add_member(self, business_id, email):
        return self.request("POST", f"/businesses/{business_id}/members", {"email": email})

    def remove_member(self, business_id, member_id):
        return self.request("DELETE", f"/businesses/{business_id}/members/{member_id}")

    # ----- dashboard -----
    def get_dashboard(self, business_id):
        return self.request("GET", f"/businesses/{business_id}/dashboard")

    # ----- categories -----
    def list_categories(self, business_id):
        return self.request("GET", f"/businesses/{business_id}/categories")

    def create_category(self, business_id, name):
        return self.request("POST", f"/businesses/{business_id}/categories", {"name": name})

    def rename_category(self, business_id, category_id, name):
        return self.request("PUT", f"/businesses/{business_id}/categories/{category_id}", {"name": name})

    def delete_category(self, business_id, category_id):
        return self.request("DELETE", f"/businesses/{business_id}/categories/{category_id}")

    # ----- products -----
    def list_products(self, business_id, search="", category_id=None, stock="all", archived="active", supplier_id=None):
        params = {"search": search or None, "category_id": category_id, "supplier_id": supplier_id,
                  "stock": stock, "archived": archived}
        return self.request("GET", f"/businesses/{business_id}/products", params=params)  # None values are not sent

    def create_product(self, business_id, values):
        return self.request("POST", f"/businesses/{business_id}/products", values)

    def update_product(self, business_id, product_id, values):
        return self.request("PUT", f"/businesses/{business_id}/products/{product_id}", values)

    def remove_product(self, business_id, product_id):
        """Returns {"action": "archived" | "deleted", "message": ...}"""
        return self.request("DELETE", f"/businesses/{business_id}/products/{product_id}")

    def restore_product(self, business_id, product_id):
        return self.request("POST", f"/businesses/{business_id}/products/{product_id}/restore")

    # ----- suppliers -----
    def list_suppliers(self, business_id):
        return self.request("GET", f"/businesses/{business_id}/suppliers")

    def create_supplier(self, business_id, values):
        return self.request("POST", f"/businesses/{business_id}/suppliers", values)

    def update_supplier(self, business_id, supplier_id, values):
        return self.request("PUT", f"/businesses/{business_id}/suppliers/{supplier_id}", values)

    def delete_supplier(self, business_id, supplier_id):
        return self.request("DELETE", f"/businesses/{business_id}/suppliers/{supplier_id}")

    # ----- stock movements -----
    def stock_in(self, business_id, product_id, quantity, reason=None):
        body = {"product_id": product_id, "quantity": quantity, "reason": reason}
        return self.request("POST", f"/businesses/{business_id}/stock/in", body)

    def stock_out(self, business_id, product_id, quantity, reason=None):
        body = {"product_id": product_id, "quantity": quantity, "reason": reason}
        return self.request("POST", f"/businesses/{business_id}/stock/out", body)

    def stock_adjust(self, business_id, product_id, new_quantity, reason):
        body = {"product_id": product_id, "new_quantity": new_quantity, "reason": reason}
        return self.request("POST", f"/businesses/{business_id}/stock/adjust", body)

    def list_transactions(self, business_id, kind=None, product_id=None, from_time=None, to_time=None, limit=200):
        params = {"type": kind, "product_id": product_id, "from_time": from_time, "to_time": to_time, "limit": limit}
        return self.request("GET", f"/businesses/{business_id}/transactions", params=params)

    # ----- reports -----
    def low_stock_report(self, business_id):
        return self.request("GET", f"/businesses/{business_id}/reports/low-stock")

    def category_report(self, business_id):
        return self.request("GET", f"/businesses/{business_id}/reports/inventory-by-category")

    def movement_report(self, business_id, from_time=None, to_time=None, tz_offset_minutes=0):
        params = {"from_time": from_time, "to_time": to_time, "tz_offset_minutes": tz_offset_minutes}
        return self.request("GET", f"/businesses/{business_id}/reports/movements", params=params)
