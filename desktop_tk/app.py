"""The main window. It owns the Session and swaps whole screens in and out."""
import customtkinter as ctk

import theme
from pages.business_picker import BusinessPickerPage
from pages.login_page import LoginPage
from pages.register_page import RegisterPage
from pages.shell import MainShell
from session import Session
from widgets.data_table import setup_table_style


class App(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=theme.BG)
        ctk.set_appearance_mode("dark")
        self.title("StockPilot")
        self.geometry("1280x800")
        self.minsize(1000, 650)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        theme.choose_font_family()  # must run before any widget uses theme.font()
        setup_table_style()

        self.session = Session()
        self.screen = None
        self.show_login()

    # ----- switching screens -----
    def _show(self, screen):
        for child in self.winfo_children():  # close any open pop-up (e.g. the product form) too
            if isinstance(child, ctk.CTkToplevel):
                child.destroy()
        if self.screen is not None:
            self.screen.destroy()
        self.screen = screen
        screen.grid(row=0, column=0, sticky="nsew")

    def show_login(self, notice=None):
        self._show(LoginPage(self, self, notice))

    def show_register(self):
        self._show(RegisterPage(self, self))

    def show_picker(self):
        self._show(BusinessPickerPage(self, self))

    def open_business(self, business):
        self.session.business = business
        self._show(MainShell(self, self))

    # ----- login / logout -----
    def start_session(self, user):
        """Called after a successful login or registration."""
        self.session.user = user
        self.show_picker()

    def log_out(self):
        self.session.log_out()
        self.show_login()

    # ----- errors -----
    def report_error(self, error, banner):
        """If the token has expired, go back to login. Otherwise show the message on the screen's banner."""
        if error.status == 401 and self.session.api.token:
            self.session.log_out()
            self.show_login(notice="Your session expired. Please log in again.")
        else:
            banner.show(error.message, "error")
