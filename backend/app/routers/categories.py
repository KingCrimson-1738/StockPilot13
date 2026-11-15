"""Product categories. Every business has its own list; nothing is built in."""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_member, get_owner_member
from app.models import BusinessMember, Category, Product
from app.schemas import CategoryIn, CategoryOut

router = APIRouter(prefix="/businesses/{business_id}/categories", tags=["Categories"])


def name_is_taken(db, business_id, name, ignore_id=None):
    """Case-insensitive check inside ONE business ('Snacks' and 'snacks' count as the same)."""
    query = select(Category.id).where(
        Category.business_id == business_id, func.lower(Category.name) == name.lower()
    )
    if ignore_id is not None:
        query = query.where(Category.id != ignore_id)
    return db.scalar(query) is not None


def get_category_or_404(db, business_id, category_id):
    # Looked up by BOTH ids, so a category of another business is simply "not found"
    category = db.scalar(select(Category).where(Category.id == category_id, Category.business_id == business_id))
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


def count_products(db, category_id):
    return db.scalar(select(func.count(Product.id)).where(Product.category_id == category_id))


@router.get("", response_model=list[CategoryOut])
def list_categories(member: BusinessMember = Depends(get_member), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Category, func.count(Product.id))
        .outerjoin(Product, Product.category_id == Category.id)
        .where(Category.business_id == member.business_id)
        .group_by(Category.id)
        .order_by(func.lower(Category.name))
    ).all()
    return [CategoryOut(id=c.id, name=c.name, product_count=count) for c, count in rows]


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryIn, member: BusinessMember = Depends(get_member), db: Session = Depends(get_db)):
    if name_is_taken(db, member.business_id, data.name):
        raise HTTPException(status_code=409, detail="This business already has a category with that name")
    category = Category(business_id=member.business_id, name=data.name)
    db.add(category)
    try:
        db.commit()
    except IntegrityError:  # two people saved the same name at the same moment
        db.rollback()
        raise HTTPException(status_code=409, detail="This business already has a category with that name")
    return CategoryOut(id=category.id, name=category.name, product_count=0)


@router.put("/{category_id}", response_model=CategoryOut)
def rename_category(
    category_id: int, data: CategoryIn, member: BusinessMember = Depends(get_member), db: Session = Depends(get_db)
):
    category = get_category_or_404(db, member.business_id, category_id)
    if name_is_taken(db, member.business_id, data.name, ignore_id=category.id):
        raise HTTPException(status_code=409, detail="This business already has a category with that name")
    category.name = data.name
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This business already has a category with that name")
    return CategoryOut(id=category.id, name=category.name, product_count=count_products(db, category.id))


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int, owner: BusinessMember = Depends(get_owner_member), db: Session = Depends(get_db)
):
    category = get_category_or_404(db, owner.business_id, category_id)
    in_use = count_products(db, category.id)
    if in_use:
        raise HTTPException(
            status_code=409,
            detail=f"{in_use} product(s) still use this category. Move or remove them first.",
        )
    db.delete(category)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
