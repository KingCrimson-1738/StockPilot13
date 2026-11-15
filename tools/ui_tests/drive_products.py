import time, subprocess, requests
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
h = {"Authorization": "Bearer " + owner["access_token"]}
biz = requests.post(f"{B}/businesses", json={"name": "ABC Electronics", "default_min_stock": 5}, headers=h).json()
requests.post(f"{B}/businesses/{biz['id']}/members", json={"email": "ravi@example.com"}, headers=h)

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
def keyrelease(ctk_entry):
    """Send a real key-release event to the Tk entry inside the CTkEntry (that is where the page's binding lives)."""
    inner = ctk_entry._entry
    inner.focus_force(); app.update()
    inner.event_generate("<KeyRelease>", when="now"); app.update()
dialogs = lambda: [w for w in app.winfo_children() if isinstance(w, ctk.CTkToplevel)]

def open_as(user, business):
    app.session.api.token = user["access_token"]; app.session.user = user["user"]
    app.session.businesses = requests.get(f"{B}/businesses", headers={"Authorization": "Bearer " + user["access_token"]}).json()
    app.open_business(next(b for b in app.session.businesses if b["id"] == business["id"]))
    return app.screen

shell = open_as(owner, biz); pump(0.5)
cats, prods = shell.pages["categories"], shell.pages["products"]
rows = lambda page: [page.table.tree.item(i, "values") for i in page.table.tree.get_children()]

# ---------- categories ----------
shell.nav_buttons["categories"][0].invoke()
wait_for(lambda: "No categories yet" in cats.table.empty_label.cget("text") and cats.table.empty_label.winfo_ismapped(), "categories empty state")
check(True, "new business has NO built-in categories (empty state shown)")
shot("10_categories_empty")
for name in ("Cables", "Phones", "Temp"):
    put(cats.name, name); cats.add(); wait_for(lambda n=name: any(r[0] == n for r in rows(cats)), f"category {name} listed")
check([r[0] for r in rows(cats)] == ["Cables", "Phones", "Temp"], "3 categories added through the UI")
put(cats.name, "cables"); cats.add(); wait_for(lambda: "already has a category" in cats.banner.message.cget("text"), "dup error")
check(True, "duplicate name (different case) shows the server's message")
cats.table.tree.selection_set("0"); pump(0.3)
check(cats.name.get() == "Cables", "selecting a row copies its name into the box")
put(cats.name, "Wires"); cats.rename(); wait_for(lambda: any(r[0] == "Wires" for r in rows(cats)), "rename")
check([r[0] for r in rows(cats)] == ["Phones", "Temp", "Wires"], "renamed Cables -> Wires (list re-sorted)")
cats.table.tree.selection_set(str([r[0] for r in rows(cats)].index("Temp"))); pump(0.2); cats.delete()
wait_for(lambda: "Temp" not in [r[0] for r in rows(cats)], "delete unused")
check(True, "unused category deleted")
# put the name back to Cables for the product tests
cats.table.tree.selection_set(str([r[0] for r in rows(cats)].index("Wires"))); pump(0.2); put(cats.name, "Cables"); cats.rename()
wait_for(lambda: "Cables" in [r[0] for r in rows(cats)], "rename back")

# ---------- products: dialog validation ----------
shell.nav_buttons["products"][0].invoke()
wait_for(lambda: prods.table.empty_label.winfo_ismapped() and "No products yet" in prods.table.empty_label.cget("text"), "products empty state")
check(True, "no products yet: empty state with a hint")
shot("11_products_empty")
prods.add_product(); wait_for(lambda: len(dialogs()) == 1, "dialog opens"); d = dialogs()[0]; pump(0.5)
shot("12_product_dialog")
d.save_button.invoke(); pump(0.2); check("product name" in d.banner.message.cget("text"), "dialog: empty name rejected")
put(d.name, "USB Cable"); d.save_button.invoke(); pump(0.2); check("SKU" in d.banner.message.cget("text"), "dialog: empty SKU rejected")
put(d.sku, "CBL-1"); put(d.purchase_price, "abc"); d.save_button.invoke(); pump(0.2); check("must be a number" in d.banner.message.cget("text"), "dialog: non-numeric price rejected")
put(d.purchase_price, "10.555"); d.save_button.invoke(); pump(0.2); check("2 decimal" in d.banner.message.cget("text"), "dialog: 3 decimal places rejected")
put(d.purchase_price, "-5"); d.save_button.invoke(); pump(0.2); check("negative" in d.banner.message.cget("text"), "dialog: negative price rejected")
put(d.purchase_price, "10"); put(d.selling_price, "15"); put(d.opening_quantity, "5x"); d.save_button.invoke(); pump(0.2)
check("whole number" in d.banner.message.cget("text"), "dialog: bad opening stock rejected")

