"""Stock movements (in / out / adjust) and the transaction history.

The rules, in the order the code applies them:
  1. LOCK the product row (SELECT ... FOR UPDATE). If two people change the same product at the
     same moment, the second waits until the first has finished, so both see the true quantity.
  2. Check the rules: the product belongs to this business, is not archived, and stock stays >= 0.
  3. Update products.quantity AND insert a stock_transactions row.
  4. COMMIT once. Both changes are saved together, or (on any error) neither is.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_member, get_owner_member
from app.models import BusinessMember, Product, StockTransaction, User
from app.schemas import StockAdjustIn, StockMoveIn, TransactionOut

router = APIRouter(prefix="/businesses/{business_id}", tags=["Stock"])

MAX_STOCK = 1_000_000_000


def lock_active_product(db, business_id, product_id):
    """Fetch the product (this business only) and lock its row until the transaction ends."""
    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.business_id == business_id).with_for_update()
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.is_archived:
        raise HTTPException(status_code=400, detail="This product is archived. Restore it before changing its stock.")
    return product


def record_movement(db, member, product, kind, change, reason):
    """Applies `change` (+ or -) to the product and records it. Caller must hold the row lock."""
    new_quantity = product.quantity + change
    if new_quantity < 0:
        raise HTTPException(
            status_code=409,
            detail=f"Not enough stock. Available: {product.quantity}, requested: {-change}.",
        )
    if new_quantity > MAX_STOCK:
        raise HTTPException(status_code=400, detail="That would make the stock quantity unrealistically large.")

    product.quantity = new_quantity
    transaction = StockTransaction(
        business_id=member.business_id, product_id=product.id, user_id=member.user_id,
        type=kind, quantity_change=change, quantity_after=new_quantity, reason=reason,
    )
    db.add(transaction)
    try:
        db.commit()  # quantity + transaction saved together
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="The stock change could not be saved. Please try again.")
    return transaction_out(transaction, product.name, product.sku, member.user.full_name)


def transaction_out(t, product_name, sku, user_name):
    return TransactionOut(
        id=t.id, product_id=t.product_id, product_name=product_name, sku=sku, type=t.type,
        quantity_change=t.quantity_change, quantity_after=t.quantity_after, reason=t.reason,
        user_name=user_name, created_at=t.created_at,
    )


@router.post("/stock/in", response_model=TransactionOut, status_code=201)
def stock_in(data: StockMoveIn, member: BusinessMember = Depends(get_member), db: Session = Depends(get_db)):
    product = lock_active_product(db, member.business_id, data.product_id)
    return record_movement(db, member, product, "in", data.quantity, data.reason)


@router.post("/stock/out", response_model=TransactionOut, status_code=201)
def stock_out(data: StockMoveIn, member: BusinessMember = Depends(get_member), db: Session = Depends(get_db)):
    product = lock_active_product(db, member.business_id, data.product_id)
    return record_movement(db, member, product, "out", -data.quantity, data.reason)


@router.post("/stock/adjust", response_model=TransactionOut, status_code=201)
def stock_adjust(data: StockAdjustIn, member: BusinessMember = Depends(get_owner_member), db: Session = Depends(get_db)):
    """Owner-only stock count correction: 'the shelf really holds N'. Recorded as the difference."""
    product = lock_active_product(db, member.business_id, data.product_id)
    difference = data.new_quantity - product.quantity
    if difference == 0:
        raise HTTPException(status_code=400, detail="The counted quantity equals the current stock, so there is nothing to adjust.")
    return record_movement(db, member, product, "adjust", difference, data.reason)


def as_utc(moment):
    """A time without a time zone is taken to be UTC."""
    return moment.replace(tzinfo=timezone.utc) if moment is not None and moment.tzinfo is None else moment


@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    product_id: int | None = None,
    kind: str | None = Query(default=None, alias="type", pattern="^(in|out|adjust)$"),
    from_time: datetime | None = Query(default=None, description="include movements at or after this time"),
    to_time: datetime | None = Query(default=None, description="include movements before this time"),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    member: BusinessMember = Depends(get_member),
    db: Session = Depends(get_db),
):
    """Newest first. The app turns the user's local dates into exact UTC times (from_time / to_time)."""
    query = (
        select(StockTransaction, Product.name, Product.sku, User.full_name)
        .join(Product, Product.id == StockTransaction.product_id)
        .outerjoin(User, User.id == StockTransaction.user_id)
        .where(StockTransaction.business_id == member.business_id)
    )
    if product_id is not None:
        query = query.where(StockTransaction.product_id == product_id)
    if kind is not None:
        query = query.where(StockTransaction.type == kind)
    if from_time is not None:
        query = query.where(StockTransaction.created_at >= as_utc(from_time))
    if to_time is not None:
        query = query.where(StockTransaction.created_at < as_utc(to_time))

    rows = db.execute(
        query.order_by(StockTransaction.created_at.desc(), StockTransaction.id.desc()).limit(limit).offset(offset)
    ).all()
    return [transaction_out(t, name, sku, user_name) for t, name, sku, user_name in rows]
