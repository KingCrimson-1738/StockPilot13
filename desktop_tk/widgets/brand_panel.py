import customtkinter as ctk

import icons
import theme
from widgets.controls import label


class BrandPanel(ctk.CTkFrame):
    """Left side of the login and register screens."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=theme.SIDEBAR, corner_radius=0)
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        logo = ctk.CTkFrame(inner, width=56, height=56, corner_radius=14, fg_color=theme.PRIMARY)
        logo.pack(anchor="w")
        logo.grid_propagate(False)
        ctk.CTkLabel(logo, text="", image=icons.get_icon("box", theme.TEXT, 30)).place(relx=0.5, rely=0.5, anchor="center")

        label(inner, "StockPilot", 34, "bold").pack(anchor="w", pady=(22, 4))
        label(inner, "Inventory control for every\nbusiness you run.", 16, color=theme.TEXT_MUTED, justify="left").pack(anchor="w")

        for text in ("Several businesses under one account", "Live stock levels and low-stock alerts", "Staff access with owner controls"):
            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(anchor="w", pady=(18, 0), fill="x")
            ctk.CTkFrame(row, width=8, height=8, corner_radius=4, fg_color=theme.PRIMARY).pack(side="left", padx=(0, 12))
            label(row, text, 13, color=theme.TEXT_MUTED).pack(side="left")
