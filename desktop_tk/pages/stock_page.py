"""Stock in / stock out / adjust. Pick a product on the left, record the movement on the right.

The screen only collects the numbers; the server does the real work (locks the row, refuses
negative stock, writes the history entry) so two people at two computers can never oversell.
"""
import customtkinter as ctk

import theme
from background import run_async
from widgets.controls import Banner, entry, label, primary_button
from widgets.data_table import DataTable

MODES = ("Stock in", "Stock out", "Adjust")
STATUS_TEXT = {"ok": "OK", "low": "Low", "out": "Out"}
ROW_TAGS = {"ok": None, "low": "low", "out": "out"}
MAX_QUANTITY = 1_000_000
REASON_HINTS = {"Stock in": "Reason (optional), e.g. Supplier delivery", "Stock out": "Reason (optional), e.g. Sale",
                "Adjust": "Reason (required), e.g. Damaged / stock count"}


def parse_quantity(text, what, minimum):
    """Whole number from the text box. Raises ValueError with a friendly message."""
    text = text.strip()
    if not text:
        raise ValueError(f"Please enter {what}.")
    if not text.isdigit():
        raise ValueError(f"{what[0].upper() + what[1:]} must be a whole number.")
    value = int(text)
    if value < minimum:
        raise ValueError(f"{what[0].upper() + what[1:]} must be at least {minimum}.")
    if value > MAX_QUANTITY:
        raise ValueError(f"{what[0].upper() + what[1:]} cannot be more than {MAX_QUANTITY:,}.")
    return value


