"""A Matplotlib chart inside a dark card.

The chart is drawn with Matplotlib's Agg renderer into a picture (PIL image) and shown in a label, and it is
redrawn when the card is resized. We deliberately do NOT use Matplotlib's Tk canvas (FigureCanvasTkAgg): it talks
to Tk through a C interface that can crash with some Tk versions, and these charts do not need zooming.
"""
from datetime import date, timedelta

import customtkinter as ctk
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from PIL import Image

import theme
from widgets.controls import label


class ChartCard(ctk.CTkFrame):
    """card.draw(render) calls render(ax) with a fresh, dark-styled axes. card.show_empty(text) shows a message instead."""

    def __init__(self, parent, title, height=250):
        super().__init__(parent, fg_color=theme.CARD, corner_radius=12)
        self.grid_columnconfigure(0, weight=1)
        label(self, title, 14, "bold", anchor="w").grid(row=0, column=0, sticky="w", padx=18, pady=(14, 0))
        self.area = ctk.CTkFrame(self, fg_color=theme.CARD, height=height)
        self.area.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.area.grid_propagate(False)  # the picture never decides the card's size; the card decides the picture's
        self.picture = ctk.CTkLabel(self.area, text="", fg_color=theme.CARD)
        self.picture.place(x=0, y=0, relwidth=1, relheight=1)
        self.render = None          # what to draw (set by draw / show_empty)
        self.drawn_size = None
        self._redraw_job = None
        self.figure = None          # the last Matplotlib figure (tests look at its axes)
        self.area.bind("<Configure>", self._resized)

    # ----- public -----
    def draw(self, render):
        self.render = render
        self._paint()

    def show_empty(self, text):
        def render(ax):
            ax.axis("off")
            ax.text(0.5, 0.5, text, ha="center", va="center", color=theme.TEXT_MUTED, fontsize=11, transform=ax.transAxes)
        self.draw(render)

    # ----- drawing -----
    def _resized(self, event):
        if self.render and (event.width, event.height) != self.drawn_size:
            if self._redraw_job:
                self.after_cancel(self._redraw_job)
            self._redraw_job = self.after(120, self._paint)  # wait until the user stops resizing

    def _paint(self):
        self._redraw_job = None
        width, height = self.area.winfo_width(), self.area.winfo_height()
        if self.render is None or width < 60 or height < 60:
            return  # not on screen yet; _resized will call us when it is
        figure = Figure(figsize=(width / 100, height / 100), dpi=100, facecolor=theme.CARD, layout="constrained")
        ax = figure.add_subplot(111)
        ax.set_facecolor(theme.CARD)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(theme.BORDER)
        ax.tick_params(colors=theme.TEXT_MUTED, labelsize=9, length=0)
        ax.grid(axis="y", color=theme.BORDER, linewidth=0.6, alpha=0.6)
        ax.set_axisbelow(True)
        self.render(ax)
        canvas = FigureCanvasAgg(figure)
        canvas.draw()
        picture = Image.frombuffer("RGBA", canvas.get_width_height(), canvas.buffer_rgba(), "raw", "RGBA", 0, 1)
        self.image = ctk.CTkImage(light_image=picture, dark_image=picture, size=(width, height))
        self.picture.configure(image=self.image)
        self.figure, self.drawn_size = figure, (width, height)


def short(text, limit=18):
    return text if len(text) <= limit else text[:limit - 1] + "…"


def draw_daily_bars(card, daily, first=None, last=None):
    """Green/blue bars of units added and removed per day. first/last = the period's days (None = use the data's range)."""
    if not daily:
        card.show_empty("No stock movements in this period.")
        return
    by_day = {d["day"]: d for d in daily}
    start, end = first or date.fromisoformat(daily[0]["day"]), last or date.fromisoformat(daily[-1]["day"])
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]  # include days with no movement
    added = [by_day.get(d.isoformat(), {"units_in": 0})["units_in"] for d in days]
    removed = [by_day.get(d.isoformat(), {"units_out": 0})["units_out"] for d in days]

    def render(ax):
        x = list(range(len(days)))
        width = 0.4
        ax.bar([i - width / 2 for i in x], added, width, color=theme.SUCCESS, label="Added")
        ax.bar([i + width / 2 for i in x], removed, width, color=theme.PRIMARY, label="Removed")
        step = max(1, len(days) // 8)
        ax.set_xticks(x[::step])
        ax.set_xticklabels([d.strftime("%d %b") for d in days][::step])
        legend = ax.legend(frameon=False, fontsize=9, loc="upper left", ncols=2)
        for text in legend.get_texts():
            text.set_color(theme.TEXT_MUTED)
    card.draw(render)


def draw_category_bars(card, categories, currency):
    """Horizontal bars: stock value (at cost) of each category."""
    if not categories or not any(c["value"] for c in categories):
        card.show_empty("No stock value yet.\nAdd products with a purchase price and stock.")
        return
    rows = categories[:8]

    def render(ax):
        ax.grid(axis="y", visible=False)
        ax.grid(axis="x", color=theme.BORDER, linewidth=0.6, alpha=0.6)
        positions = list(range(len(rows)))
        ax.barh(positions, [c["value"] for c in rows], color=theme.PRIMARY, height=0.6)
        ax.set_yticks(positions)
        ax.set_yticklabels([short(c["category"]) for c in rows])
        ax.invert_yaxis()
        ax.set_xlabel(currency, color=theme.TEXT_MUTED, fontsize=9)
    card.draw(render)
