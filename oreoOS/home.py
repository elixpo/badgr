"""Oreo OS — home screen, 320×240 landscape, celebration theme.

Layout:
  ┌─ status bar h=22 (pink bar) ───────────────────────────────┐
  │  [wifi] [bt] [bat]                              17:06       │
  ├────────────────────────────────────────────────────────────┤
  │  (home_bg asset, warm jungle/celebration bg)               │
  │                                                            │
  │          17:06       (scale=4, dark text, centred)         │
  │       Tue 12 May 2026  (centred)                           │
  │                                                            │
  ├────────────────────────────────────────────────────────────┤
  │            [APPS icon]   (cream dock, centred)             │
  └────────────────────────────────────────────────────────────┘

Nav: LEFT/RIGHT wrap, A to open.
"""

import gc

import oreoOS
from oreoOS import api, config, theme, timeutil, widgets

SW = api.SCREEN_W  # 320
SH = api.SCREEN_H  # 240

_STATUS_H = widgets.HEADER_H
_MAIN_TOP = _STATUS_H
_MAIN_H = SH - _MAIN_TOP - widgets.HINT_H  # leave room for bottom hint bar

# Clock + date — vertically centred in the play area between status bar and hint bar.
# Date uses scale=2 so it's readable.
_CLOCK_H = 32  # 8×8 font scale=4
_DATE_H = 16  # 8×8 font scale=2
_CLOCK_GAP = 12
_BLOCK_H = _CLOCK_H + _CLOCK_GAP + _DATE_H
_CLOCK_Y = _MAIN_TOP + (_MAIN_H - _BLOCK_H) // 2
_DATE_Y = _CLOCK_Y + _CLOCK_H + _CLOCK_GAP


# ── asset loaders (pipeline only — no procedural fallback drawing) ─────────────

_bg_cache = None
_apps_cache = None
_scaled_bg_cache = None  # pre-rendered 320×240 RGB565 (big-endian) bytearray


def _load_bg():
    global _bg_cache
    if _bg_cache is not None:
        return _bg_cache if _bg_cache is not False else None
    try:
        import assets.icons.optimized.home_bg as m

        _bg_cache = (m.DATA, m.W, m.H)
        return _bg_cache
    except (ImportError, AttributeError):
        pass
    try:
        import struct

        from PIL import Image

        img = Image.open("assets/icons/raw/home_bg.png").convert("RGBA")
        img = img.resize((80, 60), Image.LANCZOS)
        bg = Image.new("RGBA", (80, 60), (theme.BG_R, theme.BG_G, theme.BG_B, 255))
        bg.paste(img, mask=img.split()[3])
        rgb = bg.convert("RGB")
        px = rgb.load()
        words = []
        for y in range(60):
            for x in range(80):
                r, g, b = px[x, y]
                words.append(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3))
        data = struct.pack(">%dH" % len(words), *words)
        _bg_cache = (data, 80, 60)
        return _bg_cache
    except Exception:
        _bg_cache = False
    return None


# Main foliage color of wallpaper to seamlessly merge with the top of the scene
_HOME_STATUS_BG = api.rgb(46, 102, 74)


def _get_scaled_bg():
    """Return (bytes, w, h) for the pre-scaled normal home background."""
    global _scaled_bg_cache
    if _scaled_bg_cache is not None:
        return _scaled_bg_cache if _scaled_bg_cache is not False else None

    bg = _load_bg()
    if not bg:
        _scaled_bg_cache = False
        return None

    import struct

    data, bw, bh = bg
    SCALE = 4
    sw = bw * SCALE
    sh = bh * SCALE
    n = bw * bh
    words = struct.unpack(">%dH" % n, data[: n * 2])

    out = bytearray(sw * sh * 2)
    row = bytearray(sw * 2)

    for src_row in range(bh):
        base_w = src_row * bw
        for col in range(bw):
            v = words[base_w + col]
            # big-endian bytes (high byte first) — matches framebuf convention
            b1 = v >> 8
            b0 = v & 0xFF
            base = col * SCALE * 2
            for dx in range(SCALE):
                row[base + dx * 2] = b1
                row[base + dx * 2 + 1] = b0

        row_start = src_row * SCALE * sw * 2
        for dy in range(SCALE):
            s = row_start + dy * sw * 2
            out[s : s + sw * 2] = row

    _scaled_bg_cache = (out, sw, sh)
    gc.collect()
    return _scaled_bg_cache


# ── Home app ─────────────────────────────────────────────────────────────────


