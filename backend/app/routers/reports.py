"""Reports and CSV exports. Every query starts from ONE business (member.business_id from the verified membership).

Restock rule: a product needs restocking when quantity <= its alert level (its own, or the business default).
The suggested order brings it back to TWICE the alert level (at least 1 unit).
"""
import csv
import io
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_member
from app.models import Business, BusinessMember, Category, Product, StockTransaction, Supplier, User
from app.schemas import (CategoryValueOut, DailyMovementOut, MovementReportOut, RestockItemOut, TopProductOut)

router = APIRouter(prefix="/businesses/{business_id}", tags=["Reports"])


def as_utc(value):
    """A time without a zone is taken as UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def restock_rows(db, business_id):
    business = db.get(Business, business_id)
    level = func.coalesce(Product.min_stock, business.default_min_stock)
    rows = db.execute(
        select(Product, level, Supplier.name)
        .outerjoin(Supplier, Supplier.id == Product.supplier_id)
        .where(Product.business_id == business_id, Product.is_archived.is_(False), Product.quantity <= level)
        .order_by(Product.quantity, Product.name)
    ).all()
    items = []
    for product, alert_level, supplier_name in rows:
        suggested = max(2 * alert_level - product.quantity, 1)
        items.append(RestockItemOut(
            product_id=product.id, name=product.name, sku=product.sku, supplier_name=supplier_name,
            quantity=product.quantity, alert_level=alert_level, suggested_order=suggested,
            estimated_cost=float(suggested * product.purchase_price),
        ))
    return items


@router.get("/reports/low-stock", response_model=list[RestockItemOut])
def low_stock(member: BusinessMember = Depends(get_member), db: Session = Depends(get_db)):
    """Out-of-stock first, then the lowest stock."""
    return restock_rows(db, member.business_id)


@router.get("/reports/inventory-by-category", response_model=list[CategoryValueOut])
def inventory_by_category(member: BusinessMember = Depends(get_member), db: Session = Depends(get_db)):
    name = func.coalesce(Category.name, "Uncategorised")
    rows = db.execute(
        select(name, func.count(Product.id), func.coalesce(func.sum(Product.quantity), 0),
               func.coalesce(func.sum(Product.quantity * Product.purchase_price), 0))
        .select_from(Product).outerjoin(Category, Category.id == Product.category_id)
        .where(Product.business_id == member.business_id, Product.is_archived.is_(False))
        .group_by(name).order_by(func.sum(Product.quantity * Product.purchase_price).desc(), name)
    ).all()
    return [CategoryValueOut(category=n, product_count=c, units=int(u), value=float(v)) for n, c, u, v in rows]


@router.get("/reports/movements", response_model=MovementReportOut)
def movement_report(
    from_time: datetime | None = None, to_time: datetime | None = None,
    tz_offset_minutes: int = Query(0, ge=-840, le=840, description="the caller's UTC offset, so days are THEIR days"),
    member: BusinessMember = Depends(get_member), db: Session = Depends(get_db),
):
    """Stock added / removed in a period, per day, plus the five best-selling products."""
    t = StockTransaction
    conditions = [t.business_id == member.business_id]
    if from_time is not None:
        conditions.append(t.created_at >= as_utc(from_time))
    if to_time is not None:
        conditions.append(t.created_at < as_utc(to_time))

    totals = db.execute(
        select(
            func.coalesce(func.sum(t.quantity_change).filter(t.type == "in"), 0),
            func.coalesce(-func.sum(t.quantity_change).filter(t.type == "out"), 0),
            func.coalesce(func.sum(t.quantity_change).filter(t.type == "adjust"), 0),
            func.count(t.id),
            func.coalesce(-func.sum(t.quantity_change * Product.selling_price).filter(t.type == "out"), 0),
        ).join(Product, Product.id == t.product_id).where(*conditions)
    ).one()

    local_day = cast(func.timezone("UTC", t.created_at) + timedelta(minutes=tz_offset_minutes), Date)
    daily_rows = db.execute(
        select(local_day, func.coalesce(func.sum(t.quantity_change).filter(t.type == "in"), 0),
               func.coalesce(-func.sum(t.quantity_change).filter(t.type == "out"), 0))
        .where(*conditions, t.type.in_(("in", "out"))).group_by(local_day).order_by(local_day)
    ).all()

    top_rows = db.execute(
        select(Product.id, Product.name, Product.sku, -func.sum(t.quantity_change))
        .join(Product, Product.id == t.product_id).where(*conditions, t.type == "out")
        .group_by(Product.id).order_by((-func.sum(t.quantity_change)).desc(), Product.name).limit(5)
    ).all()

    return MovementReportOut(
        units_in=int(totals[0]), units_out=int(totals[1]), net_adjustment=int(totals[2]),
        transaction_count=totals[3], sales_value=float(totals[4]),
        daily=[DailyMovementOut(day=d.isoformat(), units_in=int(i), units_out=int(o)) for d, i, o in daily_rows],
        top_products=[TopProductOut(product_id=i, name=n, sku=s, units_out=int(u)) for i, n, s, u in top_rows],
    )


# ---------- CSV exports ----------

def safe_cell(value):
    """Stops 'CSV injection': a text starting with = + - @ would be run as a formula by Excel."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return "" if value is None else value


