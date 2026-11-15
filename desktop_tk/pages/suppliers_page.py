"""Suppliers: who the business buys from, and which products each one supplies."""
from tkinter import messagebox

import customtkinter as ctk

import theme
from background import run_async
from widgets.controls import Banner, danger_button, label, primary_button, secondary_button
from widgets.data_table import DataTable
from widgets.supplier_dialog import SupplierDialog


class SuppliersPage(ctk.CTkFrame):
    def __init__(self, parent, shell):
        super().__init__(parent, fg_color="transparent")
        self.shell, self.app, self.session = shell, shell.app, shell.session
        self.suppliers = []   # same order as the table rows
        self.supplied = []    # products of the selected supplier
        self.product_request = 0
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=3)
        self.grid_rowconfigure(4, weight=2)

        self.banner = Banner(self)
        self.banner.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.banner.hide()

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        bar.grid_columnconfigure(0, weight=1)
        self.count_label = label(bar, "", 13, color=theme.TEXT_MUTED, anchor="w")
        self.count_label.grid(row=0, column=0, sticky="w")
        primary_button(bar, "Add supplier", self.add, width=130).grid(row=0, column=1, padx=(10, 0))
        secondary_button(bar, "Edit", self.edit_selected, width=80).grid(row=0, column=2, padx=(10, 0))
        self.delete_button = danger_button(bar, "Delete", self.delete, width=90)
        self.delete_button.grid(row=0, column=3, padx=(10, 0))

        self.table = DataTable(
            self, columns=[("SUPPLIER", 190, "w"), ("CONTACT", 130, "w"), ("PHONE", 110, "w"),
                           ("EMAIL", 190, "w"), ("PRODUCTS", 80, "e")],
            empty_text="No suppliers yet.\nClick 'Add supplier' to record the first one.",
            visible_rows=6, on_select=self.row_selected, on_double_click=self.edit_at,
        )
        self.table.grid(row=2, column=0, sticky="nsew")

        self.products_title = label(self, "Select a supplier to see the products they supply.", 13, "bold", anchor="w")
        self.products_title.grid(row=3, column=0, sticky="w", pady=(16, 8))
        self.products_table = DataTable(
            self, columns=[("SKU", 110, "w"), ("PRODUCT", 260, "w"), ("STOCK", 80, "center"), ("STATUS", 90, "w")],
            empty_text="", visible_rows=4,
        )
        self.products_table.grid(row=4, column=0, sticky="nsew")

    # ----- loading -----
    def refresh(self):
        self.banner.hide()
        self.delete_button.grid() if self.session.is_owner else self.delete_button.grid_remove()
        self.load()

    def load(self):
        business_id = self.session.business["id"]
        run_async(
            self,
            work=lambda: self.session.api.list_suppliers(business_id),
            on_done=lambda suppliers: self.show(business_id, suppliers),
            on_error=lambda error: self.app.report_error(error, self.banner),
        )

    def show(self, business_id, suppliers):
        if business_id != self.session.business["id"]:
            return
        selected = self.suppliers[self.table.selected_index()]["id"] if self.table.selected_index() is not None else None
        self.suppliers = suppliers
        self.table.set_rows([(s["name"], s["contact_person"] or "—", s["phone"] or "—", s["email"] or "—", s["product_count"])
                             for s in suppliers])
        noun = "supplier" if len(suppliers) == 1 else "suppliers"
        self.count_label.configure(text=f"{len(suppliers)} {noun}")
        keep = next((i for i, s in enumerate(suppliers) if s["id"] == selected), None)
        if keep is not None:
            self.table.tree.selection_set(str(keep))
        else:
            self.show_supplied(None)

    # ----- the products of the selected supplier -----
    def row_selected(self, index):
        self.show_supplied(None if index is None else self.suppliers[index])

    def show_supplied(self, supplier):
        self.product_request += 1
        number = self.product_request
        if supplier is None:
            self.products_title.configure(text="Select a supplier to see the products they supply.")
            self.supplied = []
            self.products_table.set_rows([], empty_text="")
            return
        self.products_title.configure(text=f"Products supplied by {supplier['name']}")
        business_id = self.session.business["id"]
        run_async(
            self,
            work=lambda: self.session.api.list_products(business_id, supplier_id=supplier["id"], archived="all"),
            on_done=lambda products: self.show_products(number, business_id, products),
            on_error=lambda error: self.app.report_error(error, self.banner),
        )

    def show_products(self, number, business_id, products):
        if number != self.product_request or business_id != self.session.business["id"]:
            return
        status = {"ok": "OK", "low": "Low", "out": "Out"}
        rows = [(p["sku"], p["name"], p["quantity"], "Archived" if p["is_archived"] else status[p["stock_status"]]) for p in products]
        tags = ["muted" if p["is_archived"] else {"ok": None, "low": "low", "out": "out"}[p["stock_status"]] for p in products]
        self.products_table.set_rows(rows, tags, empty_text="No products use this supplier yet.\nChoose it when adding a product.")

    # ----- actions -----
    def selected_supplier(self):
        index = self.table.selected_index()
        if index is None:
            self.banner.show("Select a supplier in the table first.")
            return None
        return self.suppliers[index]

    def add(self):
        SupplierDialog(self.app, self.saved)

    def edit_selected(self):
        supplier = self.selected_supplier()
        if supplier:
            SupplierDialog(self.app, self.saved, supplier)

    def edit_at(self, index):
        if index is not None:
            SupplierDialog(self.app, self.saved, self.suppliers[index])

    def saved(self, supplier):
        self.banner.show(f"'{supplier['name']}' was saved.", "success")
        self.load()

    def delete(self):
        supplier = self.selected_supplier()
        if not supplier:
            return
        if not messagebox.askyesno("Delete supplier", f"Delete the supplier '{supplier['name']}'?"):
            return
        business_id = self.session.business["id"]
        run_async(
            self,
            work=lambda: self.session.api.delete_supplier(business_id, supplier["id"]),
            on_done=lambda _: self.deleted(supplier),
            on_error=lambda error: self.app.report_error(error, self.banner),
        )

    def deleted(self, supplier):
        self.banner.show(f"Supplier '{supplier['name']}' was deleted.", "success")
        self.load()
