"""App Manager — System Application & Memory Management for Oreo OS.

Inspect installed applications, disk footprints, uninstall user apps,
and monitor ESP32-S3 LittleFS flash storage and PSRAM / MicroPython heap memory.
Fully compatible with both physical hardware and the desktop simulator.

Controls:
  UP / DOWN     Navigate App List / Options
  LEFT / RIGHT  Switch Tabs (Apps <-> Diagnostics)
  A             Inspect App / Launch / Confirm Action
  B             Back / Dismiss Modal / Return to Launcher
  C             Instant Memory Clean (Garbage Collection)
  HOME          Exit to Launcher
"""

try:
    import uos as os
except ImportError:
    import os

try:
    import gc
except ImportError:
    gc = None

import json
import time
import oreoOS
from oreoOS import api, theme, widgets, storage

from oreoOS.api import ticks_ms as _ticks_ms, ticks_diff as _ticks_diff

SW = api.SCREEN_W
SH = api.SCREEN_H
HEADER_H = widgets.HEADER_H
HINT_H = widgets.HINT_H
TAB_H = 18
CARD_H = 36
CARD_GAP = 4
VISIBLE_CARDS = 4
LIST_TOP_Y = HEADER_H + TAB_H + 4

# Core OS apps protected from uninstallation
PROTECTED_APPS = ("launcher", "settings", "store", "manager", "about")


def _format_size(num_bytes):
    """Format bytes into a human-readable string."""
    if num_bytes < 1024:
        return "%d B" % num_bytes
    elif num_bytes < 1024 * 1024:
        return "%.1f KB" % (num_bytes / 1024.0)
    else:
        return "%.1f MB" % (num_bytes / (1024.0 * 1024.0))


def _calc_dir_footprint(path):
    """Recursively calculate the total size and file count of a directory."""
    total_bytes = 0
    file_count = 0
    stack = [path]

    while stack:
        cur = stack.pop()
        try:
            entries = os.listdir(cur)
        except Exception:
            continue

        for entry in entries:
            full = cur + "/" + entry
            try:
                st = os.stat(full)
                # Check for directory (S_IFDIR 0o040000)
                if st[0] & 0o040000:
                    stack.append(full)
                else:
                    total_bytes += st[6]
                    file_count += 1
            except Exception:
                pass

    return total_bytes, file_count


def _rm_tree_safe(path):
    return storage.rm_tree(path)


def _get_flash_stats():
    """Return flash storage statistics (total, free, used)."""
    try:
        st = os.statvfs("/")
        bsize = st[0]
        total = bsize * st[2]
        free = bsize * st[3]
        used = total - free
        return {"total": total, "free": free, "used": used, "valid": True}
    except Exception:
        # Emulator / Platform fallback
        return {"total": 8 * 1024 * 1024, "free": 7180 * 1024, "used": 1012 * 1024, "valid": True}


def _get_ram_stats():
    """Return RAM / Heap memory statistics."""
    if gc:
        try:
            alloc = gc.mem_alloc()
            free = gc.mem_free()
            return {"alloc": alloc, "free": free, "total": alloc + free, "type": "MicroPython Heap"}
        except Exception:
            pass

    # Simulator fallback
    return {"alloc": 1240 * 1024, "free": 2856 * 1024, "total": 4096 * 1024, "type": "ESP32 PSRAM"}


