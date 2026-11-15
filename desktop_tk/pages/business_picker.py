"""Shown after login (and from the 'Add or manage businesses' menu entry):
choose a business to open, or create a new one."""
import customtkinter as ctk

import icons
import theme
from background import run_async
from widgets.business_form import BusinessForm
from widgets.controls import Banner, card, label, primary_button, secondary_button


class BusinessPickerPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=theme.BG, corner_radius=0)
        self.app = app
        self.session = app.session
        self.grid_columnconfigure((0, 1), weight=1, uniform="half")
        self.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=40, pady=(32, 0))
        top.grid_columnconfigure(0, weight=1)
        label(top, f"Hello, {self.session.user['full_name'].split()[0]}", 28, "bold", anchor="w").grid(row=0, column=0, sticky="w")
        label(top, "Choose a business to work on, or create a new one.", 14, color=theme.TEXT_MUTED, anchor="w") \
            .grid(row=1, column=0, sticky="w", pady=(4, 0))
        secondary_button(top, "Log out", app.log_out, width=110, icon=icons.get_icon("logout", theme.TEXT, 18)).grid(row=0, column=1, rowspan=2)

        self.banner = Banner(self)
        self.banner.grid(row=1, column=0, columnspan=2, sticky="ew", padx=40, pady=(16, 0))
        self.banner.hide()

        # left: the user's businesses
        left = card(self)
        left.grid(row=2, column=0, sticky="nsew", padx=(40, 12), pady=24)
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)
        label(left, "Your businesses", 16, "bold", anchor="w").grid(row=0, column=0, sticky="w", padx=22, pady=(20, 8))
        self.list_area = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.list_area.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 12))
        self.list_area.grid_columnconfigure(0, weight=1)

        # right: create a business
        right = card(self)
        right.grid(row=2, column=1, sticky="nsew", padx=(12, 40), pady=24)
        right.grid_columnconfigure(0, weight=1)
        label(right, "Create a new business", 16, "bold", anchor="w").grid(row=0, column=0, sticky="w", padx=22, pady=(20, 0))
        self.form = BusinessForm(right, "Create business", self.create)
        self.form.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 22))

        self.load()

    # ----- loading the list -----
    def load(self):
        self._show_message("Loading your businesses…")
        run_async(self, self.session.api.list_businesses, self.show_businesses, self.load_failed)

    def load_failed(self, error):
        self._show_message("Could not load your businesses.")
        self.app.report_error(error, self.banner)

    def _show_message(self, text):
        for child in self.list_area.winfo_children():
            child.destroy()
        label(self.list_area, text, 13, color=theme.TEXT_MUTED, justify="center").grid(row=0, column=0, pady=60)

    def show_businesses(self, businesses):
        self.session.businesses = businesses
        for child in self.list_area.winfo_children():
            child.destroy()
        if not businesses:
            self._show_message("You don't have any business yet.\nCreate your first one using the form.")
            return
        for row, business in enumerate(businesses):
            self._business_row(row, business)

    def _business_row(self, row, business):
        item = ctk.CTkFrame(self.list_area, fg_color=theme.INPUT_BG, corner_radius=10)
        item.grid(row=row, column=0, sticky="ew", pady=5)
        item.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(item, text="", image=icons.get_icon("building", theme.PRIMARY, 24)).grid(row=0, column=0, rowspan=2, padx=16, pady=14)
        label(item, business["name"], 14, "bold", anchor="w").grid(row=0, column=1, sticky="sw", pady=(12, 0))
        role = "Owner" if business["my_role"] == "owner" else "Staff"
        detail = role + (f"  ·  {business['address']}" if business["address"] else "")
        label(item, detail, 12, color=theme.TEXT_MUTED, anchor="w").grid(row=1, column=1, sticky="nw", pady=(0, 12))
        primary_button(item, "Open", lambda b=business: self.app.open_business(b), width=80).grid(row=0, column=2, rowspan=2, padx=14)

    # ----- creating a business -----
    def create(self, form):
        try:
            values = form.get_values()
        except ValueError as problem:
            self.banner.show(str(problem))
            return
        self.banner.hide()
        form.set_busy(True)
        was_first = not self.session.businesses
        run_async(
            self,
            work=lambda: self.session.api.create_business(values),
            on_done=lambda business: self.created(business, was_first),
            on_error=self.create_failed,
        )

    def created(self, business, was_first):
        self.form.set_busy(False)
        self.form.set_values(None)
        if was_first:  # the user's first business: go straight in
            self.session.businesses = [business]
            self.app.open_business(business)
        else:
            self.banner.show(f"'{business['name']}' was created.", "success")
            self.load()

    def create_failed(self, error):
        self.form.set_busy(False)
        self.app.report_error(error, self.banner)
