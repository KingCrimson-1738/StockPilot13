"""A dark data table (ttk.Treeview, which CustomTkinter does not provide) with an empty state."""
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

import theme


def setup_table_style():
    """Call once at start-up. Gives every table the dark StockPilot look."""
    style = ttk.Style()
    style.theme_use("clam")
    style.configure(
        "Stock.Treeview", background=theme.CARD, fieldbackground=theme.CARD, foreground=theme.TEXT,
        borderwidth=0, rowheight=36, font=(theme.FONT_FAMILY, 11),
    )
    style.map("Stock.Treeview", background=[("selected", theme.PRIMARY)], foreground=[("selected", theme.TEXT)])
    style.configure(
        "Stock.Treeview.Heading", background=theme.SIDEBAR, foreground=theme.TEXT_MUTED, relief="flat",
        borderwidth=0, padding=(4, 8), font=(theme.FONT_FAMILY, 10, "bold"),
    )
    style.map("Stock.Treeview.Heading", background=[("active", theme.SIDEBAR)])
    style.layout("Stock.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])  # no outer border


class DataTable(ctk.CTkFrame):
    """columns = [(heading, width, anchor), ...]. Fill it with set_rows([(a, b, c), ...]).

    on_select(index_or_None) is called when the selection changes; on_double_click(index) on a double click.
    set_rows(rows, tags) can colour a row: tags[i] is "low" (amber), "out" (red), "muted" (grey) or None.
    """

    def __init__(self, parent, columns, empty_text, visible_rows=10, on_select=None, on_double_click=None):
        super().__init__(parent, fg_color=theme.CARD, corner_radius=12)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        names = [f"c{i}" for i in range(len(columns))]
        self.tree = ttk.Treeview(self, columns=names, show="headings", style="Stock.Treeview", selectmode="browse",
                                 height=visible_rows)
        for name, (heading, width, anchor) in zip(names, columns):
            self.tree.heading(name, text=heading, anchor=anchor)
            self.tree.column(name, width=width, minwidth=50, anchor=anchor, stretch=True)
        self.tree.tag_configure("low", foreground=theme.WARNING)
        self.tree.tag_configure("out", foreground=theme.DANGER)
        self.tree.tag_configure("muted", foreground=theme.TEXT_MUTED)

        scrollbar = ctk.CTkScrollbar(self, command=self.tree.yview, fg_color=theme.CARD)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=6)

        if on_select:
            self.tree.bind("<<TreeviewSelect>>", lambda event: on_select(self.selected_index()))
        if on_double_click:
            self.tree.bind("<Double-1>", lambda event: on_double_click(self.selected_index()))

        self.empty_label = ctk.CTkLabel(
            self, text=empty_text, font=theme.font(13), text_color=theme.TEXT_MUTED, fg_color=theme.CARD, justify="center",
        )

    def set_rows(self, rows, tags=None, empty_text=None):
        self.tree.delete(*self.tree.get_children())
        for index, row in enumerate(rows):
            row_tag = tags[index] if tags and tags[index] else ""
            self.tree.insert("", tk.END, iid=str(index), values=row, tags=(row_tag,) if row_tag else ())
        if empty_text:
            self.empty_label.configure(text=empty_text)
        if rows:
            self.empty_label.place_forget()
        else:
            self.empty_label.place(relx=0.5, rely=0.55, anchor="center")

    def selected_index(self):
        """Position (0, 1, 2...) of the selected row, or None."""
        selection = self.tree.selection()
        return int(selection[0]) if selection else None
