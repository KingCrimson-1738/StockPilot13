"""Restock list: every active product at or below its alert level, with a suggested order quantity."""
import customtkinter as ctk

import theme
from background import run_async
from widgets.controls import Banner, label, primary_button, secondary_button
from widgets.data_table import DataTable
from widgets.export import export_csv


class RestockPage(ctk.CTkFrame):
    def __init__(self, parent, shell):
        super().__init__(parent, fg_color="transparent")
        self.shell, self.app, self.session = shell, shell.app, shell.session
        self.items = []  # same order as the table rows
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.banner = Banner(self)
        self.banner.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.banner.hide()

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        bar.grid_columnconfigure(0, weight=1)
        self.summary = label(bar, "", 13, color=theme.TEXT_MUTED, anchor="w")
        self.summary.grid(row=0, column=0, sticky="w")
        primary_button(bar, "Record stock in", self.record_stock_in, width=150).grid(row=0, column=1, padx=(10, 0))
        secondary_button(bar, "Export CSV", self.export, width=120).grid(row=0, column=2, padx=(10, 0))

        self.table = DataTable(
            self, columns=[("SKU", 80, "w"), ("PRODUCT", 170, "w"), ("SUPPLIER", 120, "w"), ("IN STOCK", 70, "e"),
                           ("ALERT AT", 70, "e"), ("ORDER", 70, "e"), ("EST. COST", 100, "e")],
            empty_text="Nothing to reorder.\nEvery product is above its alert level.", on_double_click=lambda i: self.record_stock_in(),
        )
        self.table.grid(row=2, column=0, sticky="nsew")
        label(self, "Suggested order = enough to bring the product back to twice its alert level. "
                    "Select a row and click 'Record stock in' when the delivery arrives.",
              12, color=theme.TEXT_MUTED, anchor="w").grid(row=3, column=0, sticky="w", pady=(10, 0))

    def refresh(self):
        self.banner.hide()
        business_id = self.session.business["id"]
        run_async(
            self,
            work=lambda: self.session.api.low_stock_report(business_id),
            on_done=lambda items: self.show(business_id, items),
            on_error=lambda error: self.app.report_error(error, self.banner),
        )

    def show(self, business_id, items):
        if business_id != self.session.business["id"]:
            return
        self.items = items
        self.table.set_rows(
            [(i["sku"], i["name"], i["supplier_name"] or "—", i["quantity"], i["alert_level"], i["suggested_order"],
              f"{i['estimated_cost']:,.2f}") for i in items],
            ["out" if i["quantity"] == 0 else "low" for i in items],
        )
        total = sum(i["estimated_cost"] for i in items)
        out = sum(1 for i in items if i["quantity"] == 0)
        noun = "product needs" if len(items) == 1 else "products need"
        self.summary.configure(
            text=f"{len(items)} {noun} restocking ({out} out of stock)  ·  estimated cost {self.session.business['currency']} {total:,.2f}"
            if items else "All products are well stocked.")

    def record_stock_in(self):
        index = self.table.selected_index()
        if index is None:
            self.banner.show("Select a product in the table first.")
            return
        stock_page = self.shell.pages["stock"]
        stock_page.selected_id = self.items[index]["product_id"]  # the Stock page opens with this product selected
        stock_page.mode.set("Stock in")
        stock_page.mode_changed("Stock in")
        self.shell.show_page("stock")

    def export(self):
        business_id, api = self.session.business["id"], self.session.api
        export_csv(self, self.app, self.banner, lambda: api.download(f"/businesses/{business_id}/exports/low-stock.csv"))("restock-list.csv")
