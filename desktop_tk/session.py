"""Who is logged in and which business is open. One Session object is shared by every screen."""
from api_client import ApiClient


class Session:
    def __init__(self):
        self.api = ApiClient()
        self.user = None          # {"id", "email", "full_name"}
        self.businesses = []      # all businesses of this user (each has "my_role")
        self.business = None      # the business currently open

    @property
    def is_owner(self):
        return self.business is not None and self.business["my_role"] == "owner"

    def log_out(self):
        self.api.token = None
        self.user = None
        self.businesses = []
        self.business = None
