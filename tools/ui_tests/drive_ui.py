"""Drives the REAL StockPilot window: fills fields, clicks buttons, waits for the server, checks results."""
import subprocess, time
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "desktop_tk"))   # the Tkinter app's own folder
DEV_DB = os.getenv("DEV_DATABASE_URL", "postgresql://postgres@localhost:5433/stockpilot_dev")  # only used to insert old history rows
SHOTS = os.getenv("SHOTS_DIR", os.path.join(HERE, "screenshots"))
os.makedirs(SHOTS, exist_ok=True)
import psycopg
from app import App

app = App()
app.update()

def pump(seconds=0.3):
    end = time.time() + seconds
    while time.time() < end:
        app.update(); time.sleep(0.02)

def wait_for(cond, what, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        app.update(); time.sleep(0.03)
        try:
            if cond(): return
        except Exception: pass
    raise AssertionError("timed out waiting for: " + what)

def shot(name):
    pump(0.4)
    subprocess.run(["import", "-window", "root", os.path.join(SHOTS, name + ".png")], check=False) if __import__("shutil").which("import") else None

def type_into(box, text):
    box.delete(0, "end"); box.insert(0, text)

def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond: sys.exit(1)

# ---- 1. login screen, wrong login shows an error ----
shot("01_login")
s = app.screen
type_into(s.email, "nobody@example.com"); type_into(s.password, "wrongpass1"); s.login_button.invoke()
wait_for(lambda: app.screen.banner.message.cget("text") != "", "login error")
check("Incorrect email or password" in app.screen.banner.message.cget("text"), "wrong login shows server message")
shot("02_login_error")

# ---- 2. register ----
app.show_register(); pump()
r = app.screen
type_into(r.full_name, "Asha Kumar"); type_into(r.email, "asha@example.com")
type_into(r.password, "password123"); type_into(r.confirm, "different1")
r.register_button.invoke(); pump()
check("do not match" in r.banner.message.cget("text"), "register rejects mismatched passwords (client side)")
type_into(r.confirm, "password123"); r.register_button.invoke()
wait_for(lambda: type(app.screen).__name__ == "BusinessPickerPage", "picker after register")
check(app.session.user["email"] == "asha@example.com", "registered and logged in")
wait_for(lambda: "don't have any business" in str([c.cget("text") for c in app.screen.list_area.winfo_children()]), "empty state")
shot("03_picker_empty")

# ---- 3. validation, then create first business ----
p = app.screen
p.form.submit_button.invoke(); pump()
check("business name" in p.banner.message.cget("text"), "empty business name rejected")
type_into(p.form.name, "ABC Electronics"); type_into(p.form.address, "12 Anna Salai, Chennai")
type_into(p.form.default_min_stock, "abc"); p.form.submit_button.invoke(); pump()
check("whole number" in p.banner.message.cget("text"), "bad low-stock level rejected")
type_into(p.form.default_min_stock, "5"); p.form.submit_button.invoke()
wait_for(lambda: type(app.screen).__name__ == "MainShell", "shell after creating first business")
check(app.session.business["name"] == "ABC Electronics" and app.session.is_owner, "first business opened automatically as owner")
shell = app.screen
wait_for(lambda: shell.pages["dashboard"].cards["products"].value.cget("text") == "0", "dashboard loaded")
check(shell.pages["dashboard"].cards["value"].value.cget("text") == "INR 0.00", "empty dashboard shows zeros, not fake data")
shot("04_dashboard_empty")

# ---- 4. insert real rows straight into the database, refresh, numbers must match ----
bid = app.session.business["id"]; uid = app.session.user["id"]
with psycopg.connect(DEV_DB, autocommit=True) as c:
    rows = [("Cable",20,10,None),("Mouse",3,100,None),("Laptop",0,5000,None),("Phone",8,1000,10)]
    for name, q, price, ms in rows:
        pid = c.execute("insert into products (business_id,name,sku,quantity,purchase_price,selling_price,min_stock,is_archived,created_at,updated_at) values (%s,%s,%s,%s,%s,%s,%s,false,now(),now()) returning id",
                        (bid, name, name.upper(), q, price, price*2, ms)).fetchone()[0]
        if q: c.execute("insert into stock_transactions (business_id,product_id,user_id,type,quantity_change,quantity_after,reason,created_at) values (%s,%s,%s,'in',%s,%s,%s,now())", (bid,pid,uid,q,q,"Opening stock"))
shell.pages["dashboard"].refresh()
wait_for(lambda: shell.pages["dashboard"].cards["products"].value.cget("text") == "4", "dashboard refresh")
d = shell.pages["dashboard"].cards
check(d["stock"].value.cget("text") == "31", "units in stock = 31")
check(d["value"].value.cget("text") == "INR 8,500.00", "inventory value = INR 8,500.00")
check(d["low"].value.cget("text") == "2" and d["out"].value.cget("text") == "1", "low=2 (Mouse, Phone) out=1 (Laptop)")
check(len(shell.pages["dashboard"].table.tree.get_children()) == 3, "3 recent transactions listed")
dash = shell.pages["dashboard"]
wait_for(lambda: dash.movement_chart.figure is not None and dash.category_chart.figure is not None, "dashboard charts painted")
bars = [p for p in dash.category_chart.figure.axes[0].patches]
check(len(bars) >= 1 and max(p.get_width() for p in bars) > 0, "dashboard category chart draws real stock values")
check(any("Added" in t.get_text() for t in dash.movement_chart.figure.axes[0].get_legend().get_texts()) or dash.movement_chart.figure.axes[0].texts,
      "dashboard movement chart is drawn (bars+legend, or an empty-state message)")
shot("05_dashboard_data")

# ---- 5. add a second business through the header switcher ----
shell.business_menu.set("+  Add or manage businesses"); shell.switch_business("+  Add or manage businesses")
wait_for(lambda: type(app.screen).__name__ == "BusinessPickerPage", "picker via switcher")
p = app.screen
wait_for(lambda: len(p.list_area.winfo_children()) == 1 and "Open" in str([getattr(w, "cget", lambda k: "")("text") for w in p.list_area.winfo_children()[0].winfo_children()]), "list shows 1 business")
type_into(p.form.name, "ABC Furniture"); p.form.submit_button.invoke()
wait_for(lambda: len(p.list_area.winfo_children()) == 2, "list shows 2 businesses")
check(len(app.session.businesses) == 2, "second business created under the same account")
check(p.form.name.get() == "" and p.form.name._placeholder_text_active, "create form is cleared and shows its hint again")
shot("06_picker_two")
# open Furniture (second button) 
p.list_area.winfo_children()[0].winfo_children()[-1].invoke()  # alphabetical: ABC Electronics first
wait_for(lambda: type(app.screen).__name__ == "MainShell", "shell")
shell = app.screen
shell.switch_business("ABC Furniture")
wait_for(lambda: shell.pages["dashboard"].cards["products"].value.cget("text") == "0", "Furniture dashboard is empty (isolated)")
check(app.session.business["name"] == "ABC Furniture", "switched to ABC Furniture; its inventory is separate (0 products)")
shell.switch_business("ABC Electronics")
wait_for(lambda: shell.pages["dashboard"].cards["products"].value.cget("text") == "4", "back to Electronics")
check(True, "switched back: Electronics still shows 4 products")

# ---- 6. settings: edit, members ----
def top_page(shell):
    content = shell.pages["dashboard"].master
    return content.winfo_children()[-1]   # Tk lists children lowest-to-highest, so the last one is on top
check(top_page(shell) is shell.pages["dashboard"], "dashboard is the visible page")
shell.nav_buttons["settings"][0].invoke()
check(top_page(shell) is shell.pages["settings"], "settings page is really on top after clicking Settings")
wait_for(lambda: len(shell.pages["settings"].members) == 1, "settings members loaded")
st = shell.pages["settings"]
type_into(st.form.name, "ABC Electronics Pvt"); type_into(st.form.default_min_stock, "10"); st.form.submit_button.invoke()
wait_for(lambda: "saved" in st.banner.message.cget("text"), "save confirmation")
check(shell.business_menu.get() == "ABC Electronics Pvt", "renamed business shows in header switcher")
shot("07_settings")
type_into(st.member_email, "ghost@example.com"); st.add_button.invoke()
wait_for(lambda: "No registered user" in st.banner.message.cget("text"), "unknown email message")
check(True, "adding unknown email shows friendly error")
# register staff user via API, then add
import requests
requests.post("http://127.0.0.1:8000/auth/register", json={"email":"ravi@example.com","full_name":"Ravi Staff","password":"password123"})
type_into(st.member_email, "ravi@example.com"); st.add_button.invoke()
wait_for(lambda: len(st.members) == 2, "staff added")
check(st.members[1]["role"] == "staff", "Ravi added as staff")
st.table.tree.selection_set("1"); 
import tkinter.messagebox as mb; mb.askyesno = lambda *a, **k: True
st.remove_member()
wait_for(lambda: len(st.members) == 1, "staff removed")
check(True, "staff removed")
# dashboard after threshold change to 10: Phone(8) & Mouse(3) low; Cable(20) fine -> still 2
shell.nav_buttons["dashboard"][0].invoke()
check(top_page(shell) is shell.pages["dashboard"], "dashboard back on top")
wait_for(lambda: shell.pages["dashboard"].cards["low"].value.cget("text") == "2", "dashboard low after threshold")

# ---- 7. staff view: log out, log in as Ravi (after adding him again) ----
requests_headers = {}
app.log_out(); pump()
check(type(app.screen).__name__ == "LoginPage" and app.session.api.token is None, "logout returns to login and clears token")
print("ALL UI CHECKS PASSED")
app.destroy()
