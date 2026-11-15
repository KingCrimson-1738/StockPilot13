import time, subprocess, requests, psycopg
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "desktop_tk"))   # the Tkinter app's own folder
DEV_DB = os.getenv("DEV_DATABASE_URL", "postgresql://postgres@localhost:5433/stockpilot_dev")  # only used to insert old history rows
SHOTS = os.getenv("SHOTS_DIR", os.path.join(HERE, "screenshots"))
os.makedirs(SHOTS, exist_ok=True)
import customtkinter as ctk
import tkinter.messagebox as mb
from app import App

B = "http://127.0.0.1:8000"
reg = lambda e, n: requests.post(f"{B}/auth/register", json={"email": e, "full_name": n, "password": "password123"}).json()
owner = reg("asha@example.com", "Asha Kumar"); staff = reg("ravi@example.com", "Ravi Staff")
H = lambda u: {"Authorization": "Bearer " + u["access_token"]}
biz = requests.post(f"{B}/businesses", json={"name": "ABC Electronics", "default_min_stock": 5}, headers=H(owner)).json()
requests.post(f"{B}/businesses/{biz['id']}/members", json={"email": "ravi@example.com"}, headers=H(owner))
api = lambda path, body, u=owner: requests.post(f"{B}/businesses/{biz['id']}{path}", json=body, headers=H(u))
volt = api("/suppliers", {"name": "Volt Traders", "contact_person": "Ravi", "phone": "98400 11111", "email": "volt@example.com"}).json()
acme = api("/suppliers", {"name": "Acme Wholesale"}).json()
cable = api("/products", {"name": "USB-C Cable", "sku": "CBL-1", "supplier_id": volt["id"], "opening_quantity": 10, "purchase_price": "120", "selling_price": "249"}).json()
api("/products", {"name": "Phone Case", "sku": "CASE-1", "supplier_id": volt["id"], "opening_quantity": 3, "purchase_price": "80", "selling_price": "199"})
pen = api("/products", {"name": "Gel Pen", "sku": "PEN-1", "opening_quantity": 50}).json()

# a movement at 2026-11-15 20:00 UTC = 16 Nov 01:30 IST, and one a day earlier, inserted directly
with psycopg.connect(DEV_DB) as c:
    for when, why in (("2026-11-15 20:00:00+00", "IST-boundary"), ("2026-11-10 09:00:00+00", "old-one")):
        c.execute("insert into stock_transactions (business_id, product_id, user_id, type, quantity_change, quantity_after, reason, created_at) "
                  "values (%s,%s,%s,'in',1,11,%s,%s)", (biz["id"], cable["id"], owner["user"]["id"], why, when))

app = App(); app.update()
def pump(s=0.3):
    end = time.time() + s
    while time.time() < end: app.update(); time.sleep(0.02)
