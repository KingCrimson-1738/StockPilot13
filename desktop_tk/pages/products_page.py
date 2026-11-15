"""Products: search, filter, add, edit, archive and restore. Filtering is done by the server/database."""
from tkinter import messagebox

import customtkinter as ctk

import theme
from background import run_async
from widgets.controls import Banner, danger_button, entry, label, primary_button, secondary_button
from widgets.data_table import DataTable
from widgets.product_dialog import ProductDialog

ALL_CATEGORIES = "All categories"
STOCK_CHOICES = {"All stock levels": "all", "Stock OK": "ok", "Low stock": "low", "Out of stock": "out"}
STATUS_CHOICES = {"Active products": "active", "Archived products": "archived", "All products": "all"}
STATUS_TEXT = {"ok": "OK", "low": "Low", "out": "Out"}
ROW_TAGS = {"ok": None, "low": "low", "out": "out"}


def _menu(parent, values, command, width):
    return ctk.CTkOptionMenu(
        parent, values=values, command=command, width=width, height=38, corner_radius=8,
        fg_color=theme.CARD, button_color=theme.CARD, button_hover_color=theme.BORDER,
        dropdown_fg_color=theme.CARD, dropdown_hover_color=theme.PRIMARY, dropdown_text_color=theme.TEXT,
        text_color=theme.TEXT, font=theme.font(13), dropdown_font=theme.font(13),
    )


