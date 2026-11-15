"""Pydantic models: they describe and validate what goes in and out of the API.

UserOut has no password field, so a password hash can never leak in a response.
"""
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    # bcrypt only uses the first 72 bytes, so we cap the length
    password: str = Field(min_length=8, max_length=72)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- businesses ----------

class BusinessIn(BaseModel):
    """Used for both creating and editing a business."""
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    address: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=40)
    currency: str = Field(default="INR", min_length=1, max_length=8)
    default_min_stock: int = Field(default=5, ge=0, le=1_000_000)

    model_config = {"str_strip_whitespace": True}


class BusinessOut(BaseModel):
    id: int
    name: str
    description: str | None
    address: str | None
    phone: str | None
    currency: str
    default_min_stock: int
    my_role: str  # the logged-in user's role in this business: 'owner' or 'staff'


class MemberOut(BaseModel):
    id: int  # the membership id (not the user id)
    user_id: int
    email: str
    full_name: str
    role: str


class MemberAddIn(BaseModel):
    email: EmailStr


# ---------- dashboard ----------

class RecentTransactionOut(BaseModel):
    id: int
    product_name: str
    type: str  # 'in', 'out' or 'adjust'
    quantity_change: int
    quantity_after: int
    reason: str | None
    user_name: str | None
    created_at: datetime


class DashboardOut(BaseModel):
    currency: str
    total_products: int
    total_stock: int
    inventory_value: float  # quantity x purchase price, summed over active products
    low_stock_count: int
    out_of_stock_count: int
    recent_transactions: list[RecentTransactionOut]


# ---------- categories ----------

class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    model_config = {"str_strip_whitespace": True}


class CategoryOut(BaseModel):
    id: int
    name: str
    product_count: int  # how many products use this category (archived ones included)


# ---------- products ----------

# Prices: zero or more, at most 2 decimal places
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class ProductIn(BaseModel):
    """Fields the user can edit. Stock quantity is NOT here: it only changes through stock movements."""
    name: str = Field(min_length=1, max_length=160)
    sku: str = Field(min_length=1, max_length=60)
    category_id: int | None = None
    supplier_id: int | None = None
    purchase_price: Money = Decimal(0)
    selling_price: Money = Decimal(0)
    min_stock: int | None = Field(default=None, ge=0, le=1_000_000)  # None = use the business default

    model_config = {"str_strip_whitespace": True}


class ProductCreate(ProductIn):
    # Becomes an 'Opening stock' stock-in transaction, so history stays complete
    opening_quantity: int = Field(default=0, ge=0, le=1_000_000)


class ProductOut(BaseModel):
    id: int
    name: str
    sku: str
    category_id: int | None
    category_name: str | None
    supplier_id: int | None
    supplier_name: str | None
    purchase_price: float
    selling_price: float
    quantity: int
    min_stock: int | None
    alert_level: int  # the level actually used: the product's own, or the business default
    stock_status: str  # 'ok', 'low' or 'out'
    is_archived: bool


class ProductRemovedOut(BaseModel):
    action: str  # 'archived' or 'deleted'
    message: str


# ---------- suppliers ----------

class SupplierIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    contact_person: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=255)

    model_config = {"str_strip_whitespace": True}

    @field_validator("contact_person", "email", "phone", "address", mode="before")
    @classmethod
    def blank_means_none(cls, value):
        return None if isinstance(value, str) and not value.strip() else value


class SupplierOut(BaseModel):
    id: int
    name: str
    contact_person: str | None
    email: str | None
    phone: str | None
    address: str | None
    product_count: int  # products (archived included) that use this supplier


# ---------- stock movements ----------

class StockMoveIn(BaseModel):
    """Stock in or stock out: a positive number of units. The URL says which direction."""
    product_id: int
    quantity: int = Field(ge=1, le=1_000_000)
    reason: str | None = Field(default=None, max_length=255)

    model_config = {"str_strip_whitespace": True}

    @field_validator("reason", mode="before")
    @classmethod
    def blank_reason_means_none(cls, value):
        return None if isinstance(value, str) and not value.strip() else value


class StockAdjustIn(BaseModel):
    """A stock count correction: the user says what the real quantity is, and a reason."""
    product_id: int
    new_quantity: int = Field(ge=0, le=1_000_000_000)
    reason: str = Field(min_length=3, max_length=255)

    model_config = {"str_strip_whitespace": True}


class TransactionOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    sku: str
    type: str  # 'in', 'out' or 'adjust'
    quantity_change: int  # +10 / -3
    quantity_after: int
    reason: str | None
    user_name: str | None
    created_at: datetime


# ---------- reports ----------
class RestockItemOut(BaseModel):
    product_id: int
    name: str
    sku: str
    supplier_name: str | None
    quantity: int
    alert_level: int
    suggested_order: int      # how many to buy to get back to twice the alert level
    estimated_cost: float     # suggested_order x purchase price


class CategoryValueOut(BaseModel):
    category: str             # "Uncategorised" when the product has no category
    product_count: int
    units: int
    value: float              # units x purchase price


class DailyMovementOut(BaseModel):
    day: str                  # YYYY-MM-DD in the caller's own time zone
    units_in: int
    units_out: int


class TopProductOut(BaseModel):
    product_id: int
    name: str
    sku: str
    units_out: int


class MovementReportOut(BaseModel):
    units_in: int
    units_out: int
    net_adjustment: int
    transaction_count: int
    sales_value: float        # units out x the product's CURRENT selling price (an estimate)
    daily: list[DailyMovementOut]
    top_products: list[TopProductOut]
