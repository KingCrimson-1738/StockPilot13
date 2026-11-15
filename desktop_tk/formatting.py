"""Small helpers that turn raw API values into text for the screen."""
from datetime import datetime

TYPE_LABELS = {"in": "Stock in", "out": "Stock out", "adjust": "Adjustment"}


def money(amount, currency):
    return f"{currency} {amount:,.2f}"


def local_time(iso_text):
    """'2026-11-15T12:30:00+00:00' -> '15 Nov 18:00' in the computer's own time zone."""
    return datetime.fromisoformat(iso_text).astimezone().strftime("%d %b %H:%M")


def initials(full_name):
    parts = full_name.split()
    return "".join(p[0] for p in parts[:2]).upper() or "?"
