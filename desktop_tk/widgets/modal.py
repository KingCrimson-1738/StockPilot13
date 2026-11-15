"""Shared by every pop-up window: centre it over the main window and make it modal."""
import tkinter as tk


def show_modal(window, app):
    """Centre `window` over the main window, then grab input so the main window waits.
    Call it with window.after(150, ...) so the pop-up has finished drawing first."""
    try:
        window.update_idletasks()
        x = app.winfo_x() + (app.winfo_width() - window.winfo_width()) // 2
        y = app.winfo_y() + (app.winfo_height() - window.winfo_height()) // 3
        window.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        window.grab_set()
        window.focus_force()
    except tk.TclError:  # the window was closed before it appeared
        pass
