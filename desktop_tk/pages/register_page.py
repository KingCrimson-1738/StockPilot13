import customtkinter as ctk

import theme
from background import run_async
from widgets.brand_panel import BrandPanel
from widgets.controls import Banner, entry, label, primary_button


class RegisterPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=theme.BG, corner_radius=0)
        self.app = app
        self.grid_columnconfigure(0, weight=2, uniform="side")
        self.grid_columnconfigure(1, weight=3, uniform="side")
        self.grid_rowconfigure(0, weight=1)
        BrandPanel(self).grid(row=0, column=0, sticky="nsew")

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.grid(row=0, column=1)
        label(form, "Create your account", 28, "bold").grid(row=0, column=0, sticky="w")
        label(form, "It takes a minute. You can add businesses afterwards.", 14, color=theme.TEXT_MUTED) \
            .grid(row=1, column=0, sticky="w", pady=(4, 20))

        self.banner = Banner(form)
        self.banner.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        self.banner.hide()

        self.full_name = self._field(form, "Full name", 3, "Your name")
        self.email = self._field(form, "Email", 5, "you@example.com")
        self.password = self._field(form, "Password (at least 8 characters)", 7, "Choose a password", hide_text=True)
        self.confirm = self._field(form, "Confirm password", 9, "Type it again", hide_text=True)

        self.register_button = primary_button(form, "Create account", self.submit, width=360)
        self.register_button.grid(row=11, column=0, sticky="ew", pady=(22, 0))

        footer = ctk.CTkFrame(form, fg_color="transparent")
        footer.grid(row=12, column=0, pady=(18, 0))
        label(footer, "Already have an account?", 13, color=theme.TEXT_MUTED).pack(side="left")
        ctk.CTkButton(
            footer, text="Log in", width=10, fg_color="transparent", hover_color=theme.BG,
            text_color=theme.PRIMARY, font=theme.font(13, "bold"), command=app.show_login,
        ).pack(side="left", padx=4)

        self.full_name.focus()
        self.confirm.bind("<Return>", lambda event: self.submit())

    def _field(self, form, title, row, placeholder, hide_text=False):
        label(form, title, 12, color=theme.TEXT_MUTED).grid(row=row, column=0, sticky="w", pady=(10, 4))
        box = entry(form, placeholder, hide_text=hide_text, width=360)
        box.grid(row=row + 1, column=0, sticky="ew")
        return box

    def submit(self):
        name, email = self.full_name.get().strip(), self.email.get().strip()
        password, confirm = self.password.get(), self.confirm.get()
        if not name or not email or not password:
            self.banner.show("Please fill in all the fields.")
        elif len(password) < 8:
            self.banner.show("Your password must be at least 8 characters long.")
        elif len(password) > 72:
            self.banner.show("Your password can be at most 72 characters long.")
        elif password != confirm:
            self.banner.show("The two passwords do not match.")
        else:
            self.banner.hide()
            self.register_button.configure(state="disabled", text="Creating account…")
            run_async(
                self,
                work=lambda: self.app.session.api.register(email, name, password),
                on_done=self.app.start_session,
                on_error=self.failed,
            )

    def failed(self, error):
        self.register_button.configure(state="normal", text="Create account")
        self.banner.show(error.message)
