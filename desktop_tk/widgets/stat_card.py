import customtkinter as ctk

import icons
import theme
from widgets.controls import label


class StatCard(ctk.CTkFrame):
    """One number on the dashboard: icon, title and value."""

    def __init__(self, parent, title, icon_name, accent):
        super().__init__(parent, fg_color=theme.CARD, corner_radius=12)
        self.grid_columnconfigure(1, weight=1)

        badge = ctk.CTkFrame(self, width=40, height=40, corner_radius=10, fg_color=theme.blend(accent, theme.CARD, 0.18))
        badge.grid(row=0, column=0, rowspan=2, padx=(16, 12), pady=16)
        badge.grid_propagate(False)
        ctk.CTkLabel(badge, text="", image=icons.get_icon(icon_name, accent, 20)).place(relx=0.5, rely=0.5, anchor="center")

        label(self, title, 12, color=theme.TEXT_MUTED, anchor="w").grid(row=0, column=1, sticky="sw", padx=(0, 12), pady=(14, 0))
        self.value = label(self, "…", 20, "bold", anchor="w")
        self.value.grid(row=1, column=1, sticky="nw", padx=(0, 12), pady=(0, 14))

    def set_value(self, text, color=theme.TEXT):
        self.value.configure(text=text, text_color=color)

    def set_loading(self):
        self.set_value("…", theme.TEXT_MUTED)
