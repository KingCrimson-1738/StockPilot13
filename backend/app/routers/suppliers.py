"""Suppliers. Each business keeps its own list."""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_member, get_owner_member
from app.models import BusinessMember, Product, Supplier
from app.schemas import SupplierIn, SupplierOut

router = APIRouter(prefix="/businesses/{business_id}/suppliers", tags=["Suppliers"])

NAME_TAKEN = "This business already has a supplier with that name"


def to_supplier_out(supplier, product_count):
    return SupplierOut(
        id=supplier.id, name=supplier.name, contact_person=supplier.contact_person,
        email=supplier.email, phone=supplier.phone, address=supplier.address, product_count=product_count,
    )


def name_is_taken(db, business_id, name, ignore_id=None):
    query = select(Supplier.id).where(Supplier.business_id == business_id, func.lower(Supplier.name) == name.lower())
    if ignore_id is not None:
        query = query.where(Supplier.id != ignore_id)
    return db.scalar(query) is not None


def get_supplier_or_404(db, business_id, supplier_id):
    supplier = db.scalar(select(Supplier).where(Supplier.id == supplier_id, Supplier.business_id == business_id))
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


def count_products(db, supplier_id):
    return db.scalar(select(func.count(Product.id)).where(Product.supplier_id == supplier_id))


@router.get("", response_model=list[SupplierOut])
def list_suppliers(member: BusinessMember = Depends(get_member), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Supplier, func.count(Product.id))
        .outerjoin(Product, Product.supplier_id == Supplier.id)
        .where(Supplier.business_id == member.business_id)
        .group_by(Supplier.id)
        .order_by(func.lower(Supplier.name))
    ).all()
    return [to_supplier_out(supplier, count) for supplier, count in rows]


@router.post("", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
def create_supplier(data: SupplierIn, member: BusinessMember = Depends(get_member), db: Session = Depends(get_db)):
    if name_is_taken(db, member.business_id, data.name):
        raise HTTPException(status_code=409, detail=NAME_TAKEN)
    supplier = Supplier(business_id=member.business_id, **data.model_dump())
    db.add(supplier)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=NAME_TAKEN)
    return to_supplier_out(supplier, 0)


@router.put("/{supplier_id}", response_model=SupplierOut)
def update_supplier(
    supplier_id: int, data: SupplierIn, member: BusinessMember = Depends(get_member), db: Session = Depends(get_db)
):
    supplier = get_supplier_or_404(db, member.business_id, supplier_id)
    if name_is_taken(db, member.business_id, data.name, ignore_id=supplier.id):
        raise HTTPException(status_code=409, detail=NAME_TAKEN)
    for field, value in data.model_dump().items():
        setattr(supplier, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=NAME_TAKEN)
    return to_supplier_out(supplier, count_products(db, supplier.id))


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(
    supplier_id: int, owner: BusinessMember = Depends(get_owner_member), db: Session = Depends(get_db)
):
    supplier = get_supplier_or_404(db, owner.business_id, supplier_id)
    in_use = count_products(db, supplier.id)
    if in_use:
        raise HTTPException(
            status_code=409,
            detail=f"{in_use} product(s) still use this supplier. Change their supplier first.",
        )
    db.delete(supplier)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
