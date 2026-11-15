# StockPilot desktop app (Tkinter / CustomTkinter)

## Run it
```
pip install -r requirements.txt
python main.py
```
The backend must be running. By default the app talks to `http://127.0.0.1:8000`.
To use the deployed backend instead, set the address first:

- Windows (cmd):        `set STOCKPILOT_API_URL=https://your-project.vercel.app`
- Windows (PowerShell): `$env:STOCKPILOT_API_URL="https://your-project.vercel.app"`
- macOS / Linux:        `export STOCKPILOT_API_URL=https://your-project.vercel.app`

## How it is organised
| File / folder | Job |
|---|---|
| `main.py`, `app.py` | start-up; the window; swaps whole screens; handles logout and expired sessions |
| `config.py` | the backend address |
| `theme.py` | ALL colours and fonts (change the look in one place) |
| `icons.py` | icons drawn with Pillow (no image files, no emoji) |
| `api_client.py` | every request to the backend; turns failures into friendly `ApiError`s |
| `background.py` | runs requests in a thread so the window never freezes |
| `session.py` | who is logged in and which business is open |
| `pages/` | login, register, business picker, shell (sidebar + header), dashboard, products, stock, restock, suppliers, categories, history, reports, settings |
| `widgets/` | reusable pieces: buttons, banner, table, stat card, business form, product and supplier dialogs, `modal.py` (shared pop-up behaviour), `chart.py` (Matplotlib chart card), `export.py` (save-as for CSV) |

## How a screen talks to the backend
1. The user clicks a button, e.g. "Log in".
2. The page validates the form, disables the button and calls `run_async(...)`.
3. A background thread runs `api.login(...)` (an HTTPS request with `requests`) while the window stays responsive.
4. The result comes back to the main thread, which updates the screen (success) or shows the error banner (failure).
5. After login the JWT token is kept in memory (`ApiClient.token`) and sent with every later request.
   If the server answers 401 (token expired) the app returns to the login screen.
