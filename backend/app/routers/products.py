"""Products.

Rules enforced here:
  * a product, its category and its supplier must all belong to the same business
  * the SKU is unique inside a business
  * quantity cannot be edited directly - it only changes through stock movements.
    (A new product may start with an opening quantity, recorded as a stock-in transaction.)
  * a product with stock history is archived, never deleted, so history is kept
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_member, get_owner_member
from app.models import Business, BusinessMember, Category, Product, StockTransaction, Supplier
from app.schemas import ProductCreate, ProductIn, ProductOut, ProductRemovedOut

router = APIRouter(prefix="/businesses/{business_id}/products", tags=["Products"])

SKU_TAKEN = "Another product in this business already uses that SKU"


# ---------- helpers ----------

def products_query(business_id):
    """Products of ONE business together with their category and supplier names."""
    return (
        select(Product, Category.name, Supplier.name)
        .outerjoin(Category, Category.id == Product.category_id)
        .outerjoin(Supplier, Supplier.id == Product.supplier_id)
        .where(Product.business_id == business_id)
    )


def to_product_out(product, category_name, supplier_name, default_min_stock):
    alert_level = product.min_stock if product.min_stock is not None else default_min_stock
    if product.quantity == 0:
        stock_status = "out"
    elif product.quantity <= alert_level:
        stock_status = "low"
    else:
        stock_status = "ok"
    return ProductOut(
        id=product.id, name=product.name, sku=product.sku,
        category_id=product.category_id, category_name=category_name,
        supplier_id=product.supplier_id, supplier_name=supplier_name,
        purchase_price=float(product.purchase_price), selling_price=float(product.selling_price),
        quantity=product.quantity, min_stock=product.min_stock, alert_level=alert_level,
        stock_status=stock_status, is_archived=product.is_archived,
    )


def load_product_out(db, business_id, product_id):
    """One product as the API returns it, or 404 if it is not in this business."""
    row = db.execute(products_query(business_id).where(Product.id == product_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")
    business = db.get(Business, business_id)
    return to_product_out(*row, business.default_min_stock)


def check_category_and_supplier(db, business_id, category_id, supplier_id):
    """Rule: a product may only use a category / supplier of its own business."""
    if category_id is not None and db.scalar(
        select(Category.id).where(Category.id == category_id, Category.business_id == business_id)
    ) is None:
        raise HTTPException(status_code=400, detail="That category does not belong to this business")
    if supplier_id is not None and db.scalar(
        select(Supplier.id).where(Supplier.id == supplier_id, Supplier.business_id == business_id)
    ) is None:
        raise HTTPException(status_code=400, detail="That supplier does not belong to this business")


def sku_is_taken(db, business_id, sku, ignore_id=None):
    query = select(Product.id).where(Product.business_id == business_id, func.lower(Product.sku) == sku.lower())
    if ignore_id is not None:
        query = query.where(Product.id != ignore_id)
    return db.scalar(query) is not None


def get_product_or_404(db, business_id, product_id):
    product = db.scalar(select(Product).where(Product.id == product_id, Product.business_id == business_id))
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


# ---------- endpoints ----------

@router.get("", response_model=list[ProductOut])
def list_products(
    search: str | None = Query(default=None, max_length=100, description="matches name or SKU"),
    category_id: int | None = None,
    supplier_id: int | None = None,
    stock: str = Query(default="all", pattern="^(all|ok|low|out)$"),
    archived: str = Query(default="active", pattern="^(active|archived|all)$"),
    member: BusinessMember = Depends(get_member),
    db: Session = Depends(get_db),
):
    business = db.get(Business, member.business_id)
    query = products_query(business.id)

    if search and search.strip():
        text = search.strip()
        query = query.where(or_(Product.name.icontains(text, autoescape=True), Product.sku.icontains(text, autoescape=True)))
    if category_id is not None:
        query = query.where(Product.category_id == category_id)
    if supplier_id is not None:
        query = query.where(Product.supplier_id == supplier_id)
    if archived == "active":
        query = query.where(Product.is_archived.is_(False))
    elif archived == "archived":
        query = query.where(Product.is_archived.is_(True))

    alert_level = func.coalesce(Product.min_stock, business.default_min_stock)
    if stock == "out":
        query = query.where(Product.quantity == 0)
    elif stock == "low":
        query = query.where(Product.quantity > 0, Product.quantity <= alert_level)
    elif stock == "ok":
        query = query.where(Product.quantity > alert_level)

    rows = db.execute(query.order_by(func.lower(Product.name), Product.id)).all()
    return [to_product_out(*row, business.default_min_stock) for row in rows]


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(data: ProductCreate, member: BusinessMember = Depends(get_member), db: Session = Depends(get_db)):
    check_category_and_supplier(db, member.business_id, data.category_id, data.supplier_id)
    if sku_is_taken(db, member.business_id, data.sku):
        raise HTTPException(status_code=409, detail=SKU_TAKEN)

    product = Product(
        business_id=member.business_id, name=data.name, sku=data.sku,
        category_id=data.category_id, supplier_id=data.supplier_id,
        purchase_price=data.purchase_price, selling_price=data.selling_price,
        min_stock=data.min_stock, quantity=data.opening_quantity,
    )
    db.add(product)
    db.flush()  # gives the product an id
    if data.opening_quantity > 0:  # the product and its first transaction are saved together, or not at all
        db.add(StockTransaction(
            business_id=member.business_id, product_id=product.id, user_id=member.user_id,
            type="in", quantity_change=data.opening_quantity, quantity_after=data.opening_quantity,
            reason="Opening stock",
        ))
    try:
        db.commit()
    except IntegrityError:  # two people saved the same SKU at the same moment
        db.rollback()
        raise HTTPException(status_code=409, detail=SKU_TAKEN)
    return load_product_out(db, member.business_id, product.id)


@router.put("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int, data: ProductIn, member: BusinessMember = Depends(get_member), db: Session = Depends(get_db)
):
    product = get_product_or_404(db, member.business_id, product_id)
    check_category_and_supplier(db, member.business_id, data.category_id, data.supplier_id)
    if sku_is_taken(db, member.business_id, data.sku, ignore_id=product.id):
        raise HTTPException(status_code=409, detail=SKU_TAKEN)

    for field, value in data.model_dump().items():  # note: 'quantity' is not a field of ProductIn
        setattr(product, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=SKU_TAKEN)
    return load_product_out(db, member.business_id, product.id)


@router.delete("/{product_id}", response_model=ProductRemovedOut)
def remove_product(
    product_id: int, owner: BusinessMember = Depends(get_owner_member), db: Session = Depends(get_db)
):
    """Archive if the product has stock history (history must never disappear); otherwise delete it."""
    product = get_product_or_404(db, owner.business_id, product_id)
    has_history = db.scalar(select(func.count(StockTransaction.id)).where(StockTransaction.product_id == product.id)) > 0
    if has_history:
        product.is_archived = True
        db.commit()
        return ProductRemovedOut(action="archived", message="The product has stock history, so it was archived instead of deleted.")
    db.delete(product)
    db.commit()
    return ProductRemovedOut(action="deleted", message="The product was deleted.")


@router.post("/{product_id}/restore", response_model=ProductOut)
def restore_product(
    product_id: int, owner: BusinessMember = Depends(get_owner_member), db: Session = Depends(get_db)
):
    product = get_product_or_404(db, owner.business_id, product_id)
    product.is_archived = False
    db.commit()
    return load_product_out(db, owner.business_id, product.id)
