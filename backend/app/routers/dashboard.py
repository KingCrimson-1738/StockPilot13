"""Dashboard numbers. Everything is calculated from the real rows of ONE business."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_member
from app.models import Business, BusinessMember, Product, StockTransaction, User
from app.schemas import DashboardOut, RecentTransactionOut

router = APIRouter(prefix="/businesses", tags=["Dashboard"])


@router.get("/{business_id}/dashboard", response_model=DashboardOut)
def get_dashboard(member: BusinessMember = Depends(get_member), db: Session = Depends(get_db)):
    business = db.get(Business, member.business_id)

    # A product's own limit wins; otherwise the business default is used
    limit = func.coalesce(Product.min_stock, business.default_min_stock)

    totals = db.execute(
        select(
            func.count(Product.id),
            func.coalesce(func.sum(Product.quantity), 0),
            func.coalesce(func.sum(Product.quantity * Product.purchase_price), 0),
            func.count(Product.id).filter(Product.quantity > 0, Product.quantity <= limit),
            func.count(Product.id).filter(Product.quantity == 0),
        ).where(Product.business_id == business.id, Product.is_archived.is_(False))
    ).one()

    recent_rows = db.execute(
        select(StockTransaction, Product.name, User.full_name)
        .join(Product, Product.id == StockTransaction.product_id)
        .outerjoin(User, User.id == StockTransaction.user_id)
        .where(StockTransaction.business_id == business.id)
        .order_by(StockTransaction.created_at.desc(), StockTransaction.id.desc())
        .limit(10)
    ).all()

    recent = [
        RecentTransactionOut(
            id=t.id,
            product_name=product_name,
            type=t.type,
            quantity_change=t.quantity_change,
            quantity_after=t.quantity_after,
            reason=t.reason,
            user_name=user_name,
            created_at=t.created_at,
        )
        for t, product_name, user_name in recent_rows
    ]

    return DashboardOut(
        currency=business.currency,
        total_products=totals[0],
        total_stock=int(totals[1]),
        inventory_value=float(totals[2]),
        low_stock_count=totals[3],
        out_of_stock_count=totals[4],
        recent_transactions=recent,
    )
