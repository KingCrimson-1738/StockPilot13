"""The add / edit supplier window."""
import customtkinter as ctk

import theme
from background import run_async
from widgets.controls import Banner, entry, label, primary_button, secondary_button
from widgets.modal import show_modal


class SupplierDialog(ctk.CTkToplevel):
    def __init__(self, app, on_saved, supplier=None):
        super().__init__(app, fg_color=theme.CARD)
        self.app, self.session, self.on_saved, self.supplier = app, app.session, on_saved, supplier
        self.business_id = self.session.business["id"]
        self.title("Edit supplier" if supplier else "Add supplier")
        self.resizable(False, False)
        self.transient(app)
        self.grid_columnconfigure((0, 1), weight=1, uniform="half")

        label(self, "Edit supplier" if supplier else "Add a supplier", 20, "bold", anchor="w") \
            .grid(row=0, column=0, columnspan=2, sticky="w", padx=28, pady=(24, 6))
        self.banner = Banner(self)
        self.banner.grid(row=1, column=0, columnspan=2, sticky="ew", padx=28, pady=(6, 0))
        self.banner.hide()

        self.name = self._field("Supplier name *", 2, 0, 2, "e.g. Volt Traders")
        self.contact = self._field("Contact person", 4, 0, 1, "Full name")
        self.phone = self._field("Phone", 4, 1, 1, "Contact number")
        self.email = self._field("Email", 6, 0, 2, "name@example.com")
        self.address = self._field("Address", 8, 0, 2, "Street, city")
        if supplier:
            for box, key in ((self.name, "name"), (self.contact, "contact_person"), (self.phone, "phone"),
                             (self.email, "email"), (self.address, "address")):
                if supplier[key]:
                    box.insert(0, supplier[key])

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=10, column=0, columnspan=2, sticky="e", padx=28, pady=(24, 24))
        secondary_button(buttons, "Cancel", self.destroy, width=100).pack(side="left", padx=(0, 10))
        self.save_button = primary_button(buttons, "Save supplier", self.save, width=140)
        self.save_button.pack(side="left")
        self.bind("<Escape>", lambda event: self.destroy())
        self.after(150, lambda: show_modal(self, self.app))

    def _field(self, title, row, column, span, placeholder):
        right_gap = 28 if column + span == 2 else 10
        left_gap = 28 if column == 0 else 10
        label(self, title, 12, color=theme.TEXT_MUTED, anchor="w").grid(
            row=row, column=column, columnspan=span, sticky="w", padx=(left_gap, right_gap), pady=(12, 4))
        box = entry(self, placeholder, width=10)
        box.grid(row=row + 1, column=column, columnspan=span, sticky="ew", padx=(left_gap, right_gap))
        return box

    def save(self):
        name = self.name.get().strip()
        if not name:
            self.banner.show("Please enter the supplier name.")
            return
        values = {"name": name, "contact_person": self.contact.get().strip(), "phone": self.phone.get().strip(),
                  "email": self.email.get().strip(), "address": self.address.get().strip()}  # blank -> null on the server
        self.banner.hide()
        self.save_button.configure(state="disabled", text="Saving…")
        api = self.session.api
        if self.supplier is None:
            work = lambda: api.create_supplier(self.business_id, values)
        else:
            work = lambda: api.update_supplier(self.business_id, self.supplier["id"], values)
        run_async(self, work, self.saved, self.failed)

    def saved(self, supplier):
        self.on_saved(supplier)
        self.destroy()

    def failed(self, error):
        self.save_button.configure(state="normal", text="Save supplier")
        self.app.report_error(error, self.banner)
