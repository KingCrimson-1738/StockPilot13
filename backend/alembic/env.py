"""Alembic reads our models and the DATABASE_URL setting, so
`alembic upgrade head` updates the schema without deleting any data."""
import os
from logging.config import fileConfig

from alembic import context

from app import config as app_config
from app import models  # noqa: F401  (importing registers the tables)
from app.database import Base, make_engine

alembic_config = context.config
if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

target_metadata = Base.metadata


def run_migrations_online():
    # Neon: the app uses the POOLED address, migrations should use the DIRECT one (set DIRECT_URL when running them)
    url = os.getenv("DIRECT_URL") or app_config.DATABASE_URL
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    engine = make_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
