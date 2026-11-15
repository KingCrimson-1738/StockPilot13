from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.security import DUMMY_HASH, create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


def find_user_by_email(db, email):
    return db.scalar(select(User).where(User.email == email.lower()))


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if find_user_by_email(db, data.email):
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(
        email=data.email.lower(),
        full_name=data.full_name.strip(),
        password_hash=hash_password(data.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two people registered the same email at the same moment
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    return TokenOut(access_token=create_access_token(user.id), user=user)


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = find_user_by_email(db, data.email)
    # Same message AND same effort for "no such user" and "wrong password" so attackers learn nothing
    password_ok = verify_password(data.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not password_ok:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return TokenOut(access_token=create_access_token(user.id), user=user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