class ProductsPage(ctk.CTkFrame):
    def __init__(self, parent, shell):
        super().__init__(parent, fg_color="transparent")
        self.shell, self.app, self.session = shell, shell.app, shell.session
        self.products = []        # same order as the table rows
        self.categories = []
        self.suppliers = []
        self.category_ids = {}    # menu text -> category id
        self.request_number = 0   # lets us ignore answers that arrive late
        self.search_job = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self.banner = Banner(self)
        self.banner.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.banner.hide()

        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.grid(row=1, column=0, sticky="ew")
        filters.grid_columnconfigure(0, weight=1)
        self.search = entry(filters, "Search by name or SKU", width=200)
        self.search.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.search.bind("<KeyRelease>", self.search_typed)
        self.category_menu = _menu(filters, [ALL_CATEGORIES], self.filters_changed, 160)
        self.category_menu.grid(row=0, column=1, padx=(0, 10))
        self.stock_menu = _menu(filters, list(STOCK_CHOICES), self.filters_changed, 150)
        self.stock_menu.grid(row=0, column=2, padx=(0, 10))
        self.status_menu = _menu(filters, list(STATUS_CHOICES), self.filters_changed, 160)
        self.status_menu.grid(row=0, column=3)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", pady=(14, 10))
        actions.grid_columnconfigure(0, weight=1)
        self.count_label = label(actions, "", 13, color=theme.TEXT_MUTED, anchor="w")
        self.count_label.grid(row=0, column=0, sticky="w")
        primary_button(actions, "Add product", self.add_product, width=130).grid(row=0, column=1, padx=(10, 0))
        secondary_button(actions, "Edit", self.edit_selected, width=80).grid(row=0, column=2, padx=(10, 0))
        self.remove_button = danger_button(actions, "Archive / delete", self.remove_selected, width=150)
        self.remove_button.grid(row=0, column=3, padx=(10, 0))
        self.restore_button = secondary_button(actions, "Restore", self.restore_selected, width=90)
        self.restore_button.grid(row=0, column=4, padx=(10, 0))

        self.table = DataTable(
            self,
            columns=[("SKU", 70, "w"), ("NAME", 140, "w"), ("CATEGORY", 90, "w"), ("SUPPLIER", 90, "w"),
                     ("COST", 70, "e"), ("PRICE", 70, "e"), ("STOCK", 50, "center"), ("STATUS", 60, "w")],
            empty_text="", on_double_click=self.edit_at,
        )
        self.table.grid(row=3, column=0, sticky="nsew")

    # ----- loading -----
    def refresh(self):
        """Called whenever the page is shown or the business changes: reload categories and products."""
        self.banner.hide()
        business_id = self.session.business["id"]
        owner = self.session.is_owner
        for button in (self.remove_button, self.restore_button):
            button.grid() if owner else button.grid_remove()

        number = self._next_request()
        run_async(
            self,
            work=lambda: (self.session.api.list_categories(business_id), self.session.api.list_suppliers(business_id),
                          self.session.api.list_products(business_id, **self.filters())),
            on_done=lambda result: self.loaded(number, business_id, *result),
            on_error=lambda error: self.failed(number, error),
        )

    def filters(self):
        return {
            "search": self.search.get().strip(),
            "category_id": self.category_ids.get(self.category_menu.get()),
            "stock": STOCK_CHOICES[self.stock_menu.get()],
            "archived": STATUS_CHOICES[self.status_menu.get()],
        }

    def reload_products(self):
        business_id = self.session.business["id"]
        number = self._next_request()
        run_async(
            self,
            work=lambda: self.session.api.list_products(business_id, **self.filters()),
            on_done=lambda products: self.loaded(number, business_id, None, None, products),
            on_error=lambda error: self.failed(number, error),
        )

    def _next_request(self):
        self.request_number += 1
        return self.request_number

    def loaded(self, number, business_id, categories, suppliers, products):
        if number != self.request_number or business_id != self.session.business["id"]:
            return  # an older answer, or the user switched business meanwhile
        if categories is not None:
            self.set_categories(categories)
        if suppliers is not None:
            self.suppliers = suppliers
        self.products = products
        currency = self.session.business["currency"]
        rows, tags = [], []
        for p in products:
            status = "Archived" if p["is_archived"] else STATUS_TEXT[p["stock_status"]]
            rows.append((p["sku"], p["name"], p["category_name"] or "—", p["supplier_name"] or "—", f"{p['purchase_price']:,.2f}",
                         f"{p['selling_price']:,.2f}", p["quantity"], status))
            tags.append("muted" if p["is_archived"] else ROW_TAGS[p["stock_status"]])
        filtered = bool(self.filters()["search"]) or self.category_menu.get() != ALL_CATEGORIES \
            or self.stock_menu.get() != "All stock levels" or self.status_menu.get() != "Active products"
        empty = "No products match your search or filters." if filtered else "No products yet.\nClick 'Add product' to create your first one."
        self.table.set_rows(rows, tags, empty_text=empty)
        noun = "product" if len(products) == 1 else "products"
        self.count_label.configure(text=f"{len(products)} {noun}  ·  prices in {currency}")

    def set_categories(self, categories):
        self.categories = categories
        self.category_ids = {c["name"]: c["id"] for c in categories}
        previous = self.category_menu.get()
        self.category_menu.configure(values=[ALL_CATEGORIES] + list(self.category_ids))
        self.category_menu.set(previous if previous in self.category_ids else ALL_CATEGORIES)

    def failed(self, number, error):
        if number == self.request_number:
            self.app.report_error(error, self.banner)

    # ----- searching and filtering -----
    def search_typed(self, event):
        """Wait until the user pauses typing (300 ms) before asking the server."""
        if self.search_job:
            self.after_cancel(self.search_job)
        self.search_job = self.after(300, self.reload_products)

    def filters_changed(self, _choice):
        self.reload_products()

    # ----- actions -----
    def selected_product(self):
        index = self.table.selected_index()
        if index is None:
            self.banner.show("Select a product in the table first.")
            return None
        return self.products[index]

    def add_product(self):
        ProductDialog(self.app, self.categories, self.suppliers, self.product_saved)

    def edit_selected(self):
        product = self.selected_product()
        if product:
            ProductDialog(self.app, self.categories, self.suppliers, self.product_saved, product)

    def edit_at(self, index):  # double click
        if index is not None:
            ProductDialog(self.app, self.categories, self.suppliers, self.product_saved, self.products[index])

    def product_saved(self, product):
        self.banner.show(f"'{product['name']}' was saved.", "success")
        self.reload_products()

    def remove_selected(self):
        product = self.selected_product()
        if not product:
            return
        if product["is_archived"]:
            self.banner.show("This product is already archived.")
            return
        question = (f"Remove '{product['name']}'?\n\nIf it has stock history it will be archived "
                    "(hidden, but its history is kept). Otherwise it will be deleted.")
        if not messagebox.askyesno("Archive or delete product", question):
            return
        business_id = self.session.business["id"]
        run_async(
            self,
            work=lambda: self.session.api.remove_product(business_id, product["id"]),
            on_done=lambda result: self.removed(product, result),
            on_error=lambda error: self.app.report_error(error, self.banner),
        )

    def removed(self, product, result):
        self.banner.show(f"'{product['name']}': {result['message']}", "success")
        self.reload_products()

    def restore_selected(self):
        product = self.selected_product()
        if not product:
            return
        if not product["is_archived"]:
            self.banner.show("Only archived products can be restored. Choose 'Archived products' in the filter.")
            return
        business_id = self.session.business["id"]
        run_async(
            self,
            work=lambda: self.session.api.restore_product(business_id, product["id"]),
            on_done=lambda restored: self.restored(restored),
            on_error=lambda error: self.app.report_error(error, self.banner),
        )

    def restored(self, product):
        self.banner.show(f"'{product['name']}' was restored.", "success")
        self.reload_products()
