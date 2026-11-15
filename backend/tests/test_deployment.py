"""Things that only matter once the app is deployed: URL handling, the health check, safe migrations."""
import os
import subprocess
import sys
from pathlib import Path

import psycopg
from sqlalchemy.engine import make_url

from app.database import fix_url, make_engine
from tests.conftest import auth_header, register

BACKEND = Path(__file__).resolve().parent.parent


def test_database_urls_from_neon_and_supabase_are_understood():
    assert fix_url("postgres://u:p@h/db").startswith("postgresql+psycopg://u:p@h/db")
    assert fix_url("postgresql://u:p@h/db?sslmode=require&channel_binding=require") == \
        "postgresql+psycopg://u:p@h/db?sslmode=require&channel_binding=require"
    assert fix_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"   # already right: unchanged
    url = make_url(fix_url("postgresql://u:p%40ss@ep-x-pooler.eu.aws.neon.tech/db?sslmode=require"))
    assert url.password == "p@ss" and url.query["sslmode"] == "require"   # special characters in the password survive


def test_engine_is_safe_for_serverless_and_poolers():
    engine = make_engine("postgresql://u:p@h/db")
    assert engine.pool.__class__.__name__ == "NullPool"                    # no connections kept between requests
    assert engine.dialect.name == "postgresql"


def test_health_check_reports_database_status(client):
    ok = client.get("/health")
    assert ok.status_code == 200 and ok.json() == {"status": "ok", "database": "ok"}
    assert client.get("/").json()["status"] == "ok"   # the root URL does not need the database


def test_health_check_hides_details_when_database_is_down(client, monkeypatch):
    from app import main

    class Broken:
        def connect(self):
            raise RuntimeError("password authentication failed for user secretuser at host db.internal")

    monkeypatch.setattr(main, "engine", Broken())
    response = client.get("/health")
    assert response.status_code == 503
    assert "secretuser" not in response.text and "db.internal" not in response.text


def test_the_api_has_no_hardcoded_business_data(client):
    """A fresh install knows no businesses, products or users at all."""
    user = register(client, email="new@example.com")
    assert client.get("/businesses", headers=auth_header(user["access_token"])).json() == []


# ---------- migrations never reset data ----------

def test_running_migrations_again_keeps_existing_data():
    """Create a brand-new database, migrate it, add a row, migrate AGAIN: the row must survive."""
    server = make_url(os.environ["DATABASE_URL"]).set(drivername="postgresql")
    name = "stockpilot_migration_check"
    admin = psycopg.connect(server.render_as_string(hide_password=False), autocommit=True)
    admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
    admin.execute(f'CREATE DATABASE "{name}"')
    target = server.set(database=name).render_as_string(hide_password=False)
    env = {**os.environ, "DATABASE_URL": target}

    def migrate():
        return subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env,
                              capture_output=True, text=True)

    try:
        first = migrate()
        assert first.returncode == 0, first.stderr
        with psycopg.connect(target) as db:
            db.execute("INSERT INTO users (email, full_name, password_hash, created_at) VALUES ('keep@example.com', 'Keep Me', 'x', now())")
        second = migrate()
        assert second.returncode == 0, second.stderr
        with psycopg.connect(target) as db:
            assert db.execute("SELECT full_name FROM users WHERE email = 'keep@example.com'").fetchone() == ("Keep Me",)
            tables = {r[0] for r in db.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'").fetchall()}
        assert {"users", "businesses", "business_members", "categories", "suppliers", "products", "stock_transactions",
                "alembic_version"} <= tables
        # the models and the migration agree (nobody changed a model without writing a migration)
        check = subprocess.run([sys.executable, "-m", "alembic", "check"], cwd=BACKEND, env=env, capture_output=True, text=True)
        assert check.returncode == 0, check.stdout + check.stderr
    finally:
        admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.close()


def test_migrations_use_the_direct_url_when_given():
    text = (BACKEND / "alembic" / "env.py").read_text()
    assert 'os.getenv("DIRECT_URL")' in text
