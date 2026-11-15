# UI test scripts (Tkinter app)

These scripts open the REAL Tkinter app, click real buttons and type into real boxes, talking to a REAL backend.
They are the "driver" tests used while building each phase.

1. Start PostgreSQL and the backend on port 8000 with a **throw-away development database**
   (`DATABASE_URL=... JWT_SECRET_KEY=... python -m uvicorn api.index:app --port 8000` from `backend/`).
2. EMPTY the database before each script (they create their own users). In `psql`:
   `truncate users, businesses restart identity cascade;`   (never do this on a database that has real data)
3. Run one script, e.g. `python tools/ui_tests/drive_products.py` (needs `desktop_tk/requirements.txt` installed, and
   `pip install psycopg[binary]` for the scripts that insert old history rows directly; set `DEV_DATABASE_URL` for that).

| Script | Covers |
|---|---|
| `drive_ui.py` | register, login, business creation, switching, owner/staff roles, dashboard numbers |
| `drive_products.py` | categories, product dialog validation, search/filters, archive/restore, dashboard after changes |
| `drive_stock.py` | suppliers, stock in/out/adjust, warnings, history filters (expects India time: `TZ=Asia/Kolkata`) |
| `drive_reports.py` | restock list, charts, period filters, CSV exports (expects India time) |

Each prints `PASS`/`FAIL` lines and `ALL ... PASSED` at the end. Screenshots go to `tools/ui_tests/screenshots/` when
ImageMagick's `import` command exists (Linux with a display); otherwise they are skipped.
The Java tests live in `desktop_swing/src/test/java` (see `desktop_swing/README.md`).
`seed_for_swing_tests.py` creates the users/businesses those Java tests expect.

Note: the Java tests change data (ApiSmokeTest adds stock), so empty the database and run `seed_for_swing_tests.py` again before each Java test class.
