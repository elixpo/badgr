"""Shared UI widgets used across Oreo OS apps.

Goal: every app has the same visual chrome (header bar, hint footer, panel
backgrounds) so the OS feels cohesive. Apps just call:

    from oreoOS import widgets
    widgets.draw_header(d, "SETTINGS")
    widgets.draw_hint  (d, "A=select  HOME=back")

and the look is consistent.
"""

from oreoOS import api, pixelfont
from oreoOS import theme

try:
    import time as _time
    _ticks_ms = _time.ticks_ms
    _ticks_diff = _time.ticks_diff
except (ImportError, AttributeError):
    import time as _time
    _ticks_ms = lambda: int(_time.time() * 1000)
    _ticks_diff = lambda a, b: a - b

HEADER_H = 26
HINT_H   = 16

# Forest-green header for the home screen (matches the bg image's tones).
HEADER_HOME_BG = api.rgb(46, 102,  74)

# ── status bar cache & polling ────────────────────────────────────────────────
_STATUS_POLL_MS = 2000
_status_cache = {
    "wifi": False,
    "bt": False,
    "battery_pct": 85,
    "last_ms": None,
    "time_str": "12:00"
}


def _poll_status():
    """Refresh the cached status bar indicators (WiFi, BT, Battery, Clock)."""
    now = _ticks_ms() if _time else 0
    last = _status_cache["last_ms"]
    if last is not None and _time and _ticks_diff(now, last) < _STATUS_POLL_MS:
        return _status_cache

    try:
        from oreoOS import timeutil
        h, m, *_ = timeutil.now()
        _status_cache["time_str"] = "%02d:%02d" % (h, m)
    except Exception:
        pass

    try:
        from oreoWare import wifi as _w
        _status_cache["wifi"] = bool(_w.is_connected())
    except Exception:
        pass

    try:
        from oreoWare import bt as _b
        _status_cache["bt"] = bool(_b.is_active())
    except Exception:
        pass

    try:
        from oreoWare import battery as _bat
        _status_cache["battery_pct"] = int(_bat.read_percent())
    except Exception:
        pass

    _status_cache["last_ms"] = now
    return _status_cache


def _load_status_icon(name):
    """Try to load a pre-baked 13×13 status icon. Returns (data,w,h) or None."""
    try:
        mod = __import__("assets.status.optimized.%s" % name,
                         None, None, ["DATA", "W", "H"])
        return (mod.DATA, mod.W, mod.H)
    except Exception:
        return None


def _icon_wifi(d, x, y, connected=False):
    name = "wifi" if connected else "wifi_disabled"
    icon = _load_status_icon(name)
    if icon:
        d.blit(icon[0], x, y, icon[1], icon[2])
        return
    c = api.WHITE if connected else theme.MUTED
    d.rect(x + 5, y + 10, 3, 2, c, fill=True)
    d.rect(x + 3, y + 7,  7, 2, c, fill=True)
    d.rect(x + 1, y + 4, 11, 2, c, fill=True)
    if not connected:
        d.line(x + 11, y, x + 1, y + 11, api.rgb(240, 60, 60))


def _icon_bt(d, x, y, active=False):
    name = "bluetooth" if active else "bluetooth_disabled"
    icon = _load_status_icon(name)
    if icon:
        d.blit(icon[0], x, y, icon[1], icon[2])
        return
    c = api.WHITE if active else theme.MUTED
    d.rect(x + 5, y + 1,  2, 11, c, fill=True)
    d.rect(x + 7, y + 3,  2,  2, c, fill=True)
    d.rect(x + 5, y + 5,  2,  2, c, fill=True)
    d.rect(x + 7, y + 7,  2,  2, c, fill=True)
    d.rect(x + 5, y + 9,  2,  2, c, fill=True)
    d.rect(x + 2, y + 3,  3,  2, c, fill=True)
    d.rect(x + 2, y + 8,  3,  2, c, fill=True)
    if not active:
        d.line(x + 11, y, x + 1, y + 11, api.rgb(240, 60, 60))