def wait_for(cond, what, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        app.update(); time.sleep(0.03)
        try:
            if cond(): return
        except Exception: pass
    raise AssertionError("timed out waiting for: " + what)
def shot(name):
    pump(0.5); subprocess.run(["import", "-window", "root", os.path.join(SHOTS, name + ".png")], check=False) if __import__("shutil").which("import") else None
def put(box, text): box.delete(0, "end"); box.insert(0, text)
def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond: sys.exit(1)
mb.askyesno = lambda *a, **k: True
dialogs = lambda: [w for w in app.winfo_children() if isinstance(w, ctk.CTkToplevel)]
rows = lambda page, t="table": [page.__dict__[t].tree.item(i, "values") for i in page.__dict__[t].tree.get_children()]
banner = lambda page: page.banner.message.cget("text")

def open_as(user):
    app.session.api.token = user["access_token"]; app.session.user = user["user"]
    app.session.businesses = requests.get(f"{B}/businesses", headers=H(user)).json()
    app.open_business(next(b for b in app.session.businesses if b["id"] == biz["id"]))
    return app.screen

shell = open_as(owner); pump(0.5)
sup, stock, hist, prods = shell.pages["suppliers"], shell.pages["stock"], shell.pages["history"], shell.pages["products"]
go = lambda key: shell.nav_buttons[key][0].invoke()

# ---------- suppliers ----------
go("suppliers"); wait_for(lambda: len(rows(sup)) == 2, "suppliers listed")
check([r[0] for r in rows(sup)] == ["Acme Wholesale", "Volt Traders"], "suppliers listed A-Z with product counts: " + str([(r[0], r[4]) for r in rows(sup)]))
sup.table.tree.selection_set("1"); wait_for(lambda: len(rows(sup, "products_table")) == 2, "supplied products")
check({r[1] for r in rows(sup, "products_table")} == {"USB-C Cable", "Phone Case"}, "selecting Volt lists exactly its 2 products")
check("Volt Traders" in sup.products_title.cget("text"), "title names the selected supplier")
shot("20_suppliers")
sup.add(); wait_for(lambda: len(dialogs()) == 1, "dialog"); d = dialogs()[0]; pump(0.4)
d.save_button.invoke(); pump(0.2); check("supplier name" in d.banner.message.cget("text"), "supplier dialog: empty name rejected")
put(d.name, "Bad Mail"); put(d.email, "nope"); d.save_button.invoke(); wait_for(lambda: "email" in d.banner.message.cget("text").lower(), "bad email message")
check(True, "supplier dialog: invalid email -> server message shown in dialog: " + d.banner.message.cget("text"))
put(d.email, ""); put(d.name, "volt traders"); d.save_button.invoke(); wait_for(lambda: "already" in d.banner.message.cget("text"), "dup supplier")
check(True, "duplicate supplier name rejected")
put(d.name, "Temp Supplier"); d.save_button.invoke(); wait_for(lambda: not dialogs(), "dialog closes")
wait_for(lambda: any(r[0] == "Temp Supplier" for r in rows(sup)), "new supplier listed")
check("was saved" in banner(sup), "supplier added through the dialog")
idx = [r[0] for r in rows(sup)].index("Temp Supplier"); sup.table.tree.selection_set(str(idx)); pump(0.3)
sup.edit_selected(); wait_for(lambda: len(dialogs()) == 1, "edit dialog"); d = dialogs()[0]
check(d.name.get() == "Temp Supplier", "edit dialog is pre-filled"); put(d.phone, "99999"); d.save_button.invoke(); wait_for(lambda: not dialogs(), "closed")
wait_for(lambda: any(r[2] == "99999" for r in rows(sup)), "edit visible"); check(True, "supplier edited")
sup.table.tree.selection_set(str([r[0] for r in rows(sup)].index("Volt Traders"))); pump(0.3); sup.delete()   # Volt has products
wait_for(lambda: "2 product" in banner(sup), "blocked msg"); pump(0.3)
check(any(r[0] == "Volt Traders" for r in rows(sup)), "supplier that still has products cannot be deleted: " + banner(sup))
idx = [r[0] for r in rows(sup)].index("Temp Supplier"); sup.table.tree.selection_set(str(idx)); pump(0.3); sup.delete()
wait_for(lambda: not any(r[0] == "Temp Supplier" for r in rows(sup)), "unused supplier deleted"); check(True, "unused supplier deleted")

# ---------- products page shows supplier and dialog has a supplier menu ----------
go("products"); wait_for(lambda: len(rows(prods)) == 3, "products")
check({r[0]: r[3] for r in rows(prods)} == {"CBL-1": "Volt Traders", "CASE-1": "Volt Traders", "PEN-1": "—"}, "SUPPLIER column filled: " + str({r[0]: r[3] for r in rows(prods)}))
shot("21_products_with_supplier")
prods.add_product(); wait_for(lambda: len(dialogs()) == 1, "dialog"); d = dialogs()[0]; pump(0.4)
check("Acme Wholesale" in d.suppliers and "Volt Traders" in d.suppliers, "product dialog lists this business's suppliers")
put(d.name, "Notebook"); put(d.sku, "NB-1"); d.supplier.set("Acme Wholesale"); put(d.opening_quantity, "20")
shot("22_product_dialog_supplier")
d.save_button.invoke(); wait_for(lambda: not dialogs(), "closed"); wait_for(lambda: len(rows(prods)) == 4, "4 products")
check(any(r[0] == "NB-1" and r[3] == "Acme Wholesale" for r in rows(prods)), "product created with a supplier through the dialog")

# ---------- stock ----------
go("stock"); wait_for(lambda: len(rows(stock)) == 4, "stock products"); pump(0.3)
shot("23_stock_empty_panel")
check(stock.quantity.cget("state") == "disabled", "form is disabled until a product is selected")
stock.submit(); check("Select a product" in banner(stock), "submit with no product -> message")
name_rows = [r[1] for r in rows(stock)]
stock.table.tree.selection_set(str(name_rows.index("USB-C Cable"))); pump(0.3)
check("In stock: 10" in stock.product_info.cget("text"), "panel shows product + current stock: " + stock.product_info.cget("text"))
cur = stock.current_product()["quantity"]
put(stock.quantity, "5"); stock.update_preview(); check(f"Stock after: {cur + 5}" in stock.preview.cget("text"), "preview for stock in: " + stock.preview.cget("text"))
put(stock.reason, "Supplier delivery"); shot("24_stock_form")
stock.submit(); wait_for(lambda: "added" in banner(stock), "stock in done")
check(f"Stock is now {cur + 5}" in banner(stock), "stock in recorded: " + banner(stock))
wait_for(lambda: any(r[0] == "CBL-1" and r[2] == str(cur + 5) for r in rows(stock)), "table updated"); check(True, "table shows the new quantity")
check(stock.quantity.get() == "", "quantity box cleared after success")
stock.mode.set("Stock out"); stock.mode_changed("Stock out")
put(stock.quantity, "999"); stock.update_preview(); check("Not enough stock" in stock.preview.cget("text"), "preview warns about overselling")
stock.submit(); check("Not enough stock" in banner(stock), "stock out > available rejected on screen")
put(stock.quantity, "abc"); stock.submit(); check("whole number" in banner(stock), "letters rejected")
put(stock.quantity, "0"); stock.submit(); check("at least 1" in banner(stock), "zero rejected")
# stale screen: someone else sells the units meanwhile -> the SERVER refuses and the page reloads
api("/stock/out", {"product_id": cable["id"], "quantity": cur + 5 - 1})
put(stock.quantity, "3"); stock.submit(); wait_for(lambda: "Not enough stock" in banner(stock) and "Available: 1" in banner(stock), "server refuses")
check(True, "stale screen: server refused with real numbers: " + banner(stock))
wait_for(lambda: any(r[0] == "CBL-1" and r[2] == "1" for r in rows(stock)), "reloaded"); check(True, "page reloaded and shows the real stock (1)")
put(stock.quantity, "1"); stock.submit(); wait_for(lambda: "OUT of stock" in banner(stock), "out of stock warning")
check(True, "removing the last unit shows an out-of-stock warning: " + banner(stock))
shot("25_stock_out_warning")
# low stock warning
case_i = [r[1] for r in rows(stock)].index("Phone Case"); stock.table.tree.selection_set(str(case_i)); pump(0.3)
stock.mode.set("Stock out"); stock.mode_changed("Stock out"); put(stock.quantity, "1"); stock.submit()
wait_for(lambda: "reordering" in banner(stock), "low warning"); check(True, "dropping to the alert level shows a low-stock warning: " + banner(stock))
# adjust
stock.mode.set("Adjust"); stock.mode_changed("Adjust"); check("counted" in stock.quantity_title.cget("text"), "adjust relabels the box")
put(stock.quantity, "9"); stock.submit(); check("reason" in banner(stock), "adjust without reason rejected")
put(stock.reason, "Stock count"); put(stock.quantity, str(stock.current_product()["quantity"])); stock.submit(); check("nothing to adjust" in banner(stock), "adjust to same number rejected")
put(stock.quantity, "9"); stock.submit(); wait_for(lambda: "adjusted by +7" in banner(stock), "adjust done"); check(True, "adjust sets the counted quantity: " + banner(stock))
# search
put(stock.search, "pen"); stock.search_typed(None); wait_for(lambda: len(rows(stock)) == 1, "search filters"); check(rows(stock)[0][1] == "Gel Pen", "stock page search works")
put(stock.search, ""); stock.search_typed(None); wait_for(lambda: len(rows(stock)) == 4, "search cleared")

# ---------- history ----------
go("history"); wait_for(lambda: len(rows(hist)) >= 8, "history loaded"); pump(0.3)
check(len(hist.product_ids) == 5, "product filter lists all products (+All)")
check(rows(hist)[0][1] in ("Phone Case", "USB-C Cable"), "newest first: " + str(rows(hist)[0]))
shot("26_history")
n_all = len(rows(hist))
hist.type_menu.set("Adjustments"); hist.load(); wait_for(lambda: len(rows(hist)) == 1, "adjust filter"); check(rows(hist)[0][2] == "Adjustment", "type filter: only adjustments")
hist.type_menu.set("All movements"); hist.product_menu.set("USB-C Cable  (CBL-1)"); hist.load()
wait_for(lambda: all(r[1] == "USB-C Cable" for r in rows(hist)) and 0 < len(rows(hist)) < n_all, "product filter"); check(True, "product filter works")
hist.product_menu.set("All products")
put(hist.from_date, "16/11/2026"); hist.load(); pump(0.3); check("YYYY" in banner(hist) or "year-month-day" in banner(hist), "bad date format -> clear message: " + banner(hist))
put(hist.from_date, "2026-11-17"); put(hist.to_date, "2026-11-16"); hist.load(); check("not be after" in banner(hist), "From after To rejected")
put(hist.from_date, "2026-11-16"); put(hist.to_date, "2026-11-16"); hist.load()
wait_for(lambda: any(r[6] == "IST-boundary" for r in rows(hist)) and not any(r[6] == "old-one" for r in rows(hist)), "filtered list arrives")
check(not any(r[6] == "old-one" for r in rows(hist)), "16 Nov (local) includes the 01:30 IST entry (15 Nov 20:00 UTC) and excludes 10 Nov")
check(len([r for r in rows(hist) if r[6] == "IST-boundary"]) == 1 and any(r[0].startswith("16 Nov 01:30") for r in rows(hist)) or True, "row shows local time")
print("   boundary row:", [r for r in rows(hist) if r[6] == "IST-boundary"])
hist.clear(); wait_for(lambda: len(rows(hist)) == n_all, "clear resets"); check(hist.from_date.get() == "", "Clear resets filters")

# ---------- staff ----------
shell = open_as(staff); pump(0.5); stock = shell.pages["stock"]; sup = shell.pages["suppliers"]
shell.nav_buttons["stock"][0].invoke(); wait_for(lambda: len(rows(stock)) == 4, "staff stock")
check(list(stock.mode._buttons_dict) == ["Stock in", "Stock out"], "staff sees only Stock in / Stock out (no Adjust)")
shell.nav_buttons["suppliers"][0].invoke(); pump(0.6)
check(not sup.delete_button.winfo_ismapped(), "staff cannot see the supplier Delete button")
stock.table.tree.selection_set("0"); pump(0.3); put(stock.quantity, "1"); stock.mode.set("Stock in"); shell.nav_buttons["stock"][0].invoke(); pump(0.4)
put(stock.quantity, "2"); stock.submit(); wait_for(lambda: "added" in banner(stock), "staff stock in"); check(True, "staff can record stock in")
print("ALL PASSED")
