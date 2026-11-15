"""The business details form. Used twice: to create a business and to edit one in Settings."""
import customtkinter as ctk

import theme
from widgets.controls import entry, label, primary_button


class BusinessForm(ctk.CTkFrame):
    def __init__(self, parent, submit_text, on_submit):
        super().__init__(parent, fg_color="transparent")
        self.on_submit = on_submit
        self._submit_text = submit_text
        self.grid_columnconfigure((0, 1), weight=1, uniform="half")
        self._hints = {}  # entry -> placeholder text, so we can bring the hint back after clearing

        self.name = self._field("Business name *", 0, 0, 2, "e.g. ABC Electronics")
        self.address = self._field("Address", 2, 0, 2, "Street, city")
        self.phone = self._field("Phone", 4, 0, 1, "Contact number")
        self.currency = self._field("Currency", 4, 1, 1, "INR")
        self.default_min_stock = self._field("Low-stock alert level", 6, 0, 1, "5")
        label(self, "Products at or below this level are flagged as low stock.", 11, color=theme.TEXT_MUTED, anchor="w") \
            .grid(row=8, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.description = self._field("Description", 9, 0, 2, "What does this business sell?")

        self.submit_button = primary_button(self, submit_text, self._submit, width=180)
        self.submit_button.grid(row=11, column=0, columnspan=2, sticky="w", pady=(18, 0))
        self.fields = [self.name, self.address, self.phone, self.currency, self.default_min_stock, self.description]

    def _field(self, title, row, column, span, placeholder):
        left_gap = 0 if column == 0 else 10
        label(self, title, 12, color=theme.TEXT_MUTED, anchor="w").grid(
            row=row, column=column, columnspan=span, sticky="w", padx=(left_gap, 0), pady=(10, 4))
        box = entry(self, placeholder, width=10)
        box.grid(row=row + 1, column=column, columnspan=span, sticky="ew", padx=(left_gap, 0))
        self._hints[box] = placeholder
        return box

    def get_values(self):
        """Returns the form as a dict ready for the API, or raises ValueError with a friendly message."""
        name = self.name.get().strip()
        if not name:
            raise ValueError("Please enter a business name.")
        currency = self.currency.get().strip().upper() or "INR"
        if len(currency) > 8:
            raise ValueError("Currency should be a short code such as INR or USD.")
        level_text = self.default_min_stock.get().strip() or "5"
        if not level_text.isdigit():
            raise ValueError("The low-stock alert level must be a whole number (0 or more).")

        def optional(box):
            return box.get().strip() or None

        return {
            "name": name, "address": optional(self.address), "phone": optional(self.phone),
            "currency": currency, "default_min_stock": int(level_text), "description": optional(self.description),
        }

    def set_values(self, business):
        """Fill the form from a business dict (or clear it when business is None)."""
        keys = ("name", "address", "phone", "currency", "default_min_stock", "description")
        for box, key in zip(self.fields, keys):
            box.delete(0, "end")
            value = business.get(key) if business else None
            if value is None:
                box.configure(placeholder_text=self._hints[box])  # shows the grey hint again
            else:
                box.insert(0, str(value))

    def set_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for box in self.fields:
            box.configure(state=state)
        self.submit_button.configure(state=state)

    def set_busy(self, busy):
        self.submit_button.configure(state="disabled" if busy else "normal", text="Please wait…" if busy else self._submit_text)

    def _submit(self):
        self.on_submit(self)
