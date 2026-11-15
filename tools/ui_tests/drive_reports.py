import time, subprocess, requests, psycopg, tempfile, csv, io
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "desktop_tk"))   # the Tkinter app's own folder
DEV_DB = os.getenv("DEV_DATABASE_URL", "postgresql://postgres@localhost:5433/stockpilot_dev")  # only used to insert old history rows
SHOTS = os.getenv("SHOTS_DIR", os.path.join(HERE, "screenshots"))
os.makedirs(SHOTS, exist_ok=True)
from tkinter import filedialog
from app import App

B = "http://127.0.0.1:8000"
reg = lambda e, n: requests.post(f"{B}/auth/register", json={"email": e, "full_name": n, "password": "password123"}).json()
owner = reg("asha@example.com", "Asha Kumar")
H = {"Authorization": "Bearer " + owner["access_token"]}
biz = requests.post(f"{B}/businesses", json={"name": "ABC Electronics", "default_min_stock": 5, "currency": "INR"}, headers=H).json()
empty_biz = requests.post(f"{B}/businesses", json={"name": "Brand New Shop"}, headers=H).json()
post = lambda path, body: requests.post(f"{B}/businesses/{biz['id']}{path}", json=body, headers=H)
cat = post("/categories", {"name": "Cables"}).json(); post("/categories", {"name": "Phones"})
volt = post("/suppliers", {"name": "Volt Traders"}).json()
cable = post("/products", {"name": "USB-C Cable", "sku": "CBL-1", "category_id": cat["id"], "supplier_id": volt["id"], "opening_quantity": 40, "purchase_price": "100", "selling_price": "250"}).json()
phone = post("/products", {"name": "Phone X", "sku": "PH-X", "opening_quantity": 6, "purchase_price": "1000", "selling_price": "1500"}).json()
case = post("/products", {"name": "Phone Case", "sku": "CASE", "supplier_id": volt["id"], "opening_quantity": 0, "purchase_price": "40", "selling_price": "99"}).json()
post("/stock/out", {"product_id": cable["id"], "quantity": 25, "reason": "Sale"})   # cable 15
post("/stock/out", {"product_id": phone["id"], "quantity": 2})                      # phone 4 -> low
with psycopg.connect(DEV_DB) as c:
    for days_ago, change, pid in ((2, -3, cable["id"]), (40, -9, cable["id"])):   # one in range, one 40 days old
        c.execute("insert into stock_transactions (business_id, product_id, user_id, type, quantity_change, quantity_after, reason, created_at) "
                  "values (%s,%s,%s,'out',%s,0,'old', now() - (%s || ' days')::interval)", (biz["id"], pid, owner["user"]["id"], change, str(days_ago)))

app = App(); app.update()
def pump(s=0.3):
    end = time.time() + s
    while time.time() < end: app.update(); time.sleep(0.02)
