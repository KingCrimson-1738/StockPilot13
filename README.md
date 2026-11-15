# StockPilot

A multi-user, multi-business inventory system. One REST backend, two desktop clients.

| Part | Technology | Folder |
|---|---|---|
| Backend API | FastAPI, SQLAlchemy 2, Pydantic, JWT (PyJWT), bcrypt, Alembic | `backend/` |
| Database | PostgreSQL (Neon / Supabase in production) | - |
| Main client | Python, CustomTkinter, Pillow, Matplotlib | `desktop_tk/` |
| Companion client | Java Swing (login, business switch, dashboard, products add/edit, stock in/out, suppliers, history, basic reports) | `desktop_swing/` |
| Docs and tools | architecture, deployment, viva guide, smoke tests | `docs/`, `tools/` |

## What it does
- Register / log in (password hashed with bcrypt, 
  access token = JWT). One person can belong to several businesses.
- **Owner** and **Staff** roles per business. Owners manage products, categories, suppliers, members and stock
  adjustments; staff record stock in/out and read everything.
- Products with SKU, category, supplier, prices, low-stock alert level; archive / restore.
- Stock in, stock out, adjust. Stock can never go below zero. Every movement is saved as a history row in the same
  database transaction as the quantity change.
- Dashboard with charts, low-stock restock list with suggested quantities, inventory value by category, movement report and charts,
  CSV exports (products, history, low stock).
- No business data is hardcoded anywhere: everything comes from the database, scoped by `business_id`.

## Quick start (local)
Requirements: Python 3.13, PostgreSQL 14+ (or a free Neon database), Java 17+ and Maven (only for Swing).

```
# 1. backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then edit: DATABASE_URL, JWT_SECRET_KEY (long random text), TOKEN_EXPIRY
alembic upgrade head        # creates the tables; running it again never deletes data
python -m uvicorn api.index:app --port 8000            # API docs: http://127.0.0.1:8000/docs

# 2. main client (new terminal)
cd desktop_tk
pip install -r requirements.txt
python main.py              # server address: STOCKPILOT_API_URL env var, or server.txt, or http://127.0.0.1:8000

# 3. Swing client (optional)
cd desktop_swing && mvn package && java -jar target/stockpilot-swing-1.0-all.jar
```
Secrets live only in environment variables / `.env` (which is git-ignored). See `backend/.env.example`.

## Tests
```
cd backend && pip install -r requirements-dev.txt
# tests need a real PostgreSQL database that can be wiped: set TEST_DATABASE_URL to an EMPTY throw-away database
python -m pytest -q                          # 125 tests: auth, isolation, roles, stock rules, reports, migrations, hardening
python tools/check_deployment.py https://YOUR-APP.vercel.app    # smoke test of the deployed backend
```
UI driver scripts (real windows, real clicks) are in `tools/ui_tests/` (see its README). Java tests are in
`desktop_swing/src/test/java`.

## Documentation
- `docs/ARCHITECTURE.md` - how it fits together, tables, endpoints, stock rules, reports.
- `docs/DEPLOYMENT.md` - Neon + Vercel step by step, environment variables, troubleshooting.
- `docs/TESTING.md` - the 20 test scenarios from the brief mapped to the tests that cover them.
- `docs/VIVA_GUIDE.md` - likely questions with answers, a demo script, code walkthrough, honest limitations.

## Known limitations (said honestly)
- Not tested against real Vercel/Neon from the development sandbox (it had no access); the steps in
  `docs/DEPLOYMENT.md` and `tools/check_deployment.py` exist so you can verify it yourself. `mvn package` was likewise
  not run there (the Swing code was compiled and tested with `javac`).
- No login rate limiting, password reset or e-mail verification.
- Tokens are kept in memory only: closing the app logs you out.
- Product list is not paginated; history screen shows the newest 200 rows.
- Sales value in reports is an estimate (uses the product's current selling price).
- Look and feel was checked on Linux; fonts may differ slightly on Windows/macOS.
