"""Line icons drawn with Pillow, so the project needs no image files (and no emoji).

Each icon is drawn on a 24 x 24 grid at 8x size and shrunk, which smooths the edges.
"""
import customtkinter as ctk
from PIL import Image, ImageDraw

import theme

SCALE = 8
_cache = {}


def _p(k, *points):
    return [v * k for v in points]


def _dashboard(d, k, c, w):
    for x, y in ((3, 3), (14, 3), (3, 14), (14, 14)):
        d.rounded_rectangle(_p(k, x, y, x + 7, y + 7), radius=1.5 * k, outline=c, width=w)


def _settings(d, k, c, w):  # three sliders
    for y, knob in ((6, 8), (12, 16), (18, 11)):
        d.line(_p(k, 3, y, knob - 3, y), fill=c, width=w)
        d.line(_p(k, knob + 3, y, 21, y), fill=c, width=w)
        d.ellipse(_p(k, knob - 2.5, y - 2.5, knob + 2.5, y + 2.5), outline=c, width=w)


def _logout(d, k, c, w):
    d.line(_p(k, 10, 4, 4, 4, 4, 20, 10, 20), fill=c, width=w, joint="curve")
    d.line(_p(k, 9, 12, 21, 12), fill=c, width=w)
    d.line(_p(k, 16, 7, 21, 12, 16, 17), fill=c, width=w, joint="curve")


def _building(d, k, c, w):
    d.rectangle(_p(k, 5, 3, 19, 21), outline=c, width=w)
    for x in (8.5, 13.5):
        for y in (7, 11):
            d.rectangle(_p(k, x, y, x + 2, y + 2), fill=c)
    d.rectangle(_p(k, 10, 16, 14, 21), fill=c)


def _users(d, k, c, w):
    d.ellipse(_p(k, 5.5, 4.5, 12.5, 11.5), outline=c, width=w)
    d.arc(_p(k, 2, 14, 16, 28), 180, 360, fill=c, width=w)
    d.ellipse(_p(k, 14, 5.5, 19.5, 11), outline=c, width=w)
    d.arc(_p(k, 14, 14, 24, 25), 200, 360, fill=c, width=w)


def _box(d, k, c, w):
    d.polygon(_p(k, 12, 3, 20, 7.5, 20, 16.5, 12, 21, 4, 16.5, 4, 7.5), outline=c, width=w)
    d.line(_p(k, 4, 7.5, 12, 12, 20, 7.5), fill=c, width=w, joint="curve")
    d.line(_p(k, 12, 12, 12, 21), fill=c, width=w)


def _layers(d, k, c, w):
    d.polygon(_p(k, 12, 3, 21, 8, 12, 13, 3, 8), outline=c, width=w)
    d.line(_p(k, 3, 12, 12, 17, 21, 12), fill=c, width=w, joint="curve")
    d.line(_p(k, 3, 16, 12, 21, 21, 16), fill=c, width=w, joint="curve")


def _wallet(d, k, c, w):
    d.rounded_rectangle(_p(k, 3, 6, 21, 19), radius=2.5 * k, outline=c, width=w)
    d.line(_p(k, 3, 10, 21, 10), fill=c, width=w)
    d.ellipse(_p(k, 15.5, 12.5, 18.5, 15.5), fill=c)


def _alert(d, k, c, w):
    d.polygon(_p(k, 12, 3, 22, 20, 2, 20), outline=c, width=w)
    d.line(_p(k, 12, 9, 12, 14), fill=c, width=w)
    d.ellipse(_p(k, 11, 16, 13, 18), fill=c)


def _ban(d, k, c, w):
    d.ellipse(_p(k, 3, 3, 21, 21), outline=c, width=w)
    d.line(_p(k, 6, 6, 18, 18), fill=c, width=w)


def _plus(d, k, c, w):
    d.line(_p(k, 12, 5, 12, 19), fill=c, width=w)
    d.line(_p(k, 5, 12, 19, 12), fill=c, width=w)


def _refresh(d, k, c, w):
    d.arc(_p(k, 4, 4, 20, 20), 40, 330, fill=c, width=w)
    d.polygon(_p(k, 21, 3, 21, 10, 14, 10), fill=c)


def _tag(d, k, c, w):
    d.polygon(_p(k, 3, 12, 12, 3, 21, 3, 21, 12, 12, 21), outline=c, width=w)
    d.ellipse(_p(k, 14.5, 6.5, 17.5, 9.5), fill=c)


def _swap(d, k, c, w):  # two opposite arrows
    d.line(_p(k, 4, 8, 20, 8), fill=c, width=w)
    d.line(_p(k, 16, 4, 20, 8, 16, 12), fill=c, width=w, joint="curve")
    d.line(_p(k, 20, 16, 4, 16), fill=c, width=w)
    d.line(_p(k, 8, 12, 4, 16, 8, 20), fill=c, width=w, joint="curve")


def _truck(d, k, c, w):
    d.rectangle(_p(k, 2, 6, 14, 17), outline=c, width=w)
    d.polygon(_p(k, 14, 9, 19, 9, 22, 13, 22, 17, 14, 17), outline=c, width=w)
    for x in (7, 18):
        d.ellipse(_p(k, x - 2.2, 16, x + 2.2, 20.4), fill=theme.SIDEBAR, outline=c, width=w)


def _clock(d, k, c, w):
    d.ellipse(_p(k, 3, 3, 21, 21), outline=c, width=w)
    d.line(_p(k, 12, 7, 12, 12, 16, 14), fill=c, width=w, joint="curve")


def _chart(d, k, c, w):  # three bars on a baseline
    d.line(_p(k, 3, 20, 21, 20), fill=c, width=w)
    for x, top in ((6, 12), (11, 5), (16, 9)):
        d.rectangle(_p(k, x - 1.5, top, x + 1.5, 20), outline=c, width=w)


DRAWERS = {
    "chart": _chart,
    "swap": _swap, "truck": _truck, "clock": _clock,
    "dashboard": _dashboard, "settings": _settings, "logout": _logout, "building": _building,
    "users": _users, "box": _box, "layers": _layers, "wallet": _wallet, "alert": _alert,
    "ban": _ban, "tag": _tag, "plus": _plus, "refresh": _refresh,
}


def get_icon(name, color=theme.TEXT_MUTED, size=20):
    """Returns a CTkImage for the named icon (cached, so each icon is drawn once)."""
    key = (name, color, size)
    if key not in _cache:
        pixels = size * SCALE
        k = pixels / 24
        image = Image.new("RGBA", (pixels, pixels), (0, 0, 0, 0))
        DRAWERS[name](ImageDraw.Draw(image), k, color, round(2 * k))
        image = image.resize((size * 2, size * 2), Image.LANCZOS)  # 2x for sharp high-DPI screens
        _cache[key] = ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
    return _cache[key]
