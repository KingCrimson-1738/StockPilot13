"""The main window layout once a business is open:

    +---------+------------------------------------------+
    | sidebar |  header (page title, business switcher)  |
    |  nav    +------------------------------------------+
    | profile |  page content (dashboard, settings, ...) |
    +---------+------------------------------------------+
"""
import customtkinter as ctk

import icons
import theme
from formatting import initials
from pages.categories_page import CategoriesPage
from pages.dashboard_page import DashboardPage
from pages.history_page import HistoryPage
from pages.products_page import ProductsPage
from pages.reports_page import ReportsPage
from pages.restock_page import RestockPage
from pages.settings_page import SettingsPage
from pages.stock_page import StockPage
from pages.suppliers_page import SuppliersPage
from widgets.controls import label, secondary_button

ADD_BUSINESS_OPTION = "+  Add or manage businesses"

# (key, title in sidebar and header, icon name, page class). Later phases add more rows here.
PAGES = [
    ("dashboard", "Dashboard", "dashboard", DashboardPage),
    ("products", "Products", "box", ProductsPage),
    ("stock", "Stock", "swap", StockPage),
    ("restock", "Restock", "alert", RestockPage),
    ("suppliers", "Suppliers", "truck", SuppliersPage),
    ("categories", "Categories", "tag", CategoriesPage),
    ("history", "History", "clock", HistoryPage),
    ("reports", "Reports", "chart", ReportsPage),
    ("settings", "Settings", "settings", SettingsPage),
]


class MainShell(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=theme.BG, corner_radius=0)
        self.app = app
        self.session = app.session
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.nav_buttons = {}
        self._build_sidebar()

        right = ctk.CTkFrame(self, fg_color=theme.BG, corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        self._build_header(right)

        content = ctk.CTkFrame(right, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 24))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        self.pages = {}
        for key, title, icon, page_class in PAGES:
            page = page_class(content, self)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = page

        self.current_page = "dashboard"
        self.show_page("dashboard")

    # ----- sidebar -----
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=250, fg_color=theme.SIDEBAR, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(2, weight=1)

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="w", padx=22, pady=(26, 22))
        logo = ctk.CTkFrame(brand, width=36, height=36, corner_radius=10, fg_color=theme.PRIMARY)
        logo.pack(side="left")
        logo.grid_propagate(False)
        ctk.CTkLabel(logo, text="", image=icons.get_icon("box", theme.TEXT, 20)).place(relx=0.5, rely=0.5, anchor="center")
        label(brand, "StockPilot", 18, "bold").pack(side="left", padx=12)

        nav = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav.grid(row=1, column=0, sticky="ew", padx=14)
        nav.grid_columnconfigure(0, weight=1)
        for row, (key, title, icon, _) in enumerate(PAGES):
            button = ctk.CTkButton(
                nav, text=title, anchor="w", height=42, corner_radius=8, font=theme.font(13, "bold"),
                fg_color="transparent", hover_color=theme.CARD, text_color=theme.TEXT_MUTED,
                image=icons.get_icon(icon, theme.TEXT_MUTED, 20), compound="left",
                command=lambda k=key: self.show_page(k),
            )
            button.grid(row=row, column=0, sticky="ew", pady=3)
            self.nav_buttons[key] = (button, icon)

        profile = ctk.CTkFrame(sidebar, fg_color=theme.CARD, corner_radius=12)
        profile.grid(row=3, column=0, sticky="ew", padx=14, pady=16)
        profile.grid_columnconfigure(1, weight=1)
        user = self.session.user
        avatar = ctk.CTkFrame(profile, width=38, height=38, corner_radius=10, fg_color=theme.PRIMARY)
        avatar.grid(row=0, column=0, rowspan=2, padx=(12, 10), pady=12)
        avatar.grid_propagate(False)
        label(avatar, initials(user["full_name"]), 13, "bold").place(relx=0.5, rely=0.5, anchor="center")
        label(profile, user["full_name"], 13, "bold", anchor="w").grid(row=0, column=1, sticky="sw", padx=(0, 8), pady=(12, 0))
        label(profile, user["email"], 11, color=theme.TEXT_MUTED, anchor="w").grid(row=1, column=1, sticky="nw", padx=(0, 8), pady=(0, 12))
        secondary_button(profile, "Log out", self.app.log_out, width=10, icon=icons.get_icon("logout", theme.TEXT, 18)) \
            .grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))

    # ----- header -----
    def _build_header(self, parent):
        header = ctk.CTkFrame(parent, height=76, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28)
        header.grid_columnconfigure(0, weight=1)
        self.title = label(header, "", 24, "bold", anchor="w")
        self.title.grid(row=0, column=0, sticky="w", pady=22)

        self.role_badge = ctk.CTkLabel(header, text="", font=theme.font(11, "bold"), corner_radius=6, width=60, height=26)
        self.role_badge.grid(row=0, column=1, padx=(0, 12))
        self.business_menu = ctk.CTkOptionMenu(
            header, values=[""], command=self.switch_business, width=240, height=38, corner_radius=8,
            fg_color=theme.CARD, button_color=theme.CARD, button_hover_color=theme.BORDER,
            dropdown_fg_color=theme.CARD, dropdown_hover_color=theme.PRIMARY, dropdown_text_color=theme.TEXT,
            text_color=theme.TEXT, font=theme.font(13, "bold"), dropdown_font=theme.font(13),
        )
        self.business_menu.grid(row=0, column=2)
        self.reload_business_menu()

    def reload_business_menu(self):
        """Fills the business switcher from session.businesses and selects the open business."""
        names = [b["name"] for b in self.session.businesses]
        self.menu_labels = {}
        for business in self.session.businesses:
            text = business["name"] if names.count(business["name"]) == 1 else f"{business['name']} (#{business['id']})"
            self.menu_labels[text] = business
        current = self.session.business
        current_label = next(text for text, b in self.menu_labels.items() if b["id"] == current["id"])
        self.business_menu.configure(values=list(self.menu_labels) + [ADD_BUSINESS_OPTION])
        self.business_menu.set(current_label)

        is_owner = current["my_role"] == "owner"
        self.role_badge.configure(
            text="Owner" if is_owner else "Staff",
            text_color=theme.PRIMARY if is_owner else theme.WARNING,
            fg_color=theme.blend(theme.PRIMARY if is_owner else theme.WARNING, theme.BG, 0.16),
        )

    def switch_business(self, chosen):
        if chosen == ADD_BUSINESS_OPTION:
            self.app.show_picker()
            return
        self.session.business = self.menu_labels[chosen]
        self.reload_business_menu()
        self.pages[self.current_page].refresh()

    def business_updated(self, business):
        """Called by Settings after an edit, so the switcher shows the new name."""
        self.session.businesses = [business if b["id"] == business["id"] else b for b in self.session.businesses]
        self.session.business = business
        self.reload_business_menu()

    # ----- pages -----
    def show_page(self, key):
        self.current_page = key
        for page_key, (button, icon) in self.nav_buttons.items():
            active = page_key == key
            button.configure(
                fg_color=theme.blend(theme.PRIMARY, theme.SIDEBAR, 0.18) if active else "transparent",
                text_color=theme.PRIMARY if active else theme.TEXT_MUTED,
                image=icons.get_icon(icon, theme.PRIMARY if active else theme.TEXT_MUTED, 20),
            )
        self.title.configure(text=next(title for k, title, _, _ in PAGES if k == key))
        self.pages[key].tkraise()
        self.pages[key].refresh()
