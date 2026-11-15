"""Tests for the database safety nets (constraints that protect data even if code has a bug)."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Category, Product


# ---------- database constraints ----------

def test_database_rejects_negative_stock(db):
    from app.models import Business
    business = Business(name="Shop")
    db.add(business)
    db.flush()
    db.add(Product(business_id=business.id, name="Pen", sku="PEN-1", quantity=-1))
    with pytest.raises(IntegrityError):
        db.commit()


def test_same_category_name_allowed_in_different_businesses_only(db):
    from app.models import Business
    shop1, shop2 = Business(name="Shop 1"), Business(name="Shop 2")
    db.add_all([shop1, shop2])
    db.flush()

    db.add_all([Category(business_id=shop1.id, name="Snacks"), Category(business_id=shop2.id, name="Snacks")])
    db.commit()  # fine: different businesses

    db.add(Category(business_id=shop1.id, name="Snacks"))
    with pytest.raises(IntegrityError):
        db.commit()  # duplicate inside one business


def test_sku_must_be_unique_per_business(db):
    from app.models import Business
    shop1, shop2 = Business(name="Shop 1"), Business(name="Shop 2")
    db.add_all([shop1, shop2])
    db.flush()
    db.add_all([
        Product(business_id=shop1.id, name="Pen", sku="PEN-1"),
        Product(business_id=shop2.id, name="Pen", sku="PEN-1"),
    ])
    db.commit()

    db.add(Product(business_id=shop1.id, name="Another pen", sku="PEN-1"))
    with pytest.raises(IntegrityError):
        db.commit()
