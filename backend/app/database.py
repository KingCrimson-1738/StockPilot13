"""Database connection.

On Vercel every request may run in a brand new short-lived process, so we do
not keep a connection pool (NullPool). Neon's own pooler handles pooling.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from app import config


def fix_url(url):
    """Neon/Supabase give 'postgres://' or 'postgresql://'. SQLAlchemy needs
    to be told to use the psycopg (v3) driver."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def make_engine(url):
    url = fix_url(url)
    if url.startswith("sqlite"):  # only used for quick local tests
        return create_engine(url, connect_args={"check_same_thread": False})
    # prepare_threshold=None: Neon's pooler (PgBouncer) hands our queries to different server connections, so we turn
    # off psycopg's "server-side prepared statements", which assume the same connection every time.
    return create_engine(url, poolclass=NullPool, pool_pre_ping=True, connect_args={"prepare_threshold": None})


class Base(DeclarativeBase):
    pass


engine = make_engine(config.DATABASE_URL) if config.DATABASE_URL else None
SessionLocal = sessionmaker(bind=engine, autoflush=False) if engine else None


def get_db():
    """FastAPI dependency: gives each request its own session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