class App(oreoOS.App):
    name = "App Manager"
    author = "sea-deep"
    SHOW_LOADING = True
    CONSUMES_C = True

    def on_enter(self, os_obj):
        if gc:
            try:
                gc.collect()
            except Exception:
                pass
        self._os = os_obj
        self._tab = 0       # 0 = Apps, 1 = Diagnostics & Storage
        self._sel = 0       # Selected app index in list
        self._top = 0       # Scroll offset for app list

        # Modal State
        self._mode = "LIST" # "LIST" | "DETAILS" | "CONFIRM_UNINSTALL"
        self._detail_app = None
        self._detail_sel = 0 # 0=Launch, 1=Clean Cache, 2=Uninstall, 3=Back
        self._detail_files = []

        # Toast notification
        self._toast_msg = ""
        self._toast_until = 0

        # Memory clean delta report
        self._gc_report = ""
        self._gc_report_until = 0

        self._dirty = True
        self._scan_installed_apps()

    def on_exit(self):
        """Free caches and trigger GC sweep on exit."""
        self._apps = []
        self._icon_cache = {}
        if gc:
            try:
                gc.collect()
            except Exception:
                pass

    def _scan_installed_apps(self):
        """Scan all apps in apps/ and compute their sizes and metadata."""
        from oreoOS import launcher
        raw_apps = launcher.list_apps()

        self._apps = []
        self._icon_cache = {}

        total_app_bytes = 0
        for item in raw_apps:
            app_dir = item["dir"]
            path = "apps/" + app_dir
            size_b, file_cnt = _calc_dir_footprint(path)
            total_app_bytes += size_b

            is_sys = app_dir in PROTECTED_APPS
            entry = {
                "name": item.get("name", app_dir),
                "dir": app_dir,
                "author": item.get("author", "unknown"),
                "version": item.get("version", "1.0.0"),
                "category": item.get("category", "General"),
                "description": item.get("description", ""),
                "size_bytes": size_b,
                "size_str": _format_size(size_b),
                "files_count": file_cnt,
                "is_system": is_sys,
                "icon": item.get("icon"),
            }
            self._apps.append(entry)

        # Sort: User apps first, then system apps
        self._apps.sort(key=lambda x: (x["is_system"], x["name"].lower()))
        self._total_apps_size = total_app_bytes
        self._dirty = True

    def _trigger_gc_sweep(self):
        """Execute garbage collection sweep and report freed RAM."""
        ram_before = _get_ram_stats()["free"]
        if gc:
            try:
                gc.collect()
            except Exception:
                pass
        ram_after = _get_ram_stats()["free"]
        freed = max(0, ram_after - ram_before)

        if freed > 0:
            self._gc_report = "Freed %s RAM!" % _format_size(freed)
        else:
            self._gc_report = "Memory optimal (0 B to free)"
        self._gc_report_until = _ticks_ms() + 2500
        self._dirty = True

    def _load_app_icon(self, app_dir, icon_name):
        """Load and cache 32x32 app icon."""
        if app_dir in self._icon_cache:
            return self._icon_cache[app_dir]

        from oreoOS import icons
        res = icons.load(app_dir, icon_name)
        if res:
            data, w, h = res
            self._icon_cache[app_dir] = (bytearray(data), w, h)
            return self._icon_cache[app_dir]
        return None

    # ─── INPUT HANDLING ──────────────────────────────────────────────────────
    def on_button_press(self, btn):
        if self._mode == "DETAILS":
            self._handle_details_input(btn)
        elif self._mode == "CONFIRM_UNINSTALL":
            self._handle_confirm_input(btn)
        else:
            self._handle_list_input(btn)

    def _handle_list_input(self, btn):
        if btn in (api.BTN_HOME, api.BTN_B):
            self._os.quit()
            return

        if btn == api.BTN_C:
            self._trigger_gc_sweep()
            return

        if btn == api.BTN_LEFT:
            self._tab = (self._tab - 1) % 2
            self._dirty = True
            return
        elif btn == api.BTN_RIGHT:
            self._tab = (self._tab + 1) % 2
            self._dirty = True
            return

        if self._tab == 0:
            n = len(self._apps)
            if n == 0:
                return

            if btn == api.BTN_UP:
                self._sel = (self._sel - 1) % n
                self._scroll_to_sel()
                self._dirty = True
            elif btn == api.BTN_DOWN:
                self._sel = (self._sel + 1) % n
                self._scroll_to_sel()
                self._dirty = True
            elif btn == api.BTN_A:
                self._open_app_details(self._apps[self._sel])
        elif self._tab == 1:
            if btn == api.BTN_A:
                self._trigger_gc_sweep()

    def _scroll_to_sel(self):
        if self._sel < self._top:
            self._top = self._sel
        elif self._sel >= self._top + VISIBLE_CARDS:
            self._top = self._sel - VISIBLE_CARDS + 1

    def _open_app_details(self, app_entry):
        self._detail_app = app_entry
        self._detail_sel = 0
        self._mode = "DETAILS"
        self._dirty = True

    def _handle_details_input(self, btn):
        if btn in (api.BTN_HOME, api.BTN_B):
            self._mode = "LIST"
            self._dirty = True
            return

        max_options = 4 if not self._detail_app["is_system"] else 3
        if btn == api.BTN_UP:
            self._detail_sel = (self._detail_sel - 1) % max_options
            self._dirty = True
        elif btn == api.BTN_DOWN:
            self._detail_sel = (self._detail_sel + 1) % max_options
            self._dirty = True
        elif btn == api.BTN_A:
            if self._detail_sel == 0:
                # Launch App
                app_dir = self._detail_app["dir"]
                self._os.launch(app_dir)
            elif self._detail_sel == 1:
                # Clean Cache
                self._clean_app_cache(self._detail_app["dir"])
            elif self._detail_sel == 2:
                if not self._detail_app["is_system"]:
                    # Uninstall
                    self._mode = "CONFIRM_UNINSTALL"
                    self._dirty = True
                else:
                    # Back
                    self._mode = "LIST"
                    self._dirty = True
            elif self._detail_sel == 3:
                # Back
                self._mode = "LIST"
                self._dirty = True

    def _clean_app_cache(self, app_dir):
        """Remove __pycache__ inside the app directory."""
        cache_path = "apps/" + app_dir + "/__pycache__"
        _rm_tree_safe(cache_path)
        cache_path_src = "apps/" + app_dir + "/src/__pycache__"
        _rm_tree_safe(cache_path_src)
        self._toast_msg = "Cache cleared!"
        self._toast_until = _ticks_ms() + 2000
        self._scan_installed_apps()
        self._dirty = True

    def _handle_confirm_input(self, btn):
        if btn == api.BTN_B:
            self._mode = "DETAILS"
            self._dirty = True
            return
        elif btn == api.BTN_A:
            # Perform Uninstallation
            app_dir = self._detail_app["dir"]
            _rm_tree_safe("apps/" + app_dir)

            # Invalidate launcher apps roster cache
            try:
                from oreoOS.launcher import invalidate_apps_cache
                invalidate_apps_cache()
            except Exception:
                pass

            self._mode = "LIST"
            self._toast_msg = "Uninstalled %s" % self._detail_app["name"]
            self._toast_until = _ticks_ms() + 2500
            self._scan_installed_apps()
            self._sel = min(self._sel, max(0, len(self._apps) - 1))
            self._dirty = True

    # ─── UPDATE & RENDER ─────────────────────────────────────────────────────
    def update(self, dt):
        now = _ticks_ms()
        if self._toast_msg and now > self._toast_until:
            self._toast_msg = ""
            self._dirty = True
        if self._gc_report and now > self._gc_report_until:
            self._gc_report = ""
            self._dirty = True

    def draw(self, d):
        if not self._dirty:
            return

        d.clear(theme.BG)
        widgets.draw_header(d, "APP MANAGER")

        if self._mode == "DETAILS":
            self._draw_details_modal(d)
        elif self._mode == "CONFIRM_UNINSTALL":
            self._draw_confirm_modal(d)
        else:
            self._draw_tab_bar(d)
            if self._tab == 0:
                self._draw_apps_tab(d)
            else:
                self._draw_diagnostics_tab(d)

        # Bottom Hint Bar
        if self._mode == "LIST":
            hint = "A=inspect  B=exit  C=free ram  < > Tab"
        elif self._mode == "DETAILS":
            hint = "A=select  B=back  UP/DN=navigate"
        else:
            hint = "A=CONFIRM DELETE  B=Cancel"
        widgets.draw_hint(d, hint)

        # Draw Toast if active
        if self._toast_msg:
            self._draw_toast(d, self._toast_msg, theme.TEAL)
        elif self._gc_report:
            self._draw_toast(d, self._gc_report, theme.GOLD)

        self._dirty = False

    def _draw_tab_bar(self, d):
        y = HEADER_H
        d.rect(0, y, SW, TAB_H, theme.CARD, fill=True)
        d.rect(0, y + TAB_H - 1, SW, 1, theme.MUTED2, fill=True)

        w_half = SW // 2

        # Tab 0: APPS
        t0_sel = (self._tab == 0)
        t0_bg = theme.PRIMARY if t0_sel else theme.CARD
        t0_fg = api.WHITE if t0_sel else theme.MUTED
        d.rect(2, y + 2, w_half - 4, TAB_H - 4, t0_bg, fill=True)
        t0_lbl = "APPS (%d)" % len(self._apps)
        d.text(t0_lbl, (w_half - len(t0_lbl) * 8) // 2, y + 5, t0_fg)

        # Tab 1: DIAGNOSTICS
        t1_sel = (self._tab == 1)
        t1_bg = theme.PRIMARY if t1_sel else theme.CARD
        t1_fg = api.WHITE if t1_sel else theme.MUTED
        d.rect(w_half + 2, y + 2, w_half - 4, TAB_H - 4, t1_bg, fill=True)
        t1_lbl = "DIAGNOSTICS & RAM"
        d.text(t1_lbl, w_half + (w_half - len(t1_lbl) * 8) // 2, y + 5, t1_fg)

    # ─── TAB 0: APPS LIST ────────────────────────────────────────────────────
    def _draw_apps_tab(self, d):
        if not self._apps:
            d.text("No apps installed", 60, 110, theme.MUTED, scale=2)
            return

        vis = min(VISIBLE_CARDS, len(self._apps))
        for vi in range(vis):
            idx = self._top + vi
            if idx >= len(self._apps):
                break
            app = self._apps[idx]
            card_y = LIST_TOP_Y + vi * (CARD_H + CARD_GAP)
            self._draw_app_card(d, card_y, app, idx == self._sel)

        # Scrollbar
        n = len(self._apps)
        if n > VISIBLE_CARDS:
            track_x = SW - 4
            track_y = LIST_TOP_Y
            track_h = VISIBLE_CARDS * (CARD_H + CARD_GAP) - CARD_GAP
            d.rect(track_x, track_y, 2, track_h, theme.MUTED2, fill=True)
            thumb_h = max(10, track_h * VISIBLE_CARDS // n)
            thumb_y = track_y + (track_h - thumb_h) * self._top // (n - VISIBLE_CARDS)
            d.rect(track_x, thumb_y, 2, thumb_h, theme.PRIMARY, fill=True)

    def _draw_app_card(self, d, y, app, is_sel):
        card_w = SW - 12
        card_x = 4

        bg = theme.DOCK_SEL if is_sel else theme.CARD
        d.rect(card_x, y, card_w, CARD_H, bg, fill=True)

        if is_sel:
            d.rect(card_x, y, card_w, 1, theme.SEL_BORDER, fill=True)
            d.rect(card_x, y + CARD_H - 1, card_w, 1, theme.SEL_BORDER, fill=True)
            d.rect(card_x, y, 1, CARD_H, theme.SEL_BORDER, fill=True)
            d.rect(card_x + card_w - 1, y, 1, CARD_H, theme.SEL_BORDER, fill=True)

        # App Icon (Left, 32x32 box)
        icon_res = self._load_app_icon(app["dir"], app["icon"])
        if icon_res:
            data, iw, ih = icon_res
            d.blit(data, card_x + 3, y + 2, min(32, iw), min(32, ih))
        else:
            # Fallback glyph tile
            d.rect(card_x + 3, y + 2, 32, 32, theme.PRIMARY, fill=True)
            letter = (app["name"] or "?")[0].upper()
            d.text(letter, card_x + 11, y + 7, api.WHITE, scale=2)

        # App Name & Subtitle
        name_x = card_x + 40
        d.text(app["name"][:14], name_x, y + 5, theme.TEXT_BRIGHT, scale=1)
        sub_info = "%s · %s" % (app["category"], app["version"])
        d.text(sub_info[:18], name_x, y + 20, theme.MUTED, scale=1)

        # Right-side Badges & Footprint
        size_str = app["size_str"]
        size_w = len(size_str) * 8
        d.text(size_str, card_x + card_w - size_w - 6, y + 6, theme.TEXT_BRIGHT, scale=1)

        # Tag: SYSTEM (dim gold) or USER (green)
        tag = "SYSTEM" if app["is_system"] else "USER"
        tag_col = theme.GOLD if app["is_system"] else theme.GREEN
        tag_w = len(tag) * 8 + 8
        tx = card_x + card_w - tag_w - 6
        ty = y + 19
        d.rect(tx, ty, tag_w, 12, tag_col, fill=True)
        d.text(tag, tx + 4, ty + 2, api.WHITE, scale=1)

    # ─── TAB 1: DIAGNOSTICS & STORAGE ────────────────────────────────────────
    def _draw_diagnostics_tab(self, d):
        flash = _get_flash_stats()
        ram = _get_ram_stats()

        y = LIST_TOP_Y

        # 1. Flash Storage Card
        d.rect(6, y, SW - 12, 64, theme.CARD, fill=True)
        d.rect(6, y, SW - 12, 2, theme.PRIMARY, fill=True)
        d.text("LITTLEFS FLASH STORAGE", 14, y + 6, theme.PRIMARY, scale=1)

        # Progress bar
        bar_x = 14
        bar_y = y + 22
        bar_w = SW - 28
        bar_h = 8
        used_pct = float(flash["used"]) / max(1.0, float(flash["total"]))
        fill_w = int(bar_w * used_pct)

        d.rect(bar_x, bar_y, bar_w, bar_h, theme.MUTED2, fill=True)
        d.rect(bar_x, bar_y, fill_w, bar_h, theme.PRIMARY, fill=True)

        # Metric row
        stat_l = "Used: %s" % _format_size(flash["used"])
        stat_r = "Free: %s / %s" % (_format_size(flash["free"]), _format_size(flash["total"]))
        d.text(stat_l, bar_x, y + 36, theme.TEXT_BRIGHT)
        d.text(stat_r, SW - 14 - len(stat_r) * 8, y + 36, theme.MUTED)
        pct_str = "Total Apps on Disk: %s" % _format_size(self._total_apps_size)
        d.text(pct_str, bar_x, y + 48, theme.TEAL)

        # 2. PSRAM & Heap Memory Card
        y2 = y + 70
        d.rect(6, y2, SW - 12, 68, theme.CARD, fill=True)
        d.rect(6, y2, SW - 12, 2, theme.GOLD, fill=True)
        d.text("RAM & MICROPYTHON HEAP", 14, y2 + 6, theme.GOLD, scale=1)

        # RAM Progress bar
        bar_y2 = y2 + 22
        ram_pct = float(ram["alloc"]) / max(1.0, float(ram["total"]))
        fill_w2 = int(bar_w * ram_pct)

        d.rect(bar_x, bar_y2, bar_w, bar_h, theme.MUTED2, fill=True)
        d.rect(bar_x, bar_y2, fill_w2, bar_h, theme.GOLD, fill=True)

        ram_l = "Alloc: %s" % _format_size(ram["alloc"])
        ram_r = "Free: %s" % _format_size(ram["free"])
        d.text(ram_l, bar_x, y2 + 36, theme.TEXT_BRIGHT)
        d.text(ram_r, SW - 14 - len(ram_r) * 8, y2 + 36, theme.GREEN)

        btn_txt = "Press A or C to Run Garbage Collector"
        d.text(btn_txt, (SW - len(btn_txt) * 8) // 2, y2 + 50, theme.TEXT_DIM)

    # ─── DETAILS MODAL ───────────────────────────────────────────────────────
    def _draw_details_modal(self, d):
        app = self._detail_app
        d.rect(8, 26, SW - 16, 192, theme.CARD, fill=True)
        d.rect(8, 26, SW - 16, 2, theme.PRIMARY, fill=True)

        # Header Info
        icon_res = self._load_app_icon(app["dir"], app["icon"])
        if icon_res:
            data, iw, ih = icon_res
            d.blit(data, 16, 32, min(32, iw), min(32, ih))
        else:
            d.rect(16, 32, 32, 32, theme.PRIMARY, fill=True)
            d.text(app["name"][0].upper(), 24, 37, api.WHITE, scale=2)

        d.text(app["name"][:16], 56, 32, theme.TEXT_BRIGHT, scale=2)
        meta_ln = "v%s by %s" % (app["version"], app["author"])
        d.text(meta_ln[:26], 56, 49, theme.MUTED, scale=1)

        # App Description & Specs Grid Box
        d.rect(16, 67, SW - 32, 54, theme.BG, fill=True)
        d.rect(16, 67, SW - 32, 54, theme.MUTED2, fill=False)

        # Description text (wrap up to 2 lines)
        desc = app.get("description") or "No description provided."
        desc_lines = []
        words = desc.split(" ")
        cur_line = ""
        for w in words:
            if len(cur_line) + len(w) + 1 <= 34:
                cur_line = cur_line + " " + w if cur_line else w
            else:
                desc_lines.append(cur_line)
                cur_line = w
                if len(desc_lines) >= 2:
                    break
        if cur_line and len(desc_lines) < 2:
            desc_lines.append(cur_line)

        dy = 71
        for dl in desc_lines:
            d.text(dl[:34], 22, dy, theme.TEXT_BRIGHT)
            dy += 11

        # Specs row (Category & Size)
        spec_ln = "%s · %s (%d files)" % (app["category"], app["size_str"], app["files_count"])
        d.text(spec_ln[:34], 22, 107, theme.TEAL)

        # Action Options
        opts = ["1. Launch App", "2. Clear Cache (__pycache__)"]
        if not app["is_system"]:
            opts.append("3. Uninstall App")
            opts.append("4. Back to Apps")
        else:
            opts.append("3. Back to Apps")

        opt_y = 127
        for i, opt in enumerate(opts):
            sel = (i == self._detail_sel)
            bg = theme.PRIMARY if sel else theme.CARD
            fg = api.WHITE if sel else theme.TEXT_BRIGHT
            d.rect(16, opt_y, SW - 32, 18, bg, fill=True)
            d.text(opt, 24, opt_y + 5, fg, scale=1)
            opt_y += 20

    # ─── CONFIRM UNINSTALL MODAL ─────────────────────────────────────────────
    def _draw_confirm_modal(self, d):
        app = self._detail_app
        d.rect(16, 45, SW - 32, 140, theme.CARD, fill=True)
        d.rect(16, 45, SW - 32, 3, theme.PRIMARY, fill=True)

        d.text("UNINSTALL APP?", (SW - 14 * 16) // 2, 55, theme.PRIMARY, scale=2)

        msg1 = "Delete '%s' from flash?" % app["name"][:18]
        msg2 = "Will permanently free %s." % app["size_str"]
        d.text(msg1, (SW - len(msg1) * 8) // 2, 85, theme.TEXT_BRIGHT)
        d.text(msg2, (SW - len(msg2) * 8) // 2, 100, theme.MUTED)

        # Action Buttons
        d.rect(26, 125, 120, 24, theme.PRIMARY, fill=True)
        d.text("A: CONFIRM", 38, 133, api.WHITE)

        d.rect(160, 125, 120, 24, theme.MUTED2, fill=True)
        d.text("B: CANCEL", 175, 133, api.WHITE)

    # ─── TOAST NOTIFICATION ──────────────────────────────────────────────────
    def _draw_toast(self, d, msg, color):
        w = len(msg) * 8 + 24
        x = (SW - w) // 2
        y = SH - HINT_H - 24
        d.rect(x, y, w, 18, color, fill=True)
        d.rect(x, y, w, 18, api.WHITE, fill=False)
        d.text(msg, x + 12, y + 5, api.WHITE)
