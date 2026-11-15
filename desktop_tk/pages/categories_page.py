"""Categories: each business builds its own list. Nothing is built in."""
from tkinter import messagebox

import customtkinter as ctk

import theme
from background import run_async
from widgets.controls import Banner, danger_button, entry, label, primary_button, secondary_button
from widgets.data_table import DataTable


NAME_HINT = "Category name, e.g. Cables"


class CategoriesPage(ctk.CTkFrame):
    def __init__(self, parent, shell):
        super().__init__(parent, fg_color="transparent")
        self.shell, self.app, self.session = shell, shell.app, shell.session
        self.categories = []  # same order as the table rows
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.banner = Banner(self)
        self.banner.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.banner.hide()

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        bar.grid_columnconfigure(0, weight=1)
        self.name = entry(bar, NAME_HINT, width=200)
        self.name.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.name.bind("<Return>", lambda event: self.add())
        primary_button(bar, "Add category", self.add, width=140).grid(row=0, column=1, padx=(0, 10))
        secondary_button(bar, "Rename selected", self.rename, width=160).grid(row=0, column=2, padx=(0, 10))
        self.delete_button = danger_button(bar, "Delete selected", self.delete, width=150)
        self.delete_button.grid(row=0, column=3)

        self.table = DataTable(
            self, columns=[("CATEGORY", 300, "w"), ("PRODUCTS", 100, "e")],
            empty_text="No categories yet.\nType a name above and click 'Add category'.",
            on_select=self.row_selected,
        )
        self.table.grid(row=2, column=0, sticky="nsew")
        label(self, "Select a row to rename it, then type the new name above. "
                    "A category that still has products cannot be deleted.",
              12, color=theme.TEXT_MUTED, anchor="w").grid(row=3, column=0, sticky="w", pady=(10, 0))

    def refresh(self):
        self.banner.hide()
        if self.session.is_owner:
            self.delete_button.grid()
        else:
            self.delete_button.grid_remove()
        self.load()

    def load(self):
        business_id = self.session.business["id"]
        run_async(
            self,
            work=lambda: self.session.api.list_categories(business_id),
            on_done=lambda categories: self.show(business_id, categories),
            on_error=lambda error: self.app.report_error(error, self.banner),
        )

    def show(self, business_id, categories):
        if business_id != self.session.business["id"]:
            return
        self.categories = categories
        self.table.set_rows([(c["name"], c["product_count"]) for c in categories])

    def row_selected(self, index):
        if index is not None:  # copy the name into the box so it can be edited
            self.name.delete(0, "end")
            self.name.insert(0, self.categories[index]["name"])

    def selected_category(self):
        index = self.table.selected_index()
        if index is None:
            self.banner.show("Select a category in the table first.")
            return None
        return self.categories[index]

    def _send(self, work, success_text):
        run_async(self, work, lambda _: self.done(success_text), lambda error: self.app.report_error(error, self.banner))

    def done(self, success_text):
        self.banner.show(success_text, "success")
        self.name.delete(0, "end")  # clear the box only when the action worked, so a typo is not lost
        self.name.configure(placeholder_text=NAME_HINT)  # brings the grey hint back
        self.load()

    def add(self):
        name = self.name.get().strip()
        if not name:
            self.banner.show("Type a category name first.")
            return
        business_id = self.session.business["id"]
        self._send(lambda: self.session.api.create_category(business_id, name), f"Category '{name}' was added.")

    def rename(self):
        category = self.selected_category()
        name = self.name.get().strip()
        if not category:
            return
        if not name:
            self.banner.show("Type the new name first.")
            return
        business_id = self.session.business["id"]
        self._send(lambda: self.session.api.rename_category(business_id, category["id"], name), f"Renamed to '{name}'.")

    def delete(self):
        category = self.selected_category()
        if not category:
            return
        if not messagebox.askyesno("Delete category", f"Delete the category '{category['name']}'?"):
            return
        business_id = self.session.business["id"]
        self._send(lambda: self.session.api.delete_category(business_id, category["id"]), f"Category '{category['name']}' was deleted.")
