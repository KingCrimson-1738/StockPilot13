"""Dashboard: five headline numbers and the latest stock movements, all from the database."""
from datetime import timedelta

import customtkinter as ctk

import icons
import theme
from background import run_async
from pages.reports_page import period_range, local_midnight_iso, utc_offset_minutes
from widgets.chart import ChartCard, draw_category_bars, draw_daily_bars
from formatting import TYPE_LABELS, local_time, money
from widgets.controls import Banner, label, secondary_button
from widgets.data_table import DataTable
from widgets.stat_card import StatCard

CARD_COLUMNS_WIDE, CARD_COLUMNS_NARROW = 5, 3
WIDE_BREAKPOINT_PIXELS = 900


class DashboardPage(ctk.CTkFrame):
    def __init__(self, parent, shell):
        super().__init__(parent, fg_color="transparent")
        self.shell = shell
        self.session = shell.session
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        self.banner = Banner(self)
        self.banner.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self.banner.hide()

        self.cards_area = ctk.CTkFrame(self, fg_color="transparent")
        self.cards_area.grid(row=1, column=0, sticky="ew")
        self.cards = {
            "products": StatCard(self.cards_area, "Total products", "box", theme.PRIMARY),
            "stock": StatCard(self.cards_area, "Units in stock", "layers", theme.PRIMARY),
            "value": StatCard(self.cards_area, "Inventory value", "wallet", theme.SUCCESS),
            "low": StatCard(self.cards_area, "Low stock", "alert", theme.WARNING),
            "out": StatCard(self.cards_area, "Out of stock", "ban", theme.DANGER),
        }
        self.card_columns = 0
        self.cards_area.bind("<Configure>", self.arrange_cards)

        charts = ctk.CTkFrame(self, fg_color="transparent")
        charts.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        charts.grid_columnconfigure((0, 1), weight=1, uniform="half")
        self.movement_chart = ChartCard(charts, "Stock movement, last 7 days", height=170)
        self.movement_chart.grid(row=0, column=0, sticky="ew", padx=(6, 6))
        self.category_chart = ChartCard(charts, "Stock value by category", height=170)
        self.category_chart.grid(row=0, column=1, sticky="ew", padx=(6, 6))
        self.chart_request = 0

        heading = ctk.CTkFrame(self, fg_color="transparent")
        heading.grid(row=3, column=0, sticky="ew", pady=(18, 10))
        heading.grid_columnconfigure(0, weight=1)
        label(heading, "Recent stock movements", 16, "bold", anchor="w").grid(row=0, column=0, sticky="w")
        secondary_button(heading, "Refresh", self.refresh, width=100, icon=icons.get_icon("refresh", theme.TEXT, 16)).grid(row=0, column=1)

        self.table = DataTable(
            self,
            columns=[("TIME", 95, "w"), ("PRODUCT", 130, "w"), ("TYPE", 85, "w"), ("CHANGE", 65, "e"),
                     ("STOCK AFTER", 90, "e"), ("BY", 95, "w"), ("REASON", 100, "w")],  # fits the smallest window
            empty_text="No stock movements yet.\nStock-in, stock-out and adjustments will appear here.",
        )
        self.table.grid(row=4, column=0, sticky="nsew")

    def arrange_cards(self, event):
        """Responsive: five cards in a row on a wide window, three per row on a narrow one."""
        columns = CARD_COLUMNS_WIDE if event.width >= WIDE_BREAKPOINT_PIXELS else CARD_COLUMNS_NARROW
        if columns == self.card_columns:
            return
        self.card_columns = columns
        for index in range(CARD_COLUMNS_WIDE):
            self.cards_area.grid_columnconfigure(index, weight=1 if index < columns else 0, uniform="card" if index < columns else "")
        for index, card in enumerate(self.cards.values()):
            card.grid(row=index // columns, column=index % columns, sticky="nsew", padx=6, pady=6)

    # ----- loading -----
    def refresh(self):
        business_id = self.session.business["id"]
        self.banner.hide()
        for card in self.cards.values():
            card.set_loading()
        run_async(
            self,
            work=lambda: self.session.api.get_dashboard(business_id),
            on_done=lambda data: self.show(business_id, data),
            on_error=lambda error: self.failed(business_id, error),
        )
        self.load_charts(business_id)

    def load_charts(self, business_id):
        """Chart data comes from the same report endpoints the Reports page uses (a failure only affects the charts)."""
        first, last = period_range("Last 7 days")
        from_time, to_time = local_midnight_iso(first), local_midnight_iso(last + timedelta(days=1))
        api, offset = self.session.api, utc_offset_minutes()
        self.chart_request += 1
        number = self.chart_request
        run_async(
            self,
            work=lambda: (api.movement_report(business_id, from_time, to_time, offset), api.category_report(business_id)),
            on_done=lambda result: self.show_charts(number, business_id, first, last, *result),
            on_error=lambda error: self.failed(business_id, error) if number == self.chart_request else None,
        )

    def show_charts(self, number, business_id, first, last, movement, categories):
        if number != self.chart_request or business_id != self.session.business["id"]:
            return
        draw_daily_bars(self.movement_chart, movement["daily"], first, last)
        draw_category_bars(self.category_chart, categories, self.session.business["currency"])

    def show(self, business_id, data):
        if business_id != self.session.business["id"]:  # the user switched business meanwhile
            return
        self.cards["products"].set_value(f"{data['total_products']:,}")
        self.cards["stock"].set_value(f"{data['total_stock']:,}")
        self.cards["value"].set_value(money(data["inventory_value"], data["currency"]))
        self.cards["low"].set_value(str(data["low_stock_count"]), theme.WARNING if data["low_stock_count"] else theme.TEXT)
        self.cards["out"].set_value(str(data["out_of_stock_count"]), theme.DANGER if data["out_of_stock_count"] else theme.TEXT)

        self.table.set_rows([
            (local_time(t["created_at"]), t["product_name"], TYPE_LABELS[t["type"]], f"{t['quantity_change']:+d}",
             t["quantity_after"], t["user_name"] or "—", t["reason"] or "—")
            for t in data["recent_transactions"]
        ])
        if data["total_products"] == 0:
            self.banner.show("This business has no products yet. Totals will appear here once products are added.", "info")

    def failed(self, business_id, error):
        if business_id != self.session.business["id"]:
            return
        for card in self.cards.values():
            card.set_value("—", theme.TEXT_MUTED)
        self.shell.app.report_error(error, self.banner)