class StockPage(ctk.CTkFrame):
    def __init__(self, parent, shell):
        super().__init__(parent, fg_color="transparent")
        self.shell, self.app, self.session = shell, shell.app, shell.session
        self.products = []          # same order as the table rows
        self.request_number = 0
        self.search_job = None
        self.selected_id = None     # the product being worked on (kept across reloads)
        self.after_message = None   # shown after the next reload (so low-stock warnings use fresh data)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.banner = Banner(self)
        self.banner.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        self.banner.hide()

        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)
        self.search = entry(left, "Search by name or SKU", width=200)
        self.search.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.search.bind("<KeyRelease>", self.search_typed)
        self.table = DataTable(
            left, columns=[("SKU", 80, "w"), ("PRODUCT", 170, "w"), ("STOCK", 60, "center"), ("STATUS", 60, "w")],
            empty_text="No products yet.\nAdd products first, then record stock here.", on_select=self.row_selected,
        )
        self.table.grid(row=1, column=0, sticky="nsew")
        # a real click on the table clears an old message (reloads select rows by code and must not clear the new one)
        self.table.tree.bind("<ButtonRelease-1>", lambda event: self.banner.hide(), add="+")

        self.panel = ctk.CTkFrame(self, fg_color=theme.CARD, corner_radius=12, width=330)
        self.panel.grid(row=1, column=1, sticky="ns")
        self.panel.grid_propagate(False)
        self.panel.grid_columnconfigure(0, weight=1)
        self._build_panel()

    def _build_panel(self):
        panel = self.panel
        self.product_name = label(panel, "Select a product", 16, "bold", anchor="w", wraplength=280, justify="left")
        self.product_name.grid(row=0, column=0, sticky="ew", padx=22, pady=(22, 2))
        self.product_info = label(panel, "Pick one from the table on the left.", 12, color=theme.TEXT_MUTED, anchor="w",
                                  wraplength=280, justify="left")
        self.product_info.grid(row=1, column=0, sticky="ew", padx=22)

        self.mode = ctk.CTkSegmentedButton(
            panel, values=list(MODES), command=self.mode_changed, height=36, corner_radius=8, font=theme.font(12, "bold"),
            fg_color=theme.INPUT_BG, selected_color=theme.PRIMARY, selected_hover_color=theme.PRIMARY_HOVER,
            unselected_color=theme.INPUT_BG, unselected_hover_color=theme.BORDER, text_color=theme.TEXT,
        )
        self.mode.grid(row=2, column=0, sticky="ew", padx=22, pady=(20, 0))
        self.mode.set("Stock in")

        self.quantity_title = label(panel, "Quantity", 12, color=theme.TEXT_MUTED, anchor="w")
        self.quantity_title.grid(row=3, column=0, sticky="w", padx=22, pady=(16, 4))
        self.quantity = entry(panel, "0", width=10)
        self.quantity.grid(row=4, column=0, sticky="ew", padx=22)
        self.quantity.bind("<KeyRelease>", lambda event: self.update_preview())
        self.quantity.bind("<Return>", lambda event: self.submit())

        label(panel, "Reason", 12, color=theme.TEXT_MUTED, anchor="w").grid(row=5, column=0, sticky="w", padx=22, pady=(14, 4))
        self.reason = entry(panel, REASON_HINTS["Stock in"], width=10)
        self.reason.grid(row=6, column=0, sticky="ew", padx=22)
        self.reason.bind("<Return>", lambda event: self.submit())

        self.preview = label(panel, "", 13, "bold", anchor="w", wraplength=280, justify="left")
        self.preview.grid(row=7, column=0, sticky="ew", padx=22, pady=(16, 0))
        self.submit_button = primary_button(panel, "Record stock in", self.submit, width=10)
        self.submit_button.grid(row=8, column=0, sticky="ew", padx=22, pady=(14, 22))
        self.set_form_enabled(False)

    # ----- loading -----
    def refresh(self):
        self.banner.hide()
        owner = self.session.is_owner
        values = list(MODES) if owner else list(MODES[:2])  # only owners may adjust
        self.mode.configure(values=values)
        if self.mode.get() not in values:
            self.mode.set("Stock in")
            self.mode_changed("Stock in")
        self.reload()

    def reload(self):
        business_id = self.session.business["id"]
        self.request_number += 1
        number = self.request_number
        search = self.search.get().strip()
        run_async(
            self,
            work=lambda: self.session.api.list_products(business_id, search=search),
            on_done=lambda products: self.loaded(number, business_id, products),
            on_error=lambda error: self.failed(number, error),
        )

    def failed(self, number, error):
        if number == self.request_number:
            self.app.report_error(error, self.banner)

    def loaded(self, number, business_id, products):
        if number != self.request_number or business_id != self.session.business["id"]:
            return
        self.products = products
        self.table.set_rows(
            [(p["sku"], p["name"], p["quantity"], STATUS_TEXT[p["stock_status"]]) for p in products],
            [ROW_TAGS[p["stock_status"]] for p in products],
            empty_text="No products match your search." if self.search.get().strip() else "No products yet.\nAdd products first, then record stock here.",
        )
        index = next((i for i, p in enumerate(products) if p["id"] == self.selected_id), None)
        if index is not None:
            self.table.tree.selection_set(str(index))   # fires row_selected, which refreshes the panel
            self.table.tree.see(str(index))
        else:
            self.selected_id = None
            self.show_product(None)
        if self.after_message and index is not None:
            self.show_result_message(self.after_message, products[index])
        self.after_message = None

    def search_typed(self, event):
        if self.search_job:
            self.after_cancel(self.search_job)
        self.search_job = self.after(300, self.reload)

    # ----- the form -----
    def current_product(self):
        return next((p for p in self.products if p["id"] == self.selected_id), None)

    def row_selected(self, index):
        if index is None:
            return  # a reload cleared the highlight; keep the current product
        self.selected_id = self.products[index]["id"]
        self.show_product(self.products[index])

    def show_product(self, product):
        if product is None:
            self.product_name.configure(text="Select a product")
            self.product_info.configure(text="Pick one from the table on the left.")
            self.set_form_enabled(False)
            self.update_preview()
            return
        level = product["alert_level"]
        self.product_name.configure(text=product["name"])
        self.product_info.configure(text=f"SKU {product['sku']}   ·   In stock: {product['quantity']}   ·   Alert level: {level}")
        self.set_form_enabled(True)
        self.update_preview()

    def set_form_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for widget in (self.quantity, self.reason):
            widget.configure(state=state)
        self.submit_button.configure(state=state)
        self.mode.configure(state=state)

    def mode_changed(self, mode):
        titles = {"Stock in": "Quantity to add", "Stock out": "Quantity to remove", "Adjust": "New counted quantity"}
        self.quantity_title.configure(text=titles[mode])
        self.reason.configure(placeholder_text=REASON_HINTS[mode])
        self.submit_button.configure(text={"Stock in": "Record stock in", "Stock out": "Record stock out", "Adjust": "Save adjustment"}[mode])
        self.reason.delete(0, "end")
        self.reason.configure(placeholder_text=REASON_HINTS[mode])
        self.update_preview()

    def update_preview(self):
        """Shows what the stock will be after the movement, before anything is saved."""
        product, mode = self.current_product(), self.mode.get()
        text, color = "", theme.TEXT_MUTED
        raw = self.quantity.get().strip()
        if product and raw.isdigit() and int(raw) <= MAX_QUANTITY:
            amount, now = int(raw), product["quantity"]
            after = now + amount if mode == "Stock in" else now - amount if mode == "Stock out" else amount
            if after < 0:
                text, color = f"Not enough stock: only {now} available.", theme.DANGER
            else:
                text = f"Stock after: {after}"
                color = theme.WARNING if after == 0 or after <= product["alert_level"] else theme.SUCCESS
        self.preview.configure(text=text, text_color=color)

    def submit(self):
        product, mode = self.current_product(), self.mode.get()
        if product is None:
            self.banner.show("Select a product first.")
            return
        reason = self.reason.get().strip()
        try:
            if mode == "Adjust":
                amount = parse_quantity(self.quantity.get(), "the counted quantity", 0)
                if len(reason) < 3:
                    raise ValueError("Please give a reason for the adjustment (at least 3 letters).")
                if amount == product["quantity"]:
                    raise ValueError("The counted quantity equals the current stock, so there is nothing to adjust.")
            else:
                amount = parse_quantity(self.quantity.get(), "a quantity", 1)
                if mode == "Stock out" and amount > product["quantity"]:
                    raise ValueError(f"Not enough stock. Available: {product['quantity']}, requested: {amount}.")
        except ValueError as problem:
            self.banner.show(str(problem))
            return
        self.banner.hide()
        self.submit_button.configure(state="disabled")
        business_id, api = self.session.business["id"], self.session.api
        if mode == "Stock in":
            work = lambda: api.stock_in(business_id, product["id"], amount, reason or None)
        elif mode == "Stock out":
            work = lambda: api.stock_out(business_id, product["id"], amount, reason or None)
        else:
            work = lambda: api.stock_adjust(business_id, product["id"], amount, reason)
        run_async(self, work, lambda transaction: self.recorded(business_id, product, transaction), self.rejected)

    def rejected(self, error):
        self.submit_button.configure(state="normal")
        self.app.report_error(error, self.banner)
        self.reload()  # the numbers on screen may be stale (e.g. someone else just sold the last unit)

    def recorded(self, business_id, product, transaction):
        if business_id != self.session.business["id"]:
            return
        change = transaction["quantity_change"]
        verbs = {"in": "added", "out": "removed", "adjust": "adjusted"}
        text = (f"{product['name']}: {abs(change)} {verbs[transaction['type']]}"
                if transaction["type"] != "adjust" else f"{product['name']}: stock adjusted by {change:+d}")
        self.after_message = f"{text}. Stock is now {transaction['quantity_after']}."
        self.quantity.delete(0, "end")
        self.quantity.configure(placeholder_text="0")
        self.reason.delete(0, "end")
        self.reason.configure(placeholder_text=REASON_HINTS[self.mode.get()])
        self.submit_button.configure(state="normal")
        self.reload()

    def show_result_message(self, text, product):
        if product["stock_status"] == "out":
            self.banner.show(text + " This product is now OUT of stock.", "warning")
        elif product["stock_status"] == "low":
            self.banner.show(text + f" That is at or below the alert level ({product['alert_level']}) - consider reordering.", "warning")
        else:
            self.banner.show(text, "success")
