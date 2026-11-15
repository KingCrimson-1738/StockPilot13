# Deploying StockPilot (Neon database + Vercel backend)

The desktop apps (Tkinter and Swing) are never "deployed": each user runs them on their own computer and points them
at the backend's web address. Only the **backend** and the **database** live online.

```
 Tkinter app ─┐                         ┌─ Vercel (FastAPI, api/index.py) ─── Neon PostgreSQL
              ├── HTTPS + JWT ─────────►│
 Swing app  ──┘                         └─ business rules + security live here
```

You need free accounts at **GitHub**, **Neon** (neon.com) and **Vercel** (vercel.com). About 20 minutes.

## 1. Create the database on Neon
1. New project -> pick the region nearest your users (e.g. Mumbai/Singapore) -> create.
2. Click **Connect**. Copy TWO connection strings:
   - **Pooled** (host contains `-pooler`, the "Connection pooling" toggle ON). The app uses this one.
   - **Direct** (toggle OFF, no `-pooler`). Only the migration command uses this one.
3. Treat both like passwords: never paste them into code, chat or GitHub.

## 2. Create the tables (migration) from your own computer
Neon starts empty. Alembic creates the tables; running it again later only applies *new* changes and never deletes data
(the automated test `test_running_migrations_again_keeps_existing_data` proves this).

```
cd backend
pip install -r requirements.txt
```
Windows (PowerShell):
```
$env:DATABASE_URL = "PASTE-THE-POOLED-STRING"
$env:DIRECT_URL   = "PASTE-THE-DIRECT-STRING"
$env:JWT_SECRET_KEY = "anything-at-least-32-characters-long-for-this-step"
alembic upgrade head
```
Mac/Linux: use `export NAME="value"` instead of `$env:NAME = "value"`.
You should see `Running upgrade -> ...`. In Neon's **Tables** view you now see `users`, `businesses`, `products`, ...

## 3. Put the code on GitHub
Push the whole `stockpilot` folder to a **private** repository. Check that no `.env` file is included
(`.gitignore` already excludes it). Only `.env.example` (placeholders) should be there.

## 4. Deploy the backend on Vercel
1. Vercel -> **Add New -> Project** -> import the GitHub repository.
2. **Root Directory: `backend`** (important: `vercel.json`, `requirements.txt` and `api/index.py` live there).
   Framework preset: leave as detected (FastAPI/Other).
3. **Environment Variables** (Production), add exactly these:

   | Name | Value |
   |---|---|
   | `DATABASE_URL` | the **pooled** Neon string |
   | `JWT_SECRET_KEY` | a NEW random secret: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `TOKEN_EXPIRY` | `60` (minutes a login stays valid) |

   Use a different `JWT_SECRET_KEY` from any you used while testing. Changing it later logs everyone out (that is fine).
4. **Deploy**. You get an address like `https://stockpilot-xyz.vercel.app`.

How it works: Vercel finds `app` in `backend/api/index.py` and runs it as a serverless function; `vercel.json` sends every
URL to it. `requirements.txt` (pinned versions) is what Vercel installs.

## 5. Verify the deployment
```
python tools/check_deployment.py https://stockpilot-xyz.vercel.app
```
Expect `ALL CHECKS PASSED`. It also leaves a tiny bit of test data (users named `deploycheck-...`), which is harmless.
You can also open `https://stockpilot-xyz.vercel.app/health` in a browser: `{"status":"ok","database":"ok"}`.

## 6. Point the apps at the deployed backend
**Tkinter** (any one of these):
- Windows PowerShell: `$env:STOCKPILOT_API_URL = "https://stockpilot-xyz.vercel.app"` then `python main.py`
- or create a file `desktop_tk/server.txt` containing just the address (see `server.txt.example`)

**Swing:** same environment variable `STOCKPILOT_API_URL`, then `java -jar target/stockpilot-swing-1.0-all.jar`.

The login screen prints `Server: <address>` so you can always see what you are connected to. If the address is plain
`http://` (not localhost) a yellow warning appears, because the password would travel unencrypted. Vercel always gives HTTPS.

## Troubleshooting
| What you see | Likely cause and fix |
|---|---|
| `/health` -> 503 "database is not reachable" | Wrong `DATABASE_URL` on Vercel (re-paste, no quotes/spaces), or typo in the password. Check Vercel -> Logs. |
| Any URL -> 500 and the log says `DATABASE_URL is not set` or `JWT_SECRET_KEY ... too short` | Missing/short environment variable. Add it, then **Redeploy** (variables apply only to new deployments). |
| `relation "users" does not exist` | You skipped step 2 (migration), or ran it against a different database. |
| Apps say "Cannot reach the server" | Wrong address/typo, or no internet. Open the address + `/health` in a browser. |
| First request after a quiet period is slow (several seconds) | Normal: the serverless function and the Neon database wake up. The apps wait up to 30 s. |
| Every request -> 401 after some time | The login expired (`TOKEN_EXPIRY`). Log in again; the apps do this automatically on 401. |
| Build fails on Vercel | Root Directory is not `backend`, or a package version could not be installed (see build log). |

## Updating later
- Code change: push to GitHub; Vercel redeploys by itself.
- Database change (new column/table): write a new Alembic migration (`alembic revision --autogenerate -m "..."`), then run
  `alembic upgrade head` against Neon (step 2) **before or right after** deploying. Existing data stays.

## Security checklist (say these in the viva)
- Secrets (`DATABASE_URL`, `JWT_SECRET_KEY`) exist only as environment variables on Vercel; none are in the code or GitHub.
- Passwords are stored as bcrypt hashes; tokens are signed JWTs that expire.
- Every business route checks a membership row, so one business can never read another's data (404, not 403).
- All traffic is HTTPS on Vercel and Neon (`sslmode=require`).
- The app never shows raw database errors to users (`/health` returns a generic 503).
- No CORS setup is needed: desktop apps are not browsers. (If you ever build a web front end, add CORS then.)
- Known gaps for a mini project: no login rate limiting / lockout, no password reset, no email verification.

## What was and was not tested here
Tested locally against a real PostgreSQL 16: migrations (fresh database, repeated, no data loss), the health check, URL
handling for Neon-style connection strings, installing the pinned `requirements.txt` in a clean environment and booting
through `api/index.py`, and the full `tools/check_deployment.py` run. **Not tested:** the real Vercel and Neon services
(the build sandbox cannot reach them), so step 4 and Neon's SSL/pooler behaviour are verified only by following the
vendors' documentation. If something differs, `check_deployment.py` and the table above are the quickest way to find out.
