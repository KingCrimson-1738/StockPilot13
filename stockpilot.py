import sqlite3
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

db = sqlite3.connect(Path(__file__).with_name("stock.db"))
db.executescript("""
create table if not exists products (
    id integer primary key,
    sku text not null unique,
    name text not null,
    price real not null check (price >= 0),
    quantity integer not null default 0 check (quantity >= 0),
    min_stock integer not null default 5
);
create table if not exists moves (
    id integer primary key,
    product_id integer not null references products(id),
    change integer not null,
    quantity_after integer not null,
    at text not null
);
""")


def add_product(sku, name, price, quantity, min_stock):
    if not sku or not name:
        raise ValueError("SKU and name are required.")
    try:
        price, quantity, min_stock = float(price), int(quantity), int(min_stock)
    except ValueError:
        raise ValueError("Price, quantity and alert level must be numbers.")
    if price < 0 or quantity < 0 or min_stock < 0:
        raise ValueError("Numbers cannot be negative.")
    try:
        with db:
            cursor = db.execute("insert into products (sku, name, price, min_stock) values (?, ?, ?, ?)",
                                (sku, name, price, min_stock))
            if quantity:
                move_stock(cursor.lastrowid, quantity)
    except sqlite3.IntegrityError:
        raise ValueError("That SKU already exists.")


def move_stock(product_id, change):
    with db:
        quantity = db.execute("select quantity from products where id = ?", (product_id,)).fetchone()[0]
        if quantity + change < 0:
            raise ValueError(f"Not enough stock. Only {quantity} left.")
        db.execute("update products set quantity = quantity + ? where id = ?", (change, product_id))
        db.execute("insert into moves (product_id, change, quantity_after, at) values (?, ?, ?, ?)",
                   (product_id, change, quantity + change, datetime.now().strftime("%d %b %H:%M")))


def delete_product(product_id):
    with db:
        db.execute("delete from moves where product_id = ?", (product_id,))
        db.execute("delete from products where id = ?", (product_id,))


def find_products(text=""):
    like = f"%{text}%"
    return db.execute("select id, sku, name, price, quantity, min_stock from products "
                      "where name like ? or sku like ? order by name", (like, like)).fetchall()


def recent_moves(product_id):
    return db.execute("select at, change, quantity_after from moves where product_id = ? order by id desc limit 20",
                      (product_id,)).fetchall()


def totals():
    return db.execute("select count(*), coalesce(sum(quantity), 0), coalesce(sum(quantity * price), 0), "
                      "coalesce(sum(quantity <= min_stock), 0) from products").fetchone()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("StockPilot")
        self.geometry("900x600")

        self.summary = ttk.Label(self, font=("Segoe UI", 11, "bold"))
        self.summary.pack(anchor="w", padx=12, pady=(12, 6))

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=12)
        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *_: self.refresh())
        ttk.Entry(bar, textvariable=self.search, width=30).pack(side="left")
        for text, command in (("Add product", self.add), ("Stock in", lambda: self.move(1)),
                              ("Stock out", lambda: self.move(-1)), ("Delete", self.delete)):
            ttk.Button(bar, text=text, command=command).pack(side="left", padx=(8, 0))

        self.table = ttk.Treeview(self, columns=("sku", "name", "price", "quantity"), show="headings", height=14)
        for column, title, width in (("sku", "SKU", 120), ("name", "Product", 380), ("price", "Price", 120),
                                     ("quantity", "In stock", 120)):
            self.table.heading(column, text=title)
            self.table.column(column, width=width, anchor="w" if column in ("sku", "name") else "e")
        self.table.tag_configure("low", foreground="#d97706")
        self.table.tag_configure("out", foreground="#dc2626")
        self.table.pack(fill="both", expand=True, padx=12, pady=10)
        self.table.bind("<<TreeviewSelect>>", lambda _: self.show_history())

        self.history = ttk.Treeview(self, columns=("at", "change", "after"), show="headings", height=6)
        for column, title in (("at", "When"), ("change", "Change"), ("after", "Stock after")):
            self.history.heading(column, text=title)
            self.history.column(column, width=150, anchor="w")
        self.history.pack(fill="x", padx=12, pady=(0, 12))

        self.refresh()

    def refresh(self):
        self.table.delete(*self.table.get_children())
        for id_, sku, name, price, quantity, min_stock in find_products(self.search.get()):
            tag = "out" if quantity == 0 else "low" if quantity <= min_stock else ""
            self.table.insert("", "end", iid=str(id_), values=(sku, name, f"{price:,.2f}", quantity), tags=(tag,))
        count, units, value, low = totals()
        self.summary.config(text=f"{count} products   |   {units} units   |   value {value:,.2f}   |   {low} low or out")
        self.show_history()

    def show_history(self):
        self.history.delete(*self.history.get_children())
        if self.selected():
            for row in recent_moves(self.selected()):
                self.history.insert("", "end", values=row)

    def selected(self):
        chosen = self.table.selection()
        return int(chosen[0]) if chosen else None

    def add(self):
        window = tk.Toplevel(self)
        window.title("Add product")
        fields = {}
        for row, (key, title, start) in enumerate((("sku", "SKU", ""), ("name", "Name", ""), ("price", "Price", "0"),
                                                   ("quantity", "Opening stock", "0"), ("min_stock", "Alert level", "5"))):
            ttk.Label(window, text=title).grid(row=row, column=0, sticky="w", padx=10, pady=4)
            fields[key] = ttk.Entry(window, width=28)
            fields[key].insert(0, start)
            fields[key].grid(row=row, column=1, padx=10, pady=4)

        def save():
            try:
                add_product(*(fields[key].get().strip() for key in ("sku", "name", "price", "quantity", "min_stock")))
            except ValueError as problem:
                messagebox.showerror("Cannot save", str(problem), parent=window)
                return
            window.destroy()
            self.refresh()

        ttk.Button(window, text="Save", command=save).grid(row=5, column=1, sticky="e", padx=10, pady=10)

    def move(self, direction):
        if not self.selected():
            messagebox.showinfo("StockPilot", "Select a product first.")
            return
        amount = simpledialog.askinteger("Quantity", "How many units?", parent=self, minvalue=1)
        if amount:
            try:
                move_stock(self.selected(), direction * amount)
            except ValueError as problem:
                messagebox.showerror("Cannot save", str(problem))
            self.refresh()

    def delete(self):
        if self.selected() and messagebox.askyesno("Delete", "Delete this product and its history?"):
            delete_product(self.selected())
            self.refresh()


if __name__ == "__main__":
    App().mainloop()
