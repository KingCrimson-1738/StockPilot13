"""Design tokens: every colour and font lives here, so the whole look can be changed in one file."""
import customtkinter as ctk

BG = "#0B1120"          # window background
SIDEBAR = "#111827"
CARD = "#1E293B"
INPUT_BG = "#0F172A"
BORDER = "#334155"

PRIMARY = "#3B82F6"
PRIMARY_HOVER = "#2563EB"
TEXT = "#F8FAFC"
TEXT_MUTED = "#94A3B8"

SUCCESS = "#22C55E"
WARNING = "#F59E0B"
DANGER = "#EF4444"
DANGER_HOVER = "#DC2626"

FONT_FAMILY = "Segoe UI"  # Windows UI font. choose_font_family() swaps it if it is not installed.
FONT_CHOICES = ("Segoe UI", "Helvetica Neue", "Roboto", "DejaVu Sans", "Arial", "Helvetica")


def choose_font_family():
    """Use the first font from FONT_CHOICES that this computer has (needs the main window to exist)."""
    global FONT_FAMILY
    from tkinter import font as tk_font
    installed = set(tk_font.families())
    FONT_FAMILY = next((name for name in FONT_CHOICES if name in installed), "TkDefaultFont")


def font(size=13, weight="normal"):
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


def blend(color, background, amount):
    """Mix `color` into `background` (amount 0..1). Used for soft tinted backgrounds."""
    c = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(background[i:i + 2], 16) for i in (1, 3, 5)]
    mixed = [round(b[i] + (c[i] - b[i]) * amount) for i in range(3)]
    return "#{:02X}{:02X}{:02X}".format(*mixed)