def _icon_battery(d, x, y, pct=85):
    d.rect(x,      y,     20, 10, api.WHITE, fill=False)
    d.rect(x + 20, y + 3,  2,  4, api.WHITE, fill=True)
    filled = max(1, min(18, int((pct / 100) * 18)))
    d.rect(x + 1,  y + 1, filled, 8, api.WHITE, fill=True)


# Lazy-loaded title font (Pixelify Sans 16)
_TITLE_FONT = None


def _title_font():
    global _TITLE_FONT
    if _TITLE_FONT is None:
        try:
            _TITLE_FONT = pixelfont.load("pixelify_16")
        except (ImportError, AttributeError):
            _TITLE_FONT = False
    return _TITLE_FONT if _TITLE_FONT else None


def draw_header(d, title=None, color=None, accent=None):
    """Consistent OS status bar with Pixelify Sans title and full status cluster.

    color  : status bar bg colour (default theme.STATUS_BG)
    accent : 1-px line under the header (default theme.PRIMARY)
    """
    SW = api.SCREEN_W
    bg = color  or theme.STATUS_BG
    ac = accent or theme.PRIMARY
    d.rect(0, 0, SW, HEADER_H, bg, fill=True)
    d.rect(0, HEADER_H - 1, SW, 1, ac, fill=True)

    status = _poll_status()

    # Left: Live Clock
    time_str = status.get("time_str", "12:00")
    d.text(time_str, 6, (HEADER_H - 8) // 2 + 1, api.WHITE)

    # Center: Pixelify Sans 16 Title with extra top padding
    if title:
        title_str = str(title).strip().upper()
        pf = _title_font()
        if pf:
            tw = pf.measure(title_str)
            pf.text(d, title_str, (SW - tw) // 2, (HEADER_H - pf.h) // 2 + 1, api.WHITE)
        else:
            tw = len(title_str) * 8
            d.text(title_str, (SW - tw) // 2, (HEADER_H - 8) // 2 + 1, api.WHITE)

    # Right: Full OS Status Cluster (WiFi + BT + Battery % + Battery Icon)
    right_pad = 6
    bat_w     = 22
    icon_w    = 13
    gap       = 4

    pct_str = "%d%%" % status.get("battery_pct", 85)
    text_w  = len(pct_str) * 8

    bat_x   = SW - right_pad - bat_w
    pct_x   = bat_x - gap - text_w
    bt_x    = pct_x - gap - icon_w
    wifi_x  = bt_x  - gap - icon_w

    icon_y = (HEADER_H - icon_w) // 2 + 1
    text_y = (HEADER_H - 8) // 2 + 1
    bat_y  = (HEADER_H - 10) // 2 + 1

    _icon_wifi   (d, wifi_x, icon_y, connected=status.get("wifi", False))
    _icon_bt     (d, bt_x,   icon_y, active=status.get("bt", False))
    d.text(pct_str, pct_x, text_y, api.WHITE)
    _icon_battery(d, bat_x, bat_y, pct=status.get("battery_pct", 85))


def draw_hint(d, text, color=None):
    """Small grey hint text at the very bottom of the screen.

    Use for "press X for Y" prompts so apps don't have to handcode the bar.
    """
    SW = api.SCREEN_W
    SH = api.SCREEN_H
    y  = SH - HINT_H
    d.rect(0, y, SW, HINT_H, theme.DOCK_BG, fill=True)
    tx = (SW - len(text) * 8) // 2
    d.text(text, tx, y + 4, color or theme.TEXT_BRIGHT)


def draw_panel(d, x, y, w, h, color=None, border=True):
    """Filled panel + optional accent border. Useful for cards / dialogs."""
    fill_color = color or theme.CARD
    d.rect(x, y, w, h, fill_color, fill=True)
    if border:
        d.rect(x, y, w, 1, theme.PRIMARY, fill=True)
        d.rect(x, y + h - 1, w, 1, theme.PRIMARY, fill=True)


def play_area():
    """(x, y, w, h) of the screen region between header and hint bar."""
    SW = api.SCREEN_W
    SH = api.SCREEN_H
    return (0, HEADER_H, SW, SH - HEADER_H - HINT_H)
