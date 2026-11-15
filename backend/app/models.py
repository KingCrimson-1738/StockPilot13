"""Database tables.

Relationships in one picture:

    users --< business_members >-- businesses
    businesses --< categories, suppliers, products, stock_transactions
    products >-- categories, suppliers (optional)
    products --< stock_transactions

Every business table carries business_id. That column is what keeps one
business's data separate from another's.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric,
    String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(40))
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    # Products with quantity <= this are "low stock" unless the product has its own limit
    default_min_stock: Mapped[int] = mapped_column(Integer, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class BusinessMember(Base):
    """Links a user to a business with a role ('owner' or 'staff')."""
    __tablename__ = "business_members"
    __table_args__ = (
        UniqueConstraint("business_id", "user_id", name="uq_member_business_user"),
        CheckConstraint("role IN ('owner', 'staff')", name="ck_member_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    user: Mapped[User] = relationship()


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("business_id", "name", name="uq_category_business_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("business_id", "name", name="uq_supplier_business_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    contact_person: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("business_id", "sku", name="uq_product_business_sku"),
        # The database itself refuses negative stock, as a second safety net
        CheckConstraint("quantity >= 0", name="ck_product_quantity_not_negative"),
        CheckConstraint("purchase_price >= 0 AND selling_price >= 0", name="ck_product_prices"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), index=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    sku: Mapped[str] = mapped_column(String(60))
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    min_stock: Mapped[int | None] = mapped_column(Integer)  # None = use business default
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class StockTransaction(Base):
    """One row for every stock movement. Never edited or deleted."""
    __tablename__ = "stock_transactions"
    __table_args__ = (
        CheckConstraint("type IN ('in', 'out', 'adjust')", name="ck_transaction_type"),
        Index("ix_transactions_business_created", "business_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(10))
    quantity_change: Mapped[int] = mapped_column(Integer)  # +10 for stock-in, -3 for stock-out
    quantity_after: Mapped[int] = mapped_column(Integer)   # stock level after this movement
    reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    product: Mapped[Product] = relationship()
    user: Mapped[User | None] = relationship()
