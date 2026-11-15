"""Stock history: every movement ever recorded, newest first, with filters."""
from datetime import datetime, time, timedelta

import customtkinter as ctk

import theme
from background import run_async
from formatting import TYPE_LABELS, local_time
from widgets.controls import Banner, entry, label, secondary_button, primary_button
from widgets.data_table import DataTable

ALL_TYPES = "All movements"
TYPE_CHOICES = {ALL_TYPES: None, "Stock in": "in", "Stock out": "out", "Adjustments": "adjust"}
ALL_PRODUCTS = "All products"
LIMIT = 200


def day_range_to_utc(from_text, to_text):
    """'2026-11-16' .. '2026-11-16' typed in local time -> exact UTC instants for the server.

    The server stores UTC. For a user in India, '16 Nov' starts at 15 Nov 18:30 UTC, so we convert
    local midnight to UTC here instead of filtering by UTC calendar days (which would be wrong).
    Returns (from_time, to_time) as ISO text or None. Raises ValueError with a friendly message.
    """
    def parse(text, what):
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"The '{what}' date must look like 2026-11-16 (year-month-day).")

    start = end = None
    if from_text.strip():
        start = datetime.combine(parse(from_text.strip(), "From"), time.min).astimezone().isoformat()  # local midnight, with offset
    if to_text.strip():
        last_day = parse(to_text.strip(), "To")
        end = datetime.combine(last_day + timedelta(days=1), time.min).astimezone().isoformat()  # the whole last day is included
    if start and end and parse(from_text.strip(), "From") > parse(to_text.strip(), "To"):
        raise ValueError("The 'From' date must not be after the 'To' date.")
    return start, end


class HistoryPage(ctk.CTkFrame):
    def __init__(self, parent, shell):
        super().__init__(parent, fg_color="transparent")
        self.shell, self.app, self.session = shell, shell.app, shell.session
        self.product_ids = {ALL_PRODUCTS: None}  # menu text -> product id
        self.request_number = 0
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self.banner = Banner(self)
        self.banner.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.banner.hide()

        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.grid(row=1, column=0, sticky="ew")
        filters.grid_columnconfigure(1, weight=1)
        self.type_menu = self._menu(filters, list(TYPE_CHOICES), 150)
        self.type_menu.grid(row=0, column=0, padx=(0, 10))
        self.product_menu = self._menu(filters, [ALL_PRODUCTS], 220)
        self.product_menu.grid(row=0, column=1, sticky="w", padx=(0, 10))
        label(filters, "From", 12, color=theme.TEXT_MUTED).grid(row=0, column=2, padx=(0, 6))
        self.from_date = entry(filters, "YYYY-MM-DD", width=120)
        self.from_date.grid(row=0, column=3, padx=(0, 10))
        label(filters, "To", 12, color=theme.TEXT_MUTED).grid(row=0, column=4, padx=(0, 6))
        self.to_date = entry(filters, "YYYY-MM-DD", width=120)
        self.to_date.grid(row=0, column=5, padx=(0, 10))
        for box in (self.from_date, self.to_date):
            box.bind("<Return>", lambda event: self.load())
        primary_button(filters, "Apply", self.load, width=80).grid(row=0, column=6, padx=(0, 8))
        secondary_button(filters, "Clear", self.clear, width=80).grid(row=0, column=7)

        self.count_label = label(self, "", 13, color=theme.TEXT_MUTED, anchor="w")
        self.count_label.grid(row=2, column=0, sticky="w", pady=(14, 10))
        self.table = DataTable(
            self, columns=[("WHEN", 110, "w"), ("PRODUCT", 170, "w"), ("TYPE", 85, "w"), ("CHANGE", 65, "e"),
                           ("AFTER", 60, "e"), ("BY", 100, "w"), ("REASON", 180, "w")],
            empty_text="No stock movements match.",
        )
        self.table.grid(row=3, column=0, sticky="nsew")

    @staticmethod
    def _menu(parent, values, width):
        return ctk.CTkOptionMenu(
            parent, values=values, width=width, height=38, corner_radius=8, fg_color=theme.CARD, button_color=theme.CARD,
            button_hover_color=theme.BORDER, dropdown_fg_color=theme.CARD, dropdown_hover_color=theme.PRIMARY,
            dropdown_text_color=theme.TEXT, text_color=theme.TEXT, font=theme.font(13), dropdown_font=theme.font(13),
        )

    def clear(self):
        self.type_menu.set(ALL_TYPES)
        self.product_menu.set(ALL_PRODUCTS)
        for box in (self.from_date, self.to_date):
            box.delete(0, "end")
            box.configure(placeholder_text="YYYY-MM-DD")
        self.load()

    # ----- loading -----
    def refresh(self):
        """Reload the product list (for the product filter) and then the history."""
        self.banner.hide()
        business_id = self.session.business["id"]
        run_async(
            self,
            work=lambda: self.session.api.list_products(business_id, archived="all"),
            on_done=lambda products: self.got_products(business_id, products),
            on_error=lambda error: self.app.report_error(error, self.banner),
        )

    def got_products(self, business_id, products):
        if business_id != self.session.business["id"]:
            return
        self.product_ids = {ALL_PRODUCTS: None}
        for p in products:  # SKU makes names unique even when two products share a name
            self.product_ids[f"{p['name']}  ({p['sku']})"] = p["id"]
        previous = self.product_menu.get()
        self.product_menu.configure(values=list(self.product_ids))
        self.product_menu.set(previous if previous in self.product_ids else ALL_PRODUCTS)
        self.load()

    def load(self):
        try:
            from_time, to_time = day_range_to_utc(self.from_date.get(), self.to_date.get())
        except ValueError as problem:
            self.banner.show(str(problem))
            return
        self.banner.hide()
        business_id = self.session.business["id"]
        self.request_number += 1
        number = self.request_number
        kind = TYPE_CHOICES[self.type_menu.get()]
        product_id = self.product_ids.get(self.product_menu.get())
        run_async(
            self,
            work=lambda: self.session.api.list_transactions(business_id, kind, product_id, from_time, to_time, LIMIT),
            on_done=lambda rows: self.show(number, business_id, rows),
            on_error=lambda error: self.failed(number, error),
        )

    def failed(self, number, error):
        if number == self.request_number:
            self.app.report_error(error, self.banner)

    def show(self, number, business_id, rows):
        if number != self.request_number or business_id != self.session.business["id"]:
            return
        self.table.set_rows([
            (local_time(t["created_at"]), t["product_name"], TYPE_LABELS[t["type"]], f"{t['quantity_change']:+d}",
             t["quantity_after"], t["user_name"], t["reason"] or "—")
            for t in rows
        ])
        shown = f"{len(rows)} movement{'s' if len(rows) != 1 else ''}"
        self.count_label.configure(text=shown + (f"  ·  showing the newest {LIMIT}" if len(rows) == LIMIT else ""))