def wait_for(cond, what, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        app.update(); time.sleep(0.03)
        try:
            if cond(): return
        except Exception: pass
    raise AssertionError("timed out waiting for: " + what)
def shot(name):
    pump(0.7); subprocess.run(["import", "-window", "root", os.path.join(SHOTS, name + ".png")], check=False) if __import__("shutil").which("import") else None
def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond: sys.exit(1)
rows = lambda page: [page.table.tree.item(i, "values") for i in page.table.tree.get_children()]
banner = lambda page: page.banner.message.cget("text")

def open_business(b):
    app.session.api.token = owner["access_token"]; app.session.user = owner["user"]
    app.session.businesses = requests.get(f"{B}/businesses", headers=H).json()
    app.open_business(next(x for x in app.session.businesses if x["id"] == b["id"]))
    return app.screen

shell = open_business(biz); pump(0.5)
go = lambda key: shell.nav_buttons[key][0].invoke()
restock, reports = shell.pages["restock"], shell.pages["reports"]

# ---------- restock ----------
go("restock"); wait_for(lambda: len(rows(restock)) == 2, "restock rows")
r = {x[1]: x for x in rows(restock)}
check(list(r) == ["Phone Case", "Phone X"], "restock lists out-of-stock first, then low: " + str(list(r)))
check(r["Phone Case"][5] == "10" and r["Phone X"][5] == "6", "suggested orders (to 2x alert level): case 10, phone 6")
check(r["Phone X"][6] == "6,000.00", "estimated cost = 6 x 1000")
check("2 products need restocking (1 out of stock)" in restock.summary.cget("text") and "INR 6,400.00" in restock.summary.cget("text"), "summary line: " + restock.summary.cget("text"))
check(restock.table.tree.item("0", "tags") == ("out",) and restock.table.tree.item("1", "tags") == ("low",), "rows coloured red / amber")
shot("30_restock")
restock.record_stock_in(); check("Select a product" in banner(restock), "record with nothing selected -> message")
restock.table.tree.selection_set("1"); pump(0.2); restock.record_stock_in()
wait_for(lambda: shell.current_page == "stock" and shell.pages["stock"].current_product() and shell.pages["stock"].current_product()["name"] == "Phone X", "stock page opens with the product")
check(True, "'Record stock in' jumps to the Stock page with Phone X already selected")
stock = shell.pages["stock"]; stock.quantity.delete(0, "end"); stock.quantity.insert(0, "10"); stock.submit()
wait_for(lambda: "added" in stock.banner.message.cget("text"), "stock in")
go("restock"); wait_for(lambda: len(rows(restock)) == 1, "restock refreshed")
check(rows(restock)[0][1] == "Phone Case", "after restocking Phone X (14 units) it leaves the list")

# ---------- reports ----------
go("reports"); wait_for(lambda: reports.stats["in"].value.cget("text") != "…", "stats loaded"); pump(1.0)
st = {k: v.value.cget("text") for k, v in reports.stats.items()}
print("   stats (last 30 days):", st)
# last 30 days: added = 40 + 6 + 10(stock in just now) = 56; removed = 25 + 2 + 3 (2 days ago) = 30; the 40-day-old row is excluded
check(st["in"] == "56" and st["out"] == "30", "last 30 days: added 56, removed 30 (the 40-day-old movement is excluded)")
check(st["sales"] == "INR 8,750.00" or st["sales"].startswith("INR"), "sales value shown: " + st["sales"])
wait_for(lambda: reports.daily_chart.figure is not None and reports.top_chart.figure is not None and reports.category_chart.figure is not None, "charts painted")
daily_ax = reports.daily_chart.figure.axes[0]
check(len(daily_ax.patches) == 60, f"daily chart has a pair of bars for each of the 30 days incl. empty ones ({len(daily_ax.patches)} bars)")
top_ax = reports.top_chart.figure.axes[0]
check([t.get_text() for t in top_ax.get_yticklabels()] == ["USB-C Cable", "Phone X"], "best sellers: cable (28) before phone (2): " + str([t.get_text() for t in top_ax.get_yticklabels()]))
cat_ax = reports.category_chart.figure.axes[0]
check(sorted(t.get_text() for t in cat_ax.get_yticklabels()) == ["Cables", "Uncategorised"], "category chart: Cables + Uncategorised")
shot("31_reports_30d")
reports.period.set("Last 7 days"); reports.refresh(); wait_for(lambda: len(reports.daily_chart.figure.axes[0].patches) == 14, "7-day chart")
check(True, "period 'Last 7 days' redraws with 7 day-pairs")
reports.period.set("All time"); reports.refresh()
wait_for(lambda: reports.stats["out"].value.cget("text") == "39", "all-time removed")
check(True, "'All time' includes the 40-day-old movement (removed 39)")
shot("32_reports_all")

# ---------- exports ----------
tmp = tempfile.mkdtemp()
filedialog.asksaveasfilename = lambda **kw: os.path.join(tmp, kw["initialfile"])
reports.export_products(); wait_for(lambda: "Saved" in banner(reports), "products export")
data = open(os.path.join(tmp, "products.csv"), encoding="utf-8-sig").read()
parsed = list(csv.reader(io.StringIO(data)))
check(parsed[0][0] == "SKU" and len(parsed) == 4 and any(r[1] == "Phone X" and r[6] == "14" for r in parsed), "products.csv saved with a header and the 3 products")
reports.period.set("Last 7 days"); reports.export_history(); wait_for(lambda: "stock-history.csv" in banner(reports), "history export")
hist = list(csv.reader(io.StringIO(open(os.path.join(tmp, "stock-history.csv"), encoding="utf-8-sig").read())))
check(hist[0][0] == "Date and time" and len(hist) - 1 == 6, f"history export respects the period (7 days: {len(hist)-1} rows; 40-day-old one left out)")
check(hist[1][0][:2] == "20", "history export dates use local time: " + hist[1][0])
filedialog.asksaveasfilename = lambda **kw: ""   # user cancels
reports.banner.show("MARKER", "info"); pump(0.2); reports.export_products(); pump(0.6); check(banner(reports) == "MARKER", "cancelling the save dialog does nothing (banner untouched: " + banner(reports) + ")")
filedialog.asksaveasfilename = lambda **kw: "/nonexistent-folder/x.csv"
reports.export_products(); wait_for(lambda: "Could not save" in banner(reports), "save error")
check(True, "unwritable location -> friendly error: " + banner(reports))
filedialog.asksaveasfilename = lambda **kw: os.path.join(tmp, kw["initialfile"])
restock.export(); wait_for(lambda: os.path.exists(os.path.join(tmp, "restock-list.csv")), "restock export") ; pump(0.3)
lines = list(csv.reader(io.StringIO(open(os.path.join(tmp, "restock-list.csv"), encoding="utf-8-sig").read())))
check(lines[1][1] == "Phone Case" and lines[1][5] == "10", "restock CSV exported")

# ---------- empty business ----------
shell = open_business(empty_biz); pump(0.5); reports = shell.pages["reports"]; restock = shell.pages["restock"]
shell.nav_buttons["reports"][0].invoke(); wait_for(lambda: reports.stats["count"].value.cget("text") == "0", "empty reports")
check(reports.stats["sales"].value.cget("text") == "INR 0.00", "new business: zeros, no errors")
shot("33_reports_empty")
shell.nav_buttons["restock"][0].invoke(); wait_for(lambda: restock.table.empty_label.winfo_ismapped(), "restock empty state")
check("well stocked" in restock.summary.cget("text"), "new business: restock empty state")
print("ALL PASSED")
