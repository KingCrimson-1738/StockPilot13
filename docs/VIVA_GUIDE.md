# StockPilot - Viva Guide

## 1. One-minute pitch
StockPilot lets several small businesses keep their stock in one shared system. A FastAPI backend holds all the rules
and a PostgreSQL database holds all the data. Two desktop apps (Python Tkinter and Java Swing) are just screens that
call the same REST API. Because the rules live on the server, neither app can break them.

## 2. Architecture in four lines
1. Client sends an HTTP request with `Authorization: Bearer <JWT>`.
2. Backend decodes the token -> finds the user -> checks the user is a **member** of the business in the URL.
3. Router runs the rule (role check, stock check) using SQLAlchemy inside one database transaction.
4. Response goes back as JSON validated by Pydantic.

Tables: `users`, `businesses`, `business_members` (user + business + role), `categories`, `suppliers`, `products`,
`stock_transactions`. Every business-owned table has a `business_id`.

## 3. Likely questions and answers
**How do you stop one business seeing another's data?**
Every route has `business_id` in the URL. A dependency checks a `business_members` row exists for (user, business);
if not -> 404 (so existence is not leaked). Every query also filters by `business_id`, and child records are fetched by
their own id AND the business id. `tests/test_hardening.py` scans all routes and fails if one with a business id lacks
the membership check.

**Owner vs Staff?**
Role stored in `business_members`. Owner-only actions (edit business, members, products, categories, suppliers,
adjust stock) use `get_owner_member`; staff get 403. Staff can view and record stock in/out.

**How is stock kept from going negative?**
Two layers. The code locks the product row (`SELECT ... FOR UPDATE`), checks the quantity and answers 409 if too low.
Independently the database has `CHECK (quantity >= 0)`, so even a bug cannot save a negative number.

**What if two people sell the last item at the same time?**
The row lock makes the second request wait; when it gets the row it sees the new quantity and is rejected with 409.

**How do you make sure every movement is recorded?**
Quantity update and `stock_transactions` insert happen in the same transaction and one commit. Either both are saved or
neither (tested: a rejected request leaves quantity and history unchanged).

**How are passwords stored?**
bcrypt hash with salt; the plain password is never stored or returned. Login runs a dummy bcrypt check for unknown
emails so response time does not reveal which emails exist.

**How does JWT work here?**
On login the server signs `{sub: user_id, exp}` with `JWT_SECRET_KEY` (HS256). The client sends it on each request. The
server verifies signature and expiry; tokens without `exp`, expired, forged, or for deleted users are rejected.
Expiry comes from `TOKEN_EXPIRY`.

**Where are secrets kept?**
Only in environment variables (`DATABASE_URL`, `DIRECT_URL`, `JWT_SECRET_KEY`, `TOKEN_EXPIRY`); `.env` is git-ignored;
`.env.example` has placeholders.

**How do migrations work without losing data?**
Alembic versions the schema (`alembic upgrade head`). It only applies changes not yet applied; nothing drops data.
A test inserts data, reruns the migration and checks the data is still there.

**Why Neon pooled vs direct URL?**
The running app uses the pooled (PgBouncer) address, so it uses `NullPool` and `prepare_threshold=None`. Alembic uses the
direct address because migrations need a normal session.

**Why not Tkinter talking to the database directly?**
Then every client would need DB credentials and would have to re-implement the rules. With an API, one place enforces
security and both clients stay thin.

**How do the clients stay responsive?**
Tk: network calls run in a worker thread; results come back through a queue polled by the UI thread (`run_async`).
Swing: `SwingWorker`. A stale-response guard ignores late answers for a screen you already left.

**How is the low-stock suggestion computed?**
Item is listed when quantity <= alert level. Suggested order = max(2 x level - quantity, 1), i.e. refill to about twice
the alert level.

**What is CSV injection and what did you do?**
A cell starting with `=`, `+`, `-`, `@` can run as a formula in Excel. Exports prefix such text with `'`.

**What would you improve with more time?**
Login rate limiting, password reset by email, refresh tokens, pagination, audit log screen, real sales prices per
transaction (sales value is currently an estimate).

## 4. Five-minute demo script
1. Show `/docs` of the backend; register Asha (Owner) in the Tk app and create business "Asha Traders".
2. Add a category, a supplier and two products (one with alert level 5).
3. Stock In 20, Stock Out 18 -> dashboard shows low stock; open Restock list.
4. Try Stock Out 100 -> red error "insufficient stock" (rule enforced by server).
5. History page: every movement with user and time; export CSV.
6. Reports page: charts and period filter.
7. Log in as Ravi (Staff, added by email): owner-only buttons are refused / hidden.
8. Open the Swing app with the same account: same data, proving one shared API.
9. Show a second business: Asha's data is not visible there.

## 5. Code walkthrough (where to look)
| Topic | File |
|---|---|
| Config and secrets | `backend/app/config.py` |
| DB engine, pooler settings | `backend/app/database.py` |
| Password hash, JWT | `backend/app/security.py` |
| Membership / role checks | `backend/app/deps.py` |
| Tables and constraints | `backend/app/models.py`, `backend/alembic/versions/` |
| Stock rule + atomic movement | `backend/app/routers/stock.py` (`record_movement`) |
| Reports and CSV | `backend/app/routers/reports.py` |
| Security structure tests | `backend/tests/test_hardening.py` |
| Tk async calls | `desktop_tk/background.py`, `desktop_tk/api_client.py` |
| Tk charts (Agg -> image) | `desktop_tk/widgets/chart.py` |
| Swing API + threads | `desktop_swing/.../ApiClient.java`, `Async.java` |

## 6. Honest limitations (say these before they are asked)
See the list in the root `README.md`. In short: not verified on live Vercel/Neon from the dev sandbox; no rate limiting
or password reset; token kept in memory only; no pagination; sales value is an estimate.
