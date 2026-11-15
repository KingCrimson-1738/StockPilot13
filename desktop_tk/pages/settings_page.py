"""Settings: edit the business details and manage who has access (members)."""
from tkinter import messagebox

import customtkinter as ctk

import theme
from background import run_async
from widgets.business_form import BusinessForm
from widgets.controls import Banner, card, danger_button, entry, label, primary_button
from widgets.data_table import DataTable


class SettingsPage(ctk.CTkFrame):
    """A plain frame (so the shell can raise it) holding a scrollable area (so small windows still work)."""

    def __init__(self, parent, shell):
        super().__init__(parent, fg_color="transparent")
        self.shell = shell
        self.session = shell.session
        self.members = []  # same order as the rows in the members table
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.grid(row=0, column=0, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)
        self.build(self.body)

    def build(self, body):
        self.banner = Banner(body)
        self.banner.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self.banner.hide()

        # --- business details ---
        details = card(body)
        details.grid(row=1, column=0, sticky="ew", pady=(0, 20))
        details.grid_columnconfigure(0, weight=1)
        label(details, "Business details", 16, "bold", anchor="w").grid(row=0, column=0, sticky="w", padx=22, pady=(20, 0))
        self.owner_note = label(details, "", 12, color=theme.WARNING, anchor="w")
        self.owner_note.grid(row=1, column=0, sticky="w", padx=22)
        self.form = BusinessForm(details, "Save changes", self.save_details)
        self.form.grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 22))

        # --- members ---
        members_card = card(body)
        members_card.grid(row=2, column=0, sticky="ew")
        members_card.grid_columnconfigure(0, weight=1)
        label(members_card, "Members", 16, "bold", anchor="w").grid(row=0, column=0, sticky="w", padx=22, pady=(20, 4))
        label(members_card, "Owners manage the business and its members. Staff can view everything and record stock in and out.",
              12, color=theme.TEXT_MUTED, anchor="w").grid(row=1, column=0, sticky="w", padx=22, pady=(0, 12))
        self.table = DataTable(members_card, columns=[("NAME", 200, "w"), ("EMAIL", 280, "w"), ("ROLE", 100, "w")],
                               empty_text="No members found.", visible_rows=5)
        self.table.grid(row=2, column=0, sticky="ew", padx=22)

        self.owner_controls = ctk.CTkFrame(members_card, fg_color="transparent")
        self.owner_controls.grid(row=3, column=0, sticky="ew", padx=22, pady=(14, 22))
        self.owner_controls.grid_columnconfigure(0, weight=1)
        self.member_email = entry(self.owner_controls, "Email of a registered user to add as staff", width=10)
        self.member_email.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.add_button = primary_button(self.owner_controls, "Add staff", self.add_member, width=110)
        self.add_button.grid(row=0, column=1, padx=(0, 10))
        danger_button(self.owner_controls, "Remove selected", self.remove_member, width=150).grid(row=0, column=2)

    # ----- loading -----
    def refresh(self):
        business_id = self.session.business["id"]
        self.banner.hide()
        run_async(
            self,
            work=lambda: (self.session.api.get_business(business_id), self.session.api.list_members(business_id)),
            on_done=lambda result: self.show(business_id, *result),
            on_error=lambda error: self.shell.app.report_error(error, self.banner),
        )

    def show(self, business_id, business, members):
        if business_id != self.session.business["id"]:
            return
        self.shell.business_updated(business)  # keeps the header in step with the latest data
        is_owner = business["my_role"] == "owner"
        self.form.set_values(business)
        self.form.set_enabled(is_owner)
        self.owner_note.configure(text="" if is_owner else "Only the business owner can change these details.")
        if is_owner:
            self.owner_controls.grid()
        else:
            self.owner_controls.grid_remove()

        self.members = members
        self.table.set_rows([(m["full_name"], m["email"], m["role"].capitalize()) for m in members])

    # ----- actions (all owner-only; the server enforces this too) -----
    def save_details(self, form):
        try:
            values = form.get_values()
        except ValueError as problem:
            self.banner.show(str(problem))
            return
        business_id = self.session.business["id"]
        form.set_busy(True)
        run_async(
            self,
            work=lambda: self.session.api.update_business(business_id, values),
            on_done=self.details_saved,
            on_error=self.action_failed,
        )

    def details_saved(self, business):
        self.form.set_busy(False)
        self.shell.business_updated(business)
        self.banner.show("Business details saved.", "success")

    def add_member(self):
        email = self.member_email.get().strip()
        if not email:
            self.banner.show("Enter the email address of the person to add.")
            return
        business_id = self.session.business["id"]
        self.add_button.configure(state="disabled")
        run_async(
            self,
            work=lambda: self.session.api.add_member(business_id, email),
            on_done=self.member_added,
            on_error=self.action_failed,
        )

    def member_added(self, member):
        self.member_email.delete(0, "end")
        self.banner.show(f"{member['full_name']} was added as staff.", "success")
        self.refresh_members_only()

    def remove_member(self):
        index = self.table.selected_index()
        if index is None:
            self.banner.show("Select a member in the table first.")
            return
        member = self.members[index]
        if member["role"] == "owner":
            self.banner.show("The owner cannot be removed.")
            return
        if not messagebox.askyesno("Remove member", f"Remove {member['full_name']} from this business?"):
            return
        business_id = self.session.business["id"]
        run_async(
            self,
            work=lambda: self.session.api.remove_member(business_id, member["id"]),
            on_done=lambda _: self.member_removed(member),
            on_error=self.action_failed,
        )

    def member_removed(self, member):
        self.banner.show(f"{member['full_name']} was removed.", "success")
        self.refresh_members_only()

    def refresh_members_only(self):
        business_id = self.session.business["id"]
        run_async(
            self,
            work=lambda: self.session.api.list_members(business_id),
            on_done=lambda members: self.show_members(business_id, members),
            on_error=self.action_failed,
        )

    def show_members(self, business_id, members):
        if business_id != self.session.business["id"]:
            return
        self.members = members
        self.table.set_rows([(m["full_name"], m["email"], m["role"].capitalize()) for m in members])

    def action_failed(self, error):
        self.form.set_busy(False)
        self.add_button.configure(state="normal")
        self.shell.app.report_error(error, self.banner)
