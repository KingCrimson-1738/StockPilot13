"""Reads settings from environment variables (or a local .env file).

Secrets are never written in the source code.
"""
import os

from dotenv import load_dotenv

load_dotenv()  # only has an effect when a local .env file exists

DATABASE_URL = os.getenv("DATABASE_URL", "")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
TOKEN_EXPIRY_MINUTES = int(os.getenv("TOKEN_EXPIRY", "60"))
JWT_ALGORITHM = "HS256"


def check_settings():
    """Fail early with a clear message if a required setting is missing."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    if len(JWT_SECRET_KEY) < 32:
        raise RuntimeError("JWT_SECRET_KEY is missing or too short (min 32 characters)")
