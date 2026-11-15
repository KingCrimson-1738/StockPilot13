import customtkinter as ctk

import config
import theme
from background import run_async
from widgets.brand_panel import BrandPanel
from widgets.controls import Banner, entry, label, primary_button


class LoginPage(ctk.CTkFrame):
    def __init__(self, parent, app, notice=None):
        super().__init__(parent, fg_color=theme.BG, corner_radius=0)
        self.app = app
        self.grid_columnconfigure(0, weight=2, uniform="side")
        self.grid_columnconfigure(1, weight=3, uniform="side")
        self.grid_rowconfigure(0, weight=1)
        BrandPanel(self).grid(row=0, column=0, sticky="nsew")

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.grid(row=0, column=1)
        label(form, "Welcome back", 28, "bold").grid(row=0, column=0, sticky="w")
        label(form, "Log in to manage your inventory.", 14, color=theme.TEXT_MUTED).grid(row=1, column=0, sticky="w", pady=(4, 24))

        self.banner = Banner(form)
        self.banner.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        self.banner.hide()

        label(form, "Email", 12, color=theme.TEXT_MUTED).grid(row=3, column=0, sticky="w", pady=(0, 4))
        self.email = entry(form, "you@example.com", width=360)
        self.email.grid(row=4, column=0, sticky="ew")
        label(form, "Password", 12, color=theme.TEXT_MUTED).grid(row=5, column=0, sticky="w", pady=(14, 4))
        self.password = entry(form, "Your password", hide_text=True, width=360)
        self.password.grid(row=6, column=0, sticky="ew")

        self.login_button = primary_button(form, "Log in", self.submit, width=360)
        self.login_button.grid(row=7, column=0, sticky="ew", pady=(22, 0))

        footer = ctk.CTkFrame(form, fg_color="transparent")
        footer.grid(row=8, column=0, pady=(18, 0))
        label(footer, "New to StockPilot?", 13, color=theme.TEXT_MUTED).pack(side="left")
        ctk.CTkButton(
            footer, text="Create an account", width=10, fg_color="transparent", hover_color=theme.BG,
            text_color=theme.PRIMARY, font=theme.font(13, "bold"), command=app.show_register,
        ).pack(side="left", padx=4)
        label(form, f"Server: {config.API_URL}", 11, color=theme.TEXT_MUTED).grid(row=9, column=0, pady=(30, 0))
        if config.INSECURE:  # plain http to another computer: the password would be sent unencrypted
            label(form, "Warning: this address is not HTTPS, so your password is not encrypted on its way.", 11,
                  color=theme.WARNING, wraplength=360).grid(row=10, column=0, pady=(6, 0))

        if notice:
            self.banner.show(notice, "info")
        self.email.focus()
        self.password.bind("<Return>", lambda event: self.submit())
        self.email.bind("<Return>", lambda event: self.password.focus())

    def submit(self):
        email, password = self.email.get().strip(), self.password.get()
        if not email or not password:
            self.banner.show("Please enter your email and password.")
            return
        self.banner.hide()
        self.login_button.configure(state="disabled", text="Logging in…")
        run_async(
            self,
            work=lambda: self.app.session.api.login(email, password),
            on_done=self.app.start_session,
            on_error=self.failed,
        )

    def failed(self, error):
        self.login_button.configure(state="normal", text="Log in")
        self.banner.show(error.message)
