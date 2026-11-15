"""Reports: charts of stock movement and stock value, plus CSV exports. All numbers come from the server."""
from datetime import date, datetime, time, timedelta

import customtkinter as ctk

import theme
from background import run_async
from widgets.chart import ChartCard, draw_category_bars, draw_daily_bars, short
from widgets.controls import Banner, label, secondary_button
from widgets.export import export_csv
from widgets.stat_card import StatCard

PERIODS = ("Last 7 days", "Last 30 days", "This month", "All time")


def period_range(choice, today=None):
    """-> (first_day or None, last_day or None) in the user's local calendar."""
    today = today or date.today()
    if choice == "Last 7 days":
        return today - timedelta(days=6), today
    if choice == "Last 30 days":
        return today - timedelta(days=29), today
    if choice == "This month":
        return today.replace(day=1), today
    return None, None


def local_midnight_iso(day):
    """Local midnight of `day`, with its UTC offset, e.g. 2026-11-16T00:00:00+05:30 (what the server wants)."""
    return datetime.combine(day, time.min).astimezone().isoformat()


def utc_offset_minutes():
    return int(datetime.now().astimezone().utcoffset().total_seconds() // 60)


class ReportsPage(ctk.CTkFrame):
    def __init__(self, parent, shell):
        super().__init__(parent, fg_color="transparent")
        self.shell, self.app, self.session = shell, shell.app, shell.session
        self.request_number = 0
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.banner = Banner(self)
        self.banner.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.banner.hide()

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        bar.grid_columnconfigure(1, weight=1)
        self.period = ctk.CTkOptionMenu(
            bar, values=list(PERIODS), command=lambda _: self.refresh(), width=160, height=38, corner_radius=8,
            fg_color=theme.CARD, button_color=theme.CARD, button_hover_color=theme.BORDER, dropdown_fg_color=theme.CARD,
            dropdown_hover_color=theme.PRIMARY, dropdown_text_color=theme.TEXT, text_color=theme.TEXT,
            font=theme.font(13), dropdown_font=theme.font(13),
        )
        self.period.set("Last 30 days")
        self.period.grid(row=0, column=0)
        secondary_button(bar, "Export products", self.export_products, width=150).grid(row=0, column=2, padx=(10, 0))
        secondary_button(bar, "Export stock history", self.export_history, width=180).grid(row=0, column=3, padx=(10, 0))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", scrollbar_button_color=theme.BORDER)
        scroll.grid(row=2, column=0, sticky="nsew")
        scroll.grid_columnconfigure((0, 1), weight=1, uniform="half")

        self.stats = {}
        stat_row = ctk.CTkFrame(scroll, fg_color="transparent")
        stat_row.grid(row=0, column=0, columnspan=2, sticky="ew")
        stat_row.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="stat")
        for column, (key, title, icon, color) in enumerate((
                ("in", "Stock added", "plus", theme.SUCCESS), ("out", "Stock removed", "swap", theme.PRIMARY),
                ("sales", "Est. sales value", "wallet", theme.PRIMARY), ("count", "Movements", "clock", theme.TEXT_MUTED))):
            card = StatCard(stat_row, title, icon, color)
            card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0 if column == 3 else 6))
            self.stats[key] = card

        self.daily_chart = ChartCard(scroll, "Stock added and removed per day", height=240)
        self.daily_chart.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        self.category_chart = ChartCard(scroll, "Stock value by category (at cost)", height=230)
        self.category_chart.grid(row=2, column=0, sticky="ew", padx=(0, 7), pady=(14, 8))
        self.top_chart = ChartCard(scroll, "Best sellers (units removed)", height=230)
        self.top_chart.grid(row=2, column=1, sticky="ew", padx=(7, 0), pady=(14, 8))
        label(scroll, "Sales value is an estimate: units removed x each product's current selling price.",
              12, color=theme.TEXT_MUTED, anchor="w").grid(row=3, column=0, columnspan=2, sticky="w")

    # ----- loading -----
    def selected_range(self):
        first, last = period_range(self.period.get())
        if first is None:
            return None, None, None, None
        return first, last, local_midnight_iso(first), local_midnight_iso(last + timedelta(days=1))

    def refresh(self):
        self.banner.hide()
        business_id, api = self.session.business["id"], self.session.api
        first, last, from_time, to_time = self.selected_range()
        offset = utc_offset_minutes()
        self.request_number += 1
        number = self.request_number
        run_async(
            self,
            work=lambda: (api.movement_report(business_id, from_time, to_time, offset), api.category_report(business_id)),
            on_done=lambda result: self.show(number, business_id, first, last, *result),
            on_error=lambda error: self.failed(number, error),
        )

    def failed(self, number, error):
        if number == self.request_number:
            self.app.report_error(error, self.banner)

    def show(self, number, business_id, first, last, movement, categories):
        if number != self.request_number or business_id != self.session.business["id"]:
            return
        currency = self.session.business["currency"]
        self.stats["in"].set_value(f"{movement['units_in']:,}")
        self.stats["out"].set_value(f"{movement['units_out']:,}")
        self.stats["sales"].set_value(f"{currency} {movement['sales_value']:,.2f}")
        self.stats["count"].set_value(f"{movement['transaction_count']:,}")
        draw_daily_bars(self.daily_chart, movement["daily"], first, last)
        draw_category_bars(self.category_chart, categories, currency)
        self.draw_top(movement["top_products"])

    # ----- charts -----
    def draw_top(self, top):
        if not top:
            self.top_chart.show_empty("No stock removed in this period.")
            return

        def render(ax):
            ax.grid(axis="y", visible=False)
            ax.grid(axis="x", color=theme.BORDER, linewidth=0.6, alpha=0.6)
            positions = list(range(len(top)))
            ax.barh(positions, [t["units_out"] for t in top], color=theme.SUCCESS, height=0.6)
            ax.set_yticks(positions)
            ax.set_yticklabels([short(t["name"]) for t in top])
            ax.invert_yaxis()
            ax.set_xlabel("units", color=theme.TEXT_MUTED, fontsize=9)
        self.top_chart.draw(render)

    # ----- exports -----
    def export_products(self):
        business_id, api = self.session.business["id"], self.session.api
        export_csv(self, self.app, self.banner, lambda: api.download(f"/businesses/{business_id}/exports/products.csv"))("products.csv")

    def export_history(self):
        business_id, api = self.session.business["id"], self.session.api
        _, _, from_time, to_time = self.selected_range()
        params = {"from_time": from_time, "to_time": to_time, "tz_offset_minutes": utc_offset_minutes()}
        export_csv(self, self.app, self.banner,
                   lambda: api.download(f"/businesses/{business_id}/exports/transactions.csv", params))("stock-history.csv")
