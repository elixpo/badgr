"""System Monitor — Storage and RAM diagnostic app.

Tab 0: Flash Storage (stacked usage bar, per-bucket breakdown)
Tab 1: RAM & Heap (MicroPython GC stats)

Controls:
  Left/Right  switch tabs
  A           refresh stats
  C           force Garbage Collection (RAM tab)
  HOME        back to launcher
"""

import oreoOS
from oreoOS import api, storage, theme, widgets

SW = api.SCREEN_W
SH = api.SCREEN_H

PAD_X = 12
SUMMARY_Y = 48
SUMMARY_H = 40
BAR_H = 10
ROW_H = 18

_MISC_BROWN = api.rgb(120, 80, 45)
_FREE_GREY = api.rgb(210, 215, 220)

_BUCKET_COLORS = {
    "system": "PRIMARY",
    "apps": "TEAL",
    "gallery": "GOLD",
    "documents": "PURPLE",
    "misc": _MISC_BROWN,
}

_BUCKET_LABEL = {
    "system": "System",
    "apps": "Apps",
    "gallery": "Gallery",
    "documents": "Documents",
    "misc": "Misc",
}


def _human(n):
    if n >= 1024 * 1024:
        return "%.1f MB" % (n / 1024 / 1024)
    if n >= 1024:
        return "%.1f kB" % (n / 1024)
    return "%d B" % n


def _color(name):
    if isinstance(name, int):
        return name
    return getattr(theme, name, theme.MUTED)


class App(oreoOS.App):
    SHOW_LOADING = True

    def on_enter(self, os):
        super().on_enter(os)
        self._os = os
        self._tab = 0
        self._dirty = True
        self._refresh()

    def _refresh(self):
        try:
            self._snap = storage.usage()
        except Exception:
            self._snap = {
                "stats": {"total": 0, "free": 0, "used": 0},
                "buckets": {b: {"bytes": 0, "count": 0} for b in storage.BUCKETS},
            }
        self._dirty = True

    def update(self, dt):
        pass

    def on_button_press(self, btn):
        if btn == api.BTN_HOME:
            self._os.quit()
        elif btn == api.BTN_LEFT:
            if self._tab > 0:
                self._tab -= 1
                self._dirty = True
        elif btn == api.BTN_RIGHT:
            if self._tab < 1:
                self._tab += 1
                self._dirty = True
        elif btn == api.BTN_A:
            self._refresh()
        elif btn == api.BTN_C and self._tab == 1:
            try:
                import gc

                gc.collect()
            except Exception:
                pass
            self._dirty = True

    def draw(self, d):
        if not self._dirty:
            return
        self._dirty = False

        d.clear(theme.BG)
        widgets.draw_header(d, "SYSTEM MONITOR")

        # ── Tabs ──
        tab_w = SW // 2
        t0_bg = theme.PRIMARY if self._tab == 0 else theme.CARD
        t0_fg = api.WHITE if self._tab == 0 else theme.TEXT_DIM
        t1_bg = theme.PRIMARY if self._tab == 1 else theme.CARD
        t1_fg = api.WHITE if self._tab == 1 else theme.TEXT_DIM

        # Tab 0: FLASH
        d.rect(2, 28, tab_w - 4, 14, t0_bg, fill=True)
        t0_lbl = "FLASH STORAGE"
        d.text(t0_lbl, 2 + (tab_w - 4 - len(t0_lbl) * 8) // 2, 31, t0_fg)

        # Tab 1: RAM
        d.rect(tab_w + 2, 28, tab_w - 4, 14, t1_bg, fill=True)
        t1_lbl = "RAM & HEAP"
        d.text(t1_lbl, tab_w + 2 + (tab_w - 4 - len(t1_lbl) * 8) // 2, 31, t1_fg)

        if self._tab == 0:
            self._draw_flash(d)
            widgets.draw_hint(d, "< > switch   A=refresh")
        else:
            self._draw_ram(d)
            widgets.draw_hint(d, "< > switch   C=gc")

    def _draw_flash(self, d):
        stats = self._snap["stats"]
        bks = self._snap["buckets"]
        total = stats["total"] or 1
        used = stats["used"]
        free = stats["free"]

        y = SUMMARY_Y
        d.text("%s used" % _human(used), PAD_X, y, theme.TEXT_BRIGHT, scale=2)
        d.text("of %s" % _human(total), PAD_X, y + 18, theme.TEXT_DIM, scale=1)
        free_txt = "%s free" % _human(free)
        tw = len(free_txt) * 8
        d.text(free_txt, SW - PAD_X - tw, y + 18, theme.TEAL, scale=1)

        bar_y = y + SUMMARY_H
        bar_w = SW - 2 * PAD_X
        d.rect(PAD_X, bar_y, bar_w, BAR_H, _FREE_GREY, fill=True)

        x = PAD_X
        for name in storage.BUCKETS:
            b = bks[name]["bytes"]
            if b <= 0:
                continue
            seg_w = max(1, (b * bar_w) // total)
            if x + seg_w > PAD_X + bar_w:
                seg_w = PAD_X + bar_w - x
                if seg_w <= 0:
                    break
            d.rect(x, bar_y, seg_w, BAR_H, _color(_BUCKET_COLORS[name]), fill=True)
            x += seg_w

        row_y = bar_y + BAR_H + 10
        legend_rows = [
            (_BUCKET_LABEL[n], _color(_BUCKET_COLORS[n]), bks[n]["bytes"]) for n in storage.BUCKETS
        ]
        legend_rows.append(("Free", _FREE_GREY, free))
        for label, swatch_color, byte_count in legend_rows:
            sw_x = PAD_X
            sw_w = 10
            d.rect(sw_x, row_y + 4, sw_w, sw_w, swatch_color, fill=True)
            d.text(label, sw_x + sw_w + 8, row_y + 4, theme.TEXT_BRIGHT, scale=1)
            sz_txt = _human(byte_count)
            tw = len(sz_txt) * 8
            d.text(sz_txt, SW - PAD_X - tw, row_y + 4, theme.TEXT_DIM, scale=1)
            row_y += ROW_H

    def _draw_ram(self, d):
        d.rect(16, 64, SW - 32, 110, theme.CARD, fill=True)
        d.rect(16, 64, SW - 32, 2, theme.GOLD, fill=True)
        d.text("MICROPYTHON HEAP", 24, 74, theme.GOLD, scale=1)

        try:
            import gc

            free = gc.mem_free()
            alloc = gc.mem_alloc()
        except Exception:
            free = 0
            alloc = 0

        total = max(1, alloc + free)
        ram_pct = float(alloc) / total

        bar_y2 = 100
        bar_w = SW - 48
        fill_w2 = int(bar_w * ram_pct)

        d.rect(24, bar_y2, bar_w, 8, theme.MUTED2, fill=True)
        d.rect(24, bar_y2, fill_w2, 8, theme.GOLD, fill=True)

        d.text("Alloc: %s" % _human(alloc), 24, 120, theme.TEXT_BRIGHT)
        d.text(
            "Free: %s" % _human(free),
            SW - 24 - len("Free: %s" % _human(free)) * 8,
            120,
            theme.GREEN,
        )

        msg = "Press C to GC"
        d.text(msg, (SW - len(msg) * 8) // 2, 150, theme.TEXT_DIM)

    def on_exit(self):
        self._snap = None
        try:
            import gc

            gc.collect()
        except Exception:
            pass