# ---------- products: create four ----------
def create(name, sku, cat, buy, sell, qty, level=""):
    prods.add_product(); wait_for(lambda: len(dialogs()) == 1, "dialog"); dlg = dialogs()[0]; pump(0.2)
    put(dlg.name, name); put(dlg.sku, sku); dlg.category.set(cat); put(dlg.purchase_price, buy)
    put(dlg.selling_price, sell); put(dlg.opening_quantity, qty); put(dlg.min_stock, level)
    dlg.save_button.invoke()
    return dlg
d.destroy(); pump(0.3)
create("USB Cable", "CBL-1", "Cables", "10", "15", "50")
wait_for(lambda: len(rows(prods)) == 1 and not dialogs(), "first product saved, dialog closed")
check("was saved" in prods.banner.message.cget("text"), "success message after saving")
dup = create("Other", "cbl-1", "No category", "1", "2", "0")
wait_for(lambda: "SKU" in dup.banner.message.cget("text"), "dup sku"); check(len(dialogs()) == 1, "duplicate SKU: server message shown in the dialog, which stays open"); dup.destroy(); pump(0.2)
create("HDMI Cable", "CBL-2", "Cables", "100", "150", "3"); wait_for(lambda: len(rows(prods)) == 2, "2nd")
create("Phone X", "PH-X", "Phones", "1000", "1500", "8", "10"); wait_for(lambda: len(rows(prods)) == 3, "3rd")
create("Charger", "CHG-1", "No category", "50", "80", "0"); wait_for(lambda: len(rows(prods)) == 4, "4th")
pump(0.3); r = {x[1]: x for x in rows(prods)}
check(list(r) == ["Charger", "HDMI Cable", "Phone X", "USB Cable"], "list sorted by name")
check(r["HDMI Cable"][2] == "Cables" and r["HDMI Cable"][6] == "3" and r["HDMI Cable"][7] == "Low", "HDMI Cable: category, stock 3, status Low (default level 5)")
check(r["Phone X"][7] == "Low", "Phone X: status Low via its OWN alert level (8 <= 10)")
check(r["Charger"][7] == "Out" and r["USB Cable"][7] == "OK", "Charger Out, USB Cable OK")
check(prods.table.tree.item("0", "tags") != () , "low/out rows are colour-tagged")
shot("13_products_list")

# ---------- search and filters ----------
put(prods.search, "cable"); keyrelease(prods.search)
wait_for(lambda: len(rows(prods)) == 2, "search 'cable'"); check({x[1] for x in rows(prods)} == {"HDMI Cable", "USB Cable"}, "search 'cable' -> 2 products")
put(prods.search, "ph-x"); keyrelease(prods.search)
wait_for(lambda: len(rows(prods)) == 1, "search sku"); check(rows(prods)[0][1] == "Phone X", "search by SKU (case-insensitive)")
put(prods.search, "zzz"); keyrelease(prods.search)
wait_for(lambda: "match your search" in prods.table.empty_label.cget("text") and prods.table.empty_label.winfo_ismapped(), "no match msg")
check(True, "no match -> 'No products match your search' message")
put(prods.search, ""); keyrelease(prods.search); wait_for(lambda: len(rows(prods)) == 4, "cleared")
prods.category_menu.set("Phones"); prods.filters_changed("Phones"); wait_for(lambda: len(rows(prods)) == 1, "cat filter"); check(rows(prods)[0][1] == "Phone X", "category filter: Phones")
prods.category_menu.set("All categories"); prods.stock_menu.set("Low stock"); prods.filters_changed("")
wait_for(lambda: len(rows(prods)) == 2, "low filter"); check({x[1] for x in rows(prods)} == {"HDMI Cable", "Phone X"}, "stock filter: Low stock -> HDMI Cable, Phone X")
prods.stock_menu.set("Out of stock"); prods.filters_changed("")
wait_for(lambda: len(rows(prods)) == 1, "out filter"); check(rows(prods)[0][1] == "Charger", "stock filter: Out of stock -> Charger")
prods.stock_menu.set("All stock levels"); prods.filters_changed(""); wait_for(lambda: len(rows(prods)) == 4, "reset filters")