def csv_response(filename, header, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in rows:
        writer.writerow([safe_cell(v) for v in row])
    # utf-8 with a BOM so Excel shows accented characters correctly
    return Response(
        content="﻿" + buffer.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/exports/products.csv")
def export_products(member: BusinessMember = Depends(get_member), db: Session = Depends(get_db)):
    business = db.get(Business, member.business_id)
    rows = db.execute(
        select(Product, Category.name, Supplier.name)
        .outerjoin(Category, Category.id == Product.category_id)
        .outerjoin(Supplier, Supplier.id == Product.supplier_id)
        .where(Product.business_id == member.business_id).order_by(Product.name)
    ).all()
    data = []
    for p, category, supplier in rows:
        level = p.min_stock if p.min_stock is not None else business.default_min_stock
        data.append([p.sku, p.name, category, supplier, f"{p.purchase_price:.2f}", f"{p.selling_price:.2f}", p.quantity,
                     level, f"{p.quantity * p.purchase_price:.2f}", "archived" if p.is_archived else "active"])
    return csv_response(f"products-{date.today().isoformat()}.csv",
                        ["SKU", "Name", "Category", "Supplier", "Purchase price", "Selling price", "Quantity",
                         "Alert level", "Stock value", "Status"], data)


@router.get("/exports/transactions.csv")
def export_transactions(
    from_time: datetime | None = None, to_time: datetime | None = None,
    tz_offset_minutes: int = Query(0, ge=-840, le=840),
    member: BusinessMember = Depends(get_member), db: Session = Depends(get_db),
):
    query = (
        select(StockTransaction, Product.name, Product.sku, User.full_name)
        .join(Product, Product.id == StockTransaction.product_id)
        .outerjoin(User, User.id == StockTransaction.user_id)
        .where(StockTransaction.business_id == member.business_id)
        .order_by(StockTransaction.created_at, StockTransaction.id)
    )
    if from_time is not None:
        query = query.where(StockTransaction.created_at >= as_utc(from_time))
    if to_time is not None:
        query = query.where(StockTransaction.created_at < as_utc(to_time))
    zone = timezone(timedelta(minutes=tz_offset_minutes))
    data = [[t.created_at.astimezone(zone).strftime("%Y-%m-%d %H:%M"), sku, name, t.type, t.quantity_change,
             t.quantity_after, t.reason, who] for t, name, sku, who in db.execute(query).all()]
    return csv_response(f"stock-history-{date.today().isoformat()}.csv",
                        ["Date and time", "SKU", "Product", "Type", "Change", "Quantity after", "Reason", "Done by"], data)


@router.get("/exports/low-stock.csv")
def export_low_stock(member: BusinessMember = Depends(get_member), db: Session = Depends(get_db)):
    data = [[i.sku, i.name, i.supplier_name, i.quantity, i.alert_level, i.suggested_order, f"{i.estimated_cost:.2f}"]
            for i in restock_rows(db, member.business_id)]
    return csv_response(f"restock-list-{date.today().isoformat()}.csv",
                        ["SKU", "Product", "Supplier", "In stock", "Alert level", "Suggested order", "Estimated cost"], data)
