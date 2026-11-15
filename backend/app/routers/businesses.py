"""Businesses and their members.

Switching between businesses is done by the desktop apps: they call
GET /businesses, show the list, and use the chosen business id in later URLs.
Every URL containing {business_id} is protected by get_member / get_owner_member.
"""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_member, get_owner_member
from app.models import Business, BusinessMember, User
from app.schemas import BusinessIn, BusinessOut, MemberAddIn, MemberOut

router = APIRouter(prefix="/businesses", tags=["Businesses"])


def to_business_out(business, role):
    return BusinessOut(
        id=business.id,
        name=business.name,
        description=business.description,
        address=business.address,
        phone=business.phone,
        currency=business.currency,
        default_min_stock=business.default_min_stock,
        my_role=role,
    )


def to_member_out(member):
    return MemberOut(
        id=member.id,
        user_id=member.user_id,
        email=member.user.email,
        full_name=member.user.full_name,
        role=member.role,
    )


@router.get("", response_model=list[BusinessOut])
def list_my_businesses(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Only businesses this user belongs to (owner or staff)."""
    rows = db.execute(
        select(Business, BusinessMember.role)
        .join(BusinessMember, BusinessMember.business_id == Business.id)
        .where(BusinessMember.user_id == user.id)
        .order_by(Business.name)
    ).all()
    return [to_business_out(business, role) for business, role in rows]


@router.post("", response_model=BusinessOut, status_code=status.HTTP_201_CREATED)
def create_business(
    data: BusinessIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Creates the business and makes the creator its owner, in one transaction."""
    business = Business(**data.model_dump())
    db.add(business)
    db.flush()  # gives the business an id without committing yet
    db.add(BusinessMember(business_id=business.id, user_id=user.id, role="owner"))
    db.commit()
    return to_business_out(business, "owner")


@router.get("/{business_id}", response_model=BusinessOut)
def get_business(member: BusinessMember = Depends(get_member), db: Session = Depends(get_db)):
    # member.business_id comes from the verified membership row, not from the URL
    business = db.get(Business, member.business_id)
    return to_business_out(business, member.role)


@router.put("/{business_id}", response_model=BusinessOut)
def update_business(
    data: BusinessIn,
    member: BusinessMember = Depends(get_owner_member),
    db: Session = Depends(get_db),
):
    business = db.get(Business, member.business_id)
    for field, value in data.model_dump().items():
        setattr(business, field, value)
    db.commit()
    return to_business_out(business, member.role)


# ---------- members ----------

@router.get("/{business_id}/members", response_model=list[MemberOut])
def list_members(member: BusinessMember = Depends(get_member), db: Session = Depends(get_db)):
    members = db.scalars(
        select(BusinessMember)
        .where(BusinessMember.business_id == member.business_id)
        .order_by(BusinessMember.id)
    ).all()
    return [to_member_out(m) for m in members]


@router.post(
    "/{business_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED
)
def add_staff_member(
    data: MemberAddIn,
    owner: BusinessMember = Depends(get_owner_member),
    db: Session = Depends(get_db),
):
    """Owner adds an already-registered user to the business as staff."""
    new_user = db.scalar(select(User).where(User.email == data.email.lower()))
    if new_user is None:
        raise HTTPException(status_code=404, detail="No registered user with this email")

    already_member = db.scalar(
        select(BusinessMember).where(
            BusinessMember.business_id == owner.business_id,
            BusinessMember.user_id == new_user.id,
        )
    )
    if already_member:
        raise HTTPException(status_code=409, detail="This user is already a member")

    new_member = BusinessMember(business_id=owner.business_id, user_id=new_user.id, role="staff")
    db.add(new_member)
    db.commit()
    return to_member_out(new_member)


@router.delete("/{business_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_staff_member(
    member_id: int,
    owner: BusinessMember = Depends(get_owner_member),
    db: Session = Depends(get_db),
):
    # Looking up by BOTH ids means an owner cannot touch another business's members
    target = db.scalar(
        select(BusinessMember).where(
            BusinessMember.id == member_id,
            BusinessMember.business_id == owner.business_id,
        )
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if target.role == "owner":
        raise HTTPException(status_code=400, detail="The owner cannot be removed")
    db.delete(target)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