# ---------- edit ----------
idx = [x[1] for x in rows(prods)].index("Charger"); prods.table.tree.selection_set(str(idx)); pump(0.2)
prods.edit_selected(); wait_for(lambda: len(dialogs()) == 1, "edit dialog"); e = dialogs()[0]; pump(0.3)
check(e.name.get() == "Charger" and e.sku.get() == "CHG-1" and e.opening_quantity is None, "edit dialog is pre-filled; no opening-stock field")
put(e.selling_price, "95.50"); put(e.name, "Fast Charger"); e.category.set("Phones"); e.save_button.invoke()
wait_for(lambda: not dialogs() and any(x[1] == "Fast Charger" for x in rows(prods)), "edit saved")
fc = next(x for x in rows(prods) if x[1] == "Fast Charger")
check(fc[5] == "95.50" and fc[2] == "Phones" and fc[6] == "0", "edit saved: new name, price, category; stock untouched")
shot("14_edit_done")

# ---------- archive / delete / restore ----------
def select(name): prods.table.tree.selection_set(str([x[1] for x in rows(prods)].index(name))); pump(0.2)
select("Phone X"); prods.remove_selected(); wait_for(lambda: "archived" in prods.banner.message.cget("text"), "archived msg")
wait_for(lambda: len(rows(prods)) == 3, "archived hidden"); check("Phone X" not in [x[1] for x in rows(prods)], "product with history is ARCHIVED and hidden from the active list")
prods.status_menu.set("Archived products"); prods.filters_changed(""); wait_for(lambda: len(rows(prods)) == 1, "archived list")
check(rows(prods)[0][1] == "Phone X" and rows(prods)[0][7] == "Archived", "archived list shows Phone X with status Archived")
shot("15_archived_view")
select("Phone X"); prods.restore_selected(); wait_for(lambda: len(rows(prods)) == 0, "restored leaves archived list")
prods.status_menu.set("Active products"); prods.filters_changed(""); wait_for(lambda: len(rows(prods)) == 4, "back in active")
check("Phone X" in [x[1] for x in rows(prods)], "restored: Phone X is back in the active list")
select("Fast Charger"); prods.remove_selected(); wait_for(lambda: len(rows(prods)) == 3, "deleted")
check("deleted" in prods.banner.message.cget("text") and "Fast Charger" not in [x[1] for x in rows(prods)], "product WITHOUT history is really deleted")

# ---------- categories page counts + in-use delete; dashboard totals ----------
shell.nav_buttons["categories"][0].invoke()
wait_for(lambda: any(r[0] == "Cables" and r[1] == "2" for r in rows(cats)), "counts"); check({r[0]: r[1] for r in rows(cats)} == {"Cables": "2", "Phones": "1"}, "category list shows product counts")
cats.table.tree.selection_set("0"); pump(0.2); cats.delete(); wait_for(lambda: "still use" in cats.banner.message.cget("text"), "in-use msg")
check(True, "deleting a category that has products is refused with the server's message")
shot("16_categories")
shell.nav_buttons["dashboard"][0].invoke(); dash = shell.pages["dashboard"]
wait_for(lambda: dash.cards["products"].value.cget("text") == "3", "dashboard")
print("      dashboard shows:", dash.cards["stock"].value.cget("text"), "units,", dash.cards["value"].value.cget("text"))
check(dash.cards["stock"].value.cget("text") == "61" and dash.cards["value"].value.cget("text") == "INR 8,800.00", "dashboard: 61 units, INR 8,800.00 (50x10 + 3x100 + 8x1000 = 500 + 300 + 8000)")
check(dash.cards["low"].value.cget("text") == "2" and dash.cards["out"].value.cget("text") == "0", "dashboard: 2 low, 0 out")
check(len(dash.table.tree.get_children()) == 3, "opening stock appears as 3 'Stock in' movements")

# ---------- staff view ----------
app.log_out(); pump(0.3)
shell = open_as(staff, biz); pump(0.3); prods, cats = shell.pages["products"], shell.pages["categories"]
shell.nav_buttons["products"][0].invoke(); wait_for(lambda: len(rows(prods)) == 3, "staff sees products")
check(prods.remove_button.winfo_manager() == "" and prods.restore_button.winfo_manager() == "", "staff: archive/delete and restore buttons are hidden")
shell.nav_buttons["categories"][0].invoke(); wait_for(lambda: len(rows(cats)) == 2, "staff sees categories")
check(cats.delete_button.winfo_manager() == "", "staff: category delete button is hidden")
prods = shell.pages["products"]; shell.nav_buttons["products"][0].invoke(); pump(0.3)
create("Staff Item", "ST-1", "No category", "5", "9", "2"); wait_for(lambda: any(x[1] == "Staff Item" for x in rows(prods)), "staff creates")
check(True, "staff can add products")
print("ALL PRODUCT/CATEGORY UI CHECKS PASSED"); app.destroy()
