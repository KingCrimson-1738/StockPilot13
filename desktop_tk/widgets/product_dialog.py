"""The add / edit product window (a pop-up on top of the main window)."""
from decimal import Decimal, InvalidOperation

import customtkinter as ctk

import theme
from background import run_async
from widgets.controls import Banner, entry, label, primary_button, secondary_button
from widgets.modal import show_modal

NO_CATEGORY = "No category"
NO_SUPPLIER = "No supplier"


def parse_price(text, field_name):
    """'' -> '0.00'. Raises ValueError with a friendly message for bad input."""
    text = text.strip() or "0"
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError(f"{field_name} must be a number, for example 249.50.")
    if not value.is_finite() or value < 0:
        raise ValueError(f"{field_name} cannot be negative.")
    if value.as_tuple().exponent < -2:
        raise ValueError(f"{field_name} can have at most 2 decimal places.")
    return f"{value:.2f}"  # sent as text so no precision is lost


def parse_whole_number(text, field_name, blank_means):
    text = text.strip()
    if not text:
        return blank_means
    if not text.isdigit():
        raise ValueError(f"{field_name} must be a whole number (0 or more).")
    return int(text)


class ProductDialog(ctk.CTkToplevel):
    def __init__(self, app, categories, suppliers, on_saved, product=None):
        super().__init__(app, fg_color=theme.CARD)
        self.app, self.session, self.on_saved, self.product = app, app.session, on_saved, product
        self.categories = {c["name"]: c["id"] for c in categories}
        self.suppliers = {x["name"]: x["id"] for x in suppliers}
        self.business_id = self.session.business["id"]
        self.title("Edit product" if product else "Add product")
        self.resizable(False, False)
        self.transient(app)
        self.grid_columnconfigure((0, 1), weight=1, uniform="half")

        label(self, "Edit product" if product else "Add a product", 20, "bold", anchor="w") \
            .grid(row=0, column=0, columnspan=2, sticky="w", padx=28, pady=(24, 6))
        self.banner = Banner(self)
        self.banner.grid(row=1, column=0, columnspan=2, sticky="ew", padx=28, pady=(6, 0))
        self.banner.hide()

        self.name = self._field("Product name *", 2, 0, 2, "e.g. USB-C cable 1m")
        self.sku = self._field("SKU (unique code) *", 4, 0, 1, "e.g. CBL-001")
        label(self, "Category", 12, color=theme.TEXT_MUTED, anchor="w").grid(row=4, column=1, sticky="w", padx=(10, 28), pady=(12, 4))
        self.category = self._menu([NO_CATEGORY] + list(self.categories))
        self.category.grid(row=5, column=1, sticky="ew", padx=(10, 28))
        self.purchase_price = self._field("Purchase price", 6, 0, 1, "0.00")
        self.selling_price = self._field("Selling price", 6, 1, 1, "0.00")
        label(self, "Supplier", 12, color=theme.TEXT_MUTED, anchor="w").grid(row=8, column=0, columnspan=2, sticky="w", padx=28, pady=(12, 4))
        self.supplier = self._menu([NO_SUPPLIER] + list(self.suppliers))
        self.supplier.grid(row=9, column=0, columnspan=2, sticky="ew", padx=28)
        default_level = self.session.business["default_min_stock"]
        self.min_stock = self._field(f"Low-stock alert level (blank = {default_level})", 10, 0, 1, str(default_level))

        if product is None:
            self.opening_quantity = self._field("Opening stock", 10, 1, 1, "0")
        else:
            self.opening_quantity = None
            label(self, f"Current stock: {product['quantity']}  (change it with Stock in / out)", 11,
                  color=theme.TEXT_MUTED, anchor="w", wraplength=200, justify="left").grid(row=10, column=1, rowspan=2, sticky="w", padx=(10, 28))
            self._fill(product)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=12, column=0, columnspan=2, sticky="e", padx=28, pady=(24, 24))
        secondary_button(buttons, "Cancel", self.destroy, width=100).pack(side="left", padx=(0, 10))
        self.save_button = primary_button(buttons, "Save product", self.save, width=140)
        self.save_button.pack(side="left")

        self.bind("<Escape>", lambda event: self.destroy())
        self.after(150, lambda: show_modal(self, self.app))

    def _menu(self, values):
        return ctk.CTkOptionMenu(
            self, values=values, height=40, corner_radius=8,
            fg_color=theme.INPUT_BG, button_color=theme.INPUT_BG, button_hover_color=theme.BORDER,
            dropdown_fg_color=theme.CARD, dropdown_hover_color=theme.PRIMARY, text_color=theme.TEXT,
            font=theme.font(13), dropdown_font=theme.font(13),
        )

    def _field(self, title, row, column, span, placeholder):
        right_gap = 28 if column + span == 2 else 10
        left_gap = 28 if column == 0 else 10
        label(self, title, 12, color=theme.TEXT_MUTED, anchor="w").grid(
            row=row, column=column, columnspan=span, sticky="w", padx=(left_gap, right_gap), pady=(12, 4))
        box = entry(self, placeholder, width=10)
        box.grid(row=row + 1, column=column, columnspan=span, sticky="ew", padx=(left_gap, right_gap))
        return box

    def _fill(self, product):
        self.name.insert(0, product["name"])
        self.sku.insert(0, product["sku"])
        self.category.set(product["category_name"] or NO_CATEGORY)
        self.supplier.set(product["supplier_name"] if product["supplier_name"] in self.suppliers else NO_SUPPLIER)
        self.purchase_price.insert(0, f"{product['purchase_price']:.2f}")
        self.selling_price.insert(0, f"{product['selling_price']:.2f}")
        if product["min_stock"] is not None:
            self.min_stock.insert(0, str(product["min_stock"]))

    def read_form(self):
        """Returns the values for the API, or raises ValueError with a message for the user."""
        name, sku = self.name.get().strip(), self.sku.get().strip()
        if not name:
            raise ValueError("Please enter the product name.")
        if not sku:
            raise ValueError("Please enter a SKU (a unique code for this product).")
        values = {
            "name": name, "sku": sku,
            "category_id": self.categories.get(self.category.get()),  # None for "No category"
            "supplier_id": self.suppliers.get(self.supplier.get()),
            "purchase_price": parse_price(self.purchase_price.get(), "Purchase price"),
            "selling_price": parse_price(self.selling_price.get(), "Selling price"),
            "min_stock": parse_whole_number(self.min_stock.get(), "The alert level", blank_means=None),
        }
        if self.opening_quantity is not None:
            values["opening_quantity"] = parse_whole_number(self.opening_quantity.get(), "Opening stock", blank_means=0)
        return values

    def save(self):
        try:
            values = self.read_form()
        except ValueError as problem:
            self.banner.show(str(problem))
            return
        self.banner.hide()
        self.save_button.configure(state="disabled", text="Saving…")
        api = self.session.api
        if self.product is None:
            work = lambda: api.create_product(self.business_id, values)
        else:
            work = lambda: api.update_product(self.business_id, self.product["id"], values)
        run_async(self, work, self.saved, self.failed)

    def saved(self, product):
        self.on_saved(product)
        self.destroy()

    def failed(self, error):
        self.save_button.configure(state="normal", text="Save product")
        self.app.report_error(error, self.banner)
