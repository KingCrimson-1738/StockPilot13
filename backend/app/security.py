"""Password hashing (bcrypt) and login tokens (JWT).

How JWT works, in short:
  1. User logs in with email + password.
  2. We create a token containing the user id and an expiry time, and sign it
     with JWT_SECRET_KEY. Only the server knows the key, so nobody can forge one.
  3. The app sends the token with every request. We verify the signature and
     the expiry, then know who the user is. No session is stored on the server.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app import config


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password, password_hash):
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# A real bcrypt hash of a random text. Login checks the password against it when the email is unknown,
# so "no such user" takes as long as "wrong password" and the response time does not reveal which emails exist.
DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt()).decode("utf-8")


def create_access_token(user_id):
    expires = datetime.now(timezone.utc) + timedelta(minutes=config.TOKEN_EXPIRY_MINUTES)
    payload = {"sub": str(user_id), "exp": expires}
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def read_user_id_from_token(token):
    """Returns the user id, or None if the token is invalid or expired."""
    try:
        # "require": a token without an expiry (or without a user id) is rejected instead of living forever
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM],
                             options={"require": ["exp", "sub"]})
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