class Home(oreoOS.App):
    name = "home"
    FULLSCREEN = True

    def __init__(self, app_list):
        self._apps = app_list
        self._dirty = True  # full redraw (background + everything)
        self._clock_dirty = False  # repaint only clock+date band
        self._status_dirty = False  # repaint only status bar
        self._last_sec = -1
        self._blink = True

    def on_enter(self, os):
        super().on_enter(os)
        self._dirty = True

    def on_button_press(self, btn):
        if btn == api.BTN_A:
            self.os.launch("__appmenu__")
        elif btn == api.BTN_B:
            self.os.launch("badge")

    def update(self, dt):
        _h, m, s, *_ = timeutil.now()
        if s != self._last_sec:
            self._last_sec = s
            self._blink = not self._blink
            # Repaint main clock area on second tick (for colon blink)
            self._clock_dirty = True
            # Repaint status bar when minute rolls over so header clock stays in sync
            if m != getattr(self, "_last_min", None):
                self._last_min = m
                self._status_dirty = True

    def draw(self, d):
        full = self._dirty
        clock_only = (not full) and getattr(self, "_clock_dirty", False)
        status_only = (not full) and getattr(self, "_status_dirty", False)
        if not (full or clock_only or status_only):
            return

        h, m, _s, wd, day, mon, yr = timeutil.now()

        if full:
            try:
                import time as _t

                _draw_start = _t.ticks_ms()
                if config.DEBUG:
                    print("[home] full draw begin")
            except Exception:
                _draw_start = None

            # ── background (uses cached pre-scaled buffer) ──────────────
            sbg = _get_scaled_bg()
            if sbg:
                data, sw, sh = sbg
                d.blit(data, 0, _MAIN_TOP, sw, sh)
            else:
                d.clear(theme.BG)

            self._draw_status_bar(d, h, m)
            self._draw_clock_area(d, h, m, wd, day, mon, yr)
            widgets.draw_hint(d, "A=apps  B=Badge  C=notif")
            self._dirty = False
            self._clock_dirty = False
            self._status_dirty = False

            try:
                if _draw_start is not None and config.DEBUG:
                    print(
                        "[home] full draw done in %d ms" % _t.ticks_diff(_t.ticks_ms(), _draw_start)
                    )
            except Exception:
                pass
            return

        if clock_only:
            # Clear ONLY the clock+date area, then redraw
            self._draw_clock_area(d, h, m, wd, day, mon, yr)
            self._clock_dirty = False

        if status_only:
            self._draw_status_bar(d, h, m)
            self._status_dirty = False

    def _draw_status_bar(self, d, h=None, m=None):
        widgets.draw_header(d, color=_HOME_STATUS_BG, accent=theme.PRIMARY)

    def _draw_clock_area(self, d, h, m, wd, day, mon, yr):
        # Repaint just the clock band over the (cached) background.
        # We re-blit the relevant slice of the cached scaled bg as our "erase".
        sbg = _get_scaled_bg()
        if sbg:
            data, sw, _sh = sbg
            # Slice rows _CLOCK_Y..(_DATE_Y+8) from the cached bg
            slice_y = _CLOCK_Y - _MAIN_TOP
            slice_h = (_DATE_Y + 8) - _CLOCK_Y
            row_bytes = sw * 2
            start = slice_y * row_bytes
            end = start + slice_h * row_bytes
            d.blit(data[start:end], 0, _CLOCK_Y, sw, slice_h)
        else:
            d.rect(0, _CLOCK_Y, SW, (_DATE_Y + 8) - _CLOCK_Y, theme.BG, fill=True)

        char_w = 8 * 4
        total_w = 5 * char_w
        cx = (SW - total_w) // 2
        colon_c = theme.TEXT_BRIGHT if self._blink else theme.MUTED
        d.text("%02d" % h, cx, _CLOCK_Y, theme.TEXT_BRIGHT, scale=4)
        d.text(":", cx + 2 * char_w, _CLOCK_Y, colon_c, scale=4)
        d.text("%02d" % m, cx + 3 * char_w, _CLOCK_Y, theme.TEXT_BRIGHT, scale=4)

        date_str = "%s %d %s %d" % (wd, day, mon, yr)
        # Bigger date (scale=2) for legibility; centred horizontally.
        dx = max(0, (SW - len(date_str) * 16) // 2)
        d.text(date_str, dx, _DATE_Y, theme.TEXT_BRIGHT, scale=2)
