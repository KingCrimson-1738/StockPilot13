# StockPilot: Architecture (viva notes)

## The big picture

```
Tkinter app (primary) ──┐
                        ├── HTTPS + JSON + JWT ──> FastAPI (Vercel) ──> PostgreSQL (Neon)
Java Swing app (small) ─┘
```

Think of a restaurant. The database is the pantry. The FastAPI backend is the
kitchen: the only place allowed to touch the pantry, and it checks every order.
The two desktop apps are waiters: they take requests from the user and carry them
to the kitchen. Neither app has its own data or its own business rules, which is
why both always show the same products.

## Folder layout

```
backend/app/
  main.py        creates the app, includes routers (no logic)
  config.py      reads DATABASE_URL, JWT_SECRET_KEY, TOKEN_EXPIRY
  database.py    engine + one session per request
  models.py      the 7 tables
  schemas.py     Pydantic: validates input, shapes output (never includes password hash)
  security.py    bcrypt hashing + JWT create/verify
  deps.py        get_current_user, get_member, get_owner_member
  routers/       auth.py, businesses.py, dashboard.py, categories.py, products.py
backend/alembic/ migrations (schema changes without deleting data)
backend/tests/   pytest, run against real PostgreSQL
```

## Database relationships

```
users --< business_members >-- businesses
businesses --< categories, suppliers, products, stock_transactions
products >-- category (optional), supplier (optional)
products --< stock_transactions
```

- `business_members` is the join table: one row per (user, business) with a role,
  `owner` or `staff`. A user can belong to many businesses and a business can have many users.
- Every business table carries `business_id`. That column is what separates one business's data from another's.
- Unique rules are per business: `(business_id, name)` for categories and suppliers,
  `(business_id, sku)` for products. Two businesses may both have a "Snacks" category.
- `CHECK (quantity >= 0)` on products: even if the code had a bug, the database refuses negative stock.

## How login works (JWT)

1. `POST /auth/login` with email and password. The server compares the password with the stored bcrypt hash.
2. If it matches, the server creates a token containing the user id and an expiry time, signed with `JWT_SECRET_KEY`.
3. The app stores the token in memory and sends `Authorization: Bearer <token>` on every request.
4. `get_current_user` verifies the signature and expiry and loads the user.
   Nothing is stored on the server, and nobody can forge a token without the secret.

Passwords are never stored, only bcrypt hashes. Wrong email and wrong password give the same error message.

## How businesses are isolated

Every URL like `/businesses/{business_id}/...` goes through `get_member`:

1. Who is calling? (from the token)
2. Is there a `business_members` row for (this user, this business)?
   - No: **404 Business not found** (same answer whether the business exists or not, so ids can't be probed).
   - Yes: continue. Handlers use `member.business_id` from that verified row, not the raw URL value.

`get_owner_member` adds a role check (staff get **403** on owner-only actions).
Child records (members, later products etc.) are always looked up by BOTH their own id AND the business id,
so a valid id from another business returns 404.

## Endpoints built so far

| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | /auth/register | anyone | create account, returns token |
| POST | /auth/login | anyone | returns token |
| GET | /auth/me | logged in | current user |
| GET | /businesses | logged in | my businesses + my role in each |
| POST | /businesses | logged in | create business (creator becomes owner) |
| GET | /businesses/{id} | member | business details |
| PUT | /businesses/{id} | owner | edit business details and default low-stock level |
| GET | /businesses/{id}/members | member | list members |
| POST | /businesses/{id}/members | owner | add a registered user as staff (by email) |
| DELETE | /businesses/{id}/members/{member_id} | owner | remove staff (owner cannot be removed) |
| GET | /businesses/{id}/dashboard | member | totals, low/out-of-stock counts, 10 latest stock movements |
| GET | /businesses/{id}/categories | member | categories with a product count |
| POST | /businesses/{id}/categories | member | add category (name unique per business, case-insensitive) |
| PUT | /businesses/{id}/categories/{cid} | member | rename |
| DELETE | /businesses/{id}/categories/{cid} | owner | delete; refused (409) while products use it |
| GET | /businesses/{id}/products | member | list; query: `search`, `category_id`, `supplier_id`, `stock` (all/ok/low/out), `archived` (active/archived/all) |
| POST | /businesses/{id}/products | member | add product; optional `opening_quantity` becomes a stock-in transaction |
| PUT | /businesses/{id}/products/{pid} | member | edit details (never the quantity) |
| DELETE | /businesses/{id}/products/{pid} | owner | archive if it has stock history, otherwise delete |
| POST | /businesses/{id}/products/{pid}/restore | owner | un-archive |
| GET | /businesses/{id}/suppliers | member | list with `product_count` |
| POST / PUT | /businesses/{id}/suppliers[/{sid}] | member | add / edit (name unique per business) |
| DELETE | /businesses/{id}/suppliers/{sid} | owner | refused (409) while products use it |
| POST | /businesses/{id}/stock/in | member | add stock (quantity 1..1,000,000, optional reason) |
| POST | /businesses/{id}/stock/out | member | remove stock; 409 if more than available |
| POST | /businesses/{id}/stock/adjust | owner | set the counted quantity; reason (3+ letters) required |
| GET | /businesses/{id}/reports/low-stock | member | products at/below their alert level + suggested order |
| GET | /businesses/{id}/reports/inventory-by-category | member | units and stock value (at cost) per category |
| GET | /businesses/{id}/reports/movements | member | added/removed totals, per-day series, top 5 sellers; `from_time`, `to_time`, `tz_offset_minutes` |
| GET | /businesses/{id}/exports/products.csv, transactions.csv, low-stock.csv | member | CSV downloads |
| GET | /businesses/{id}/transactions | member | history, newest first; `product_id`, `type`, `from_time`, `to_time`, `limit`, `offset` |

"Switching business" is done by the app: it lists `/businesses`, the user picks one, and the app
uses that id in later URLs. The server re-checks membership on every request.

## HTTP status codes used

200/201/204 success. 401 not logged in or bad/expired token. 403 logged in but wrong role.
404 not found or not your business. 409 conflict (duplicate). 422 invalid input.

## Stock rules (Phase 6)

Stock-in, stock-out and adjustments all go through one function, `record_movement` (backend/app/routers/stock.py):

1. **Lock the row.** `SELECT ... FOR UPDATE` on the product. A second request for the same product waits here
   until the first has committed, so two people can never both "sell the last unit".
2. **Check.** New quantity below 0 -> 409 "Not enough stock. Available: X, requested: Y." Archived product -> 400.
3. **Write both.** Update `products.quantity` and insert the `stock_transactions` row, then ONE commit.
   If anything fails in between, the whole thing is rolled back (neither change is saved).
4. **Safety net.** The database itself has `CHECK (quantity >= 0)`, so even a bug in the code cannot store negative stock.

Each transaction row stores the signed change, the quantity after, the reason, and who did it. Rows are never
edited or deleted; archived products keep their history. Only owners may *adjust* (a stock count correction),
because it overrides the book figure; staff may record stock in and out.

**Time zones.** The server stores UTC. The history screen turns the dates the user types ("2026-11-16") into the exact
UTC instants of local midnight and sends those (`from_time` inclusive, `to_time` exclusive), so "16 Nov" means
16 Nov in the user's own country, not in UTC.

## Reports and exports (Phase 7)

- **Restock rule:** active product with quantity <= its alert level (own level, else the business default).
  Suggested order = (2 x alert level) - quantity, at least 1. Estimated cost = suggested order x purchase price.
  Sorted fewest-in-stock first, so out-of-stock items lead.
- **Movement report:** one grouped SQL query per figure, always filtered by `business_id`. "Stock added" includes opening
  stock. **Sales value is an estimate** (units removed x the product's *current* selling price) because the system does not
  record the price at the time of each sale. Say this in the viva.
- **Days in the user's time zone:** the client sends its UTC offset (`tz_offset_minutes`); the server shifts each UTC
  timestamp by it before grouping by date, so a sale at 01:30 IST counts on the Indian date.
- **CSV:** built with Python's `csv` module (commas and quotes are escaped correctly), UTF-8 with a BOM so Excel shows
  all characters. **CSV injection protection:** a cell starting with `=`, `+`, `-` or `@` gets a leading `'`, so Excel
  cannot run it as a formula (a product named `=HYPERLINK(...)` would otherwise be dangerous).
- **Charts:** Matplotlib draws each chart with its software (Agg) renderer into a picture shown in the page, redrawn on
  resize. We avoid Matplotlib's Tk canvas because it caused random crashes with some Tk versions.

## Dashboard numbers (how they are calculated)

All figures come from one query over the open business's rows, excluding archived products:

- Total products = count of active products.
- Units in stock = sum of quantity.
- Inventory value = sum of quantity x purchase price.
- Low stock = quantity > 0 and quantity <= the product's own alert level, or the business default if it has none.
- Out of stock = quantity = 0.

## Deployment (Phase 9)

See `docs/DEPLOYMENT.md`. Vercel runs `backend/api/index.py`; Neon holds the data. The app uses Neon's pooled address, so
`database.py` uses `NullPool` and turns off psycopg's server-side prepared statements (a pooler may give each query a different
connection). Migrations use the direct address (`DIRECT_URL`). `GET /health` proves the database is reachable.
Clients find the server through `STOCKPILOT_API_URL` (or `desktop_tk/server.txt`).

## The Java Swing app (Phase 8)

A smaller companion client in `desktop_swing/` (see its README). It calls the same REST endpoints with Java's
`HttpClient`, so every rule (membership check, roles, no negative stock) is enforced by the server for both clients.
Pages: dashboard, products (search, filter, add/edit for owners, stock in/out), suppliers (list), history, reports
(restock list and stock value by category). Two clients, one backend is the point: business logic lives in the
backend, not in the screens.

## The Tkinter app

See `desktop_tk/README.md`. In short: pages call `ApiClient` methods; `run_async` keeps the window responsive;
the app holds a `Session` (user, businesses, open business); `theme.py` holds every colour.
The dashboard shows the five totals, a 7-day stock movement chart, a stock-value-by-category chart and the latest
movements; the Reports page has the same charts with period filters plus best sellers and CSV exports.

## Product and category rules (Phase 5)

- **Same-business rule:** a product's category and supplier must belong to the same business as the product.
  The API checks this on create and edit (400 otherwise). Looking anything up always uses
  `WHERE id = ... AND business_id = ...`, so another business's id simply gives 404.
- **Unique names:** category names and product SKUs are unique inside one business, ignoring upper/lower case
  (two businesses may both have a "Snacks" category). The database has a unique constraint as a second safety net.
- **Quantity is not editable.** `ProductIn` (used by edit) has no quantity field. Quantity changes only through
  stock movements (Phase 6). A new product may start with an *opening quantity*; it is saved together with a
  stock-in transaction ("Opening stock") in one database transaction, so the history is always complete.
- **Archive vs delete:** removing a product that has stock history archives it (hidden, history kept, can be
  restored). A product with no history (for example a typo) is really deleted.
- **Who may do what:** owner and staff can add/edit categories and products; only the owner can delete a
  category or archive/restore a product.
- **Search and filters** run in the database (`ILIKE` on name or SKU, category, stock level), not in the app.
  A product's low-stock level is its own `min_stock`, or the business default when that is empty.
