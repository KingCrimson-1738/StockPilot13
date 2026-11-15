"""Shared checks used by every protected endpoint.

get_current_user  -> "who is calling?"  (reads the JWT)
get_member        -> "may they use THIS business?"  (looks in business_members)
get_owner_member  -> same, but the role must be 'owner'

This is the heart of multi-business isolation. The business_id in the URL is
never trusted by itself: it only counts if this user has a membership row.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BusinessMember, User
from app.security import read_user_id_from_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
):
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not logged in or session expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    user_id = read_user_id_from_token(credentials.credentials)
    if user_id is None:
        raise unauthorized
    user = db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


def get_member(
    business_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns the user's BusinessMember row for this business, or 404.

    We answer 404 (not 403) for outsiders so nobody can discover which
    business ids exist.
    """
    member = db.scalar(
        select(BusinessMember).where(
            BusinessMember.business_id == business_id,
            BusinessMember.user_id == user.id,
        )
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Business not found")
    return member


def get_owner_member(member: BusinessMember = Depends(get_member)):
    if member.role != "owner":
        raise HTTPException(status_code=403, detail="Only the business owner can do this")
    return member
