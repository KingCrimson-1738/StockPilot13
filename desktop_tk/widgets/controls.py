"""Basic building blocks (label, text box, buttons, message banner) styled once, used everywhere."""
import customtkinter as ctk

import theme


def label(parent, text, size=13, weight="normal", color=theme.TEXT, **options):
    return ctk.CTkLabel(parent, text=text, font=theme.font(size, weight), text_color=color, **options)


def entry(parent, placeholder="", hide_text=False, width=280):
    return ctk.CTkEntry(
        parent, placeholder_text=placeholder, show="•" if hide_text else "", width=width, height=40,
        corner_radius=8, fg_color=theme.INPUT_BG, border_color=theme.BORDER, border_width=1,
        text_color=theme.TEXT, placeholder_text_color=theme.TEXT_MUTED, font=theme.font(13),
    )


def _button(parent, text, command, width, fg, hover, text_color, icon, border=0):
    return ctk.CTkButton(
        parent, text=text, command=command, width=width, height=40, corner_radius=8,
        fg_color=fg, hover_color=hover, text_color=text_color, border_width=border,
        border_color=theme.BORDER, font=theme.font(13, "bold"), image=icon, compound="left",
    )


def primary_button(parent, text, command, width=140, icon=None):
    return _button(parent, text, command, width, theme.PRIMARY, theme.PRIMARY_HOVER, theme.TEXT, icon)


def secondary_button(parent, text, command, width=140, icon=None):
    return _button(parent, text, command, width, "transparent", theme.CARD, theme.TEXT, icon, border=1)


def danger_button(parent, text, command, width=140, icon=None):
    return _button(parent, text, command, width, theme.DANGER, theme.DANGER_HOVER, theme.TEXT, icon)


def card(parent, **options):
    return ctk.CTkFrame(parent, fg_color=theme.CARD, corner_radius=12, **options)


class Banner(ctk.CTkFrame):
    """A message strip (error / success / info). Place it with .grid(); it hides itself when empty.

    banner.show("Saved", "success") - success messages disappear after 4 seconds.
    """
    COLORS = {"error": theme.DANGER, "success": theme.SUCCESS, "info": theme.PRIMARY, "warning": theme.WARNING}

    def __init__(self, parent):
        super().__init__(parent, corner_radius=8, border_width=1)
        self.message = ctk.CTkLabel(self, text="", font=theme.font(13), anchor="w", justify="left")
        self.message.pack(fill="both", expand=True, padx=14, pady=10)
        self._hide_job = None
        self.bind("<Configure>", self._wrap_text)

    def _wrap_text(self, event):
        self.message.configure(wraplength=max(event.width - 40, 100))

    def show(self, text, kind="error"):
        color = self.COLORS[kind]
        self.configure(fg_color=theme.blend(color, theme.BG, 0.14), border_color=theme.blend(color, theme.BG, 0.5))
        self.message.configure(text=text, text_color=color)
        self.grid()
        if self._hide_job:
            self.after_cancel(self._hide_job)
            self._hide_job = None
        if kind == "success":
            self._hide_job = self.after(4000, self.hide)

    def hide(self):
        self.grid_remove()
