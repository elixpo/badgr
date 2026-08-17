"""Color Picker - Photoshop-style 2D spectrum + crosshair cursor.

Layout:
  Header (28 px)  : "COLOR" label + small live preview swatch + tiny readout
                    of the current value in the active model (RGB / HSL / CMYK)
  Spectrum field  : full 320 x 196 rainbow, upscaled 4x from a baked
                    80 x 49 source asset (apps/color_picker/assets/optimized/
                    color_splash.py). White at the top -> saturated band in
                    the middle -> black at the bottom. Hue sweeps left -> right.
  Hint bar (16 px): control summary.

Controls:
  arrows  move the crosshair (long-press accelerates ~5x after ~0.4 s held)
  B       cycle display model RGB -> HSL -> CMYK -> RGB
  A       save the current colour to apps/color_picker/state.txt
  HOME    back to the apps drawer

The current colour is read directly out of the upscaled spectrum buffer at
the cursor position (so what you see is what you get; no resampling
artefacts). The HSL / CMYK readouts are derived on the fly from RGB.
"""

import oreoOS
from oreoOS import api, theme, widgets

SW = api.SCREEN_W  # 320
SH = api.SCREEN_H  # 240
PLAY_TOP = widgets.HEADER_H
PLAY_BOT = SH - widgets.HINT_H
PLAY_H = PLAY_BOT - PLAY_TOP  # 196
PLAY_W = SW  # full width
STATE_PATH = "state_color.txt"

# Movement tuning. Tap = 1 px nudge; hold for ACCEL_AFTER seconds and the
# cursor steps by FAST_PX_PER_FRAME each frame for fast traversal.
TAP_NUDGE_PX = 2
SLOW_PX_PER_S = 60.0
FAST_PX_PER_S = 380.0
ACCEL_AFTER_S = 0.4

# Channel labels per model (just for the header readout)
_MODELS = ("RGB", "HSL", "CMYK")


# ── conversions ─────────────────────────────────────────────────────────────


def _rgb_to_hsl(r, g, b):
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    mx = max(rf, gf, bf)
    mn = min(rf, gf, bf)
    l = (mx + mn) / 2
    if mx == mn:
        return 0, 0, int(round(l * 100))
    d = mx - mn
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == rf:
        h = ((gf - bf) / d) % 6
    elif mx == gf:
        h = (bf - rf) / d + 2
    else:
        h = (rf - gf) / d + 4
    return int(round(h * 60)) % 360, int(round(s * 100)), int(round(l * 100))


def _rgb_to_cmyk(r, g, b):
    if r == 0 and g == 0 and b == 0:
        return 0, 0, 0, 100
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    k = 1 - max(rf, gf, bf)
    inv_k = 1 - k if k < 1 else 1.0
    c = (1 - rf - k) / inv_k
    m = (1 - gf - k) / inv_k
    y = (1 - bf - k) / inv_k
    return (int(round(c * 100)), int(round(m * 100)), int(round(y * 100)), int(round(k * 100)))


# ── upscale 80x49 -> 320x196 (nearest-neighbour) ───────────────────────────


def _upscale_4x(src, sw, sh, dw, dh):
    """RGB565-big-endian src buffer -> dest buffer, 4x point-sampled."""
    out = bytearray(dw * dh * 2)
    sx_step = (sw << 16) // dw
    sy_step = (sh << 16) // dh
    sy = 0
    for dy in range(dh):
        src_row = (sy >> 16) * sw * 2
        sx = 0
        row_off = dy * dw * 2
        for dx in range(dw):
            s = src_row + (sx >> 16) * 2
            out[row_off + dx * 2] = src[s]
            out[row_off + dx * 2 + 1] = src[s + 1]
            sx += sx_step
        sy += sy_step
    return out


def _try_load_spectrum():
    for modpath in (
        "apps.Colors.assets.optimized.color_splash",
        "apps_market.Colors.assets.optimized.color_splash",
        "apps.color_picker.assets.optimized.color_splash",
    ):
        try:
            m = __import__(modpath, None, None, ["DATA", "W", "H"])
            return bytes(m.DATA), m.W, m.H
        except Exception:
            pass
    try:
        pkg = __name__.rsplit(".", 2)[0]
        m = __import__(pkg + ".assets.optimized.color_splash", None, None, ["DATA", "W", "H"])
        return bytes(m.DATA), m.W, m.H
    except Exception:
        return None


# ── persistence ─────────────────────────────────────────────────────────────


def _save_state(cx, cy, rgb):
    try:
        with open(STATE_PATH, "w") as f:
            f.write("%f,%f,%d,%d,%d" % (cx, cy, rgb[0], rgb[1], rgb[2]))
    except Exception:
        pass


def _load_state():
    try:
        with open(STATE_PATH) as f:
            parts = f.read().strip().split(",")
            if len(parts) == 5:
                return (
                    float(parts[0]),
                    float(parts[1]),
                    (int(parts[2]), int(parts[3]), int(parts[4])),
                )
            elif len(parts) == 3:
                return (PLAY_W / 2.0, PLAY_H / 2.0, (int(parts[0]), int(parts[1]), int(parts[2])))
    except Exception:
        pass
    return (PLAY_W / 2.0, PLAY_H / 2.0, (255, 93, 104))


SLOT_KEYS = ("PRI", "BG", "CARD", "SEC", "ACC")
SLOT_TITLES = {
    "PRI": "PRIMARY",
    "BG": "BACKGROUND",
    "CARD": "CARD SURFACE",
    "SEC": "SECONDARY",
    "ACC": "ACCENT",
}


class App(oreoOS.App):
    SHOW_LOADING = True  # ~300 ms upscale at entry — hidden by the panel
    NO_HEADER = True  # Custom header with live color swatch & format readout
    CONSUMES_C = True  # Uses C button to cycle curated OS theme presets

    # ── lifecycle ──────────────────────────────────────────────────────────
    def on_enter(self, os):
        self._os = os
        spec = _try_load_spectrum()
        if spec:
            src, sw, sh = spec
            self._bg = _upscale_4x(src, sw, sh, PLAY_W, PLAY_H)
            self._bg_w, self._bg_h = PLAY_W, PLAY_H
        else:
            self._bg = None
            self._bg_w = self._bg_h = 0

        self._cx, self._cy, self._rgb = _load_state()
        self._slot_idx = 0  # active palette slot (0: PRI, 1: BG, 2: CARD, 3: SEC, 4: ACC)
        self._auto_harmonize = True

        # Initialize slots from active theme
        th = theme.CURRENT_THEME
        self._slots = {
            "PRI": th.primary_rgb,
            "BG": th.bg_rgb,
            "CARD": th.card_rgb,
            "SEC": th.teal_rgb,
            "ACC": th.gold_rgb,
        }

        self._saved_flash = 0.0
        self._saved_msg = "Theme Applied!"
        self._hold_t = {api.BTN_LEFT: 0.0, api.BTN_RIGHT: 0.0, api.BTN_UP: 0.0, api.BTN_DOWN: 0.0}
        self._sample_color()
        self._dirty = True

    # ── input ──────────────────────────────────────────────────────────────
    def on_button_press(self, btn):
        if btn == api.BTN_LEFT:
            self._active_preset_id = None
            self._cx -= TAP_NUDGE_PX
            self._clamp_cursor()
            self._sample_color()
            self._dirty = True
        elif btn == api.BTN_RIGHT:
            self._active_preset_id = None
            self._cx += TAP_NUDGE_PX
            self._clamp_cursor()
            self._sample_color()
            self._dirty = True
        elif btn == api.BTN_UP:
            self._active_preset_id = None
            self._cy -= TAP_NUDGE_PX
            self._clamp_cursor()
            self._sample_color()
            self._dirty = True
        elif btn == api.BTN_DOWN:
            self._active_preset_id = None
            self._cy += TAP_NUDGE_PX
            self._clamp_cursor()
            self._sample_color()
            self._dirty = True
        elif btn == api.BTN_B:
            # Cycle active palette slot to customize from scratch
            self._auto_harmonize = False
            self._slot_idx = (self._slot_idx + 1) % len(SLOT_KEYS)
            self._active_preset_id = None
            cur_slot = SLOT_KEYS[self._slot_idx]
            self._saved_msg = "Slot: %s" % SLOT_TITLES[cur_slot]
            self._saved_flash = 1.0
            self._dirty = True
        elif btn == api.BTN_C:
            # Cycle curated presets
            keys = [k for k in theme.PRESET_KEYS if k != "custom"]
            self._preset_idx = (getattr(self, "_preset_idx", -1) + 1) % len(keys)
            self._active_preset_id = keys[self._preset_idx]
            preset = theme.PRESETS[self._active_preset_id]
            self._rgb = preset.primary_rgb
            self._slots["PRI"] = preset.primary_rgb
            self._slots["BG"] = preset.bg_rgb
            self._slots["CARD"] = preset.card_rgb
            self._slots["SEC"] = preset.teal_rgb
            self._slots["ACC"] = preset.gold_rgb
            theme.set_preset(self._active_preset_id, save=True)
            self._saved_msg = preset.name
            self._saved_flash = 1.5
            self._dirty = True
        elif btn == api.BTN_A:
            # Save the active multi-slot theme configuration
            if getattr(self, "_active_preset_id", None):
                theme.set_preset(self._active_preset_id, save=True)
                preset = theme.PRESETS[self._active_preset_id]
                self._saved_msg = "%s Applied!" % preset.name
            else:
                pri = self._slots["PRI"]
                bg = self._slots["BG"]
                card = self._slots["CARD"]
                sec = self._slots["SEC"]
                acc = self._slots["ACC"]

                bg_lum = theme.get_perceived_luminance(*bg)
                is_dark = bg_lum < 100

                text_bright = (245, 245, 250) if is_dark else (24, 24, 32)
                text_dim = (180, 180, 200) if is_dark else (100, 80, 70)
                muted = (130, 130, 155) if is_dark else (160, 120, 100)
                muted2 = (60, 60, 85) if is_dark else (200, 160, 140)

                pri_lum = theme.get_perceived_luminance(*pri)
                status_text = (24, 24, 32) if pri_lum >= 170 else (255, 255, 255)

                custom_th = theme.Theme(
                    id="custom",
                    name="Custom Palette",
                    bg=bg,
                    card=card,
                    primary=pri,
                    teal=sec,
                    gold=acc,
                    text_bright=text_bright,
                    text_dim=text_dim,
                    muted=muted,
                    muted2=muted2,
                    status_bg=pri,
                    status_text=status_text,
                    status_accent=acc,
                    dock_bg=card,
                    dock_sel=(
                        min(255, card[0] + 15),
                        min(255, card[1] + 15),
                        min(255, card[2] + 15),
                    ),
                    sel_border=pri,
                    sel_text=pri
                    if (not is_dark and pri_lum < 170) or (is_dark and pri_lum > 80)
                    else text_bright,
                    is_dark=is_dark,
                )
                theme.apply_theme(custom_th, save=True)
                _save_state(self._cx, self._cy, pri)
                try:
                    self._os.settings_set("color_picker_rgb", pri)
                except Exception:
                    pass
                self._saved_msg = "Theme Applied!"
            self._saved_flash = 1.5
            self._dirty = True

    def update(self, dt):
        moved = False
        b = self._os.buttons
        for btn, dx, dy in (
            (api.BTN_LEFT, -1, 0),
            (api.BTN_RIGHT, +1, 0),
            (api.BTN_UP, 0, -1),
            (api.BTN_DOWN, 0, +1),
        ):
            try:
                held = b.is_pressed(btn)
            except Exception:
                held = False
            if held:
                self._active_preset_id = None
                self._hold_t[btn] += dt
                t = self._hold_t[btn]
                speed = FAST_PX_PER_S if t > ACCEL_AFTER_S else SLOW_PX_PER_S
                self._cx += dx * speed * dt
                self._cy += dy * speed * dt
                moved = True
            else:
                self._hold_t[btn] = 0.0

        if moved:
            self._clamp_cursor()
            self._sample_color()
            self._dirty = True

        if self._saved_flash > 0:
            self._saved_flash = max(0.0, self._saved_flash - dt)
            self._dirty = True

    def _clamp_cursor(self):
        if self._cx < 0:
            self._cx = 0
        if self._cy < 0:
            self._cy = 0
        if self._cx > PLAY_W - 1:
            self._cx = PLAY_W - 1
        if self._cy > PLAY_H - 1:
            self._cy = PLAY_H - 1

    def _sample_color(self):
        """Read RGB pixel under cursor and assign to the active slot."""
        if not self._bg:
            return
        x = int(self._cx)
        y = int(self._cy)
        i = (y * self._bg_w + x) * 2
        v = (self._bg[i] << 8) | self._bg[i + 1]
        r = ((v >> 11) & 0x1F) << 3
        g = ((v >> 5) & 0x3F) << 2
        b = (v & 0x1F) << 3
        self._rgb = (r | (r >> 5), g | (g >> 6), b | (b >> 5))

        cur_slot = SLOT_KEYS[self._slot_idx]
        self._slots[cur_slot] = self._rgb

        if cur_slot == "PRI" and getattr(self, "_auto_harmonize", True):
            derived = theme.derive_custom_theme(*self._rgb)
            self._slots["BG"] = derived.bg_rgb
            self._slots["CARD"] = derived.card_rgb
            self._slots["SEC"] = derived.teal_rgb
            self._slots["ACC"] = derived.gold_rgb

    # ── render ────────────────────────────────────────────────────────────
    def draw(self, d):
        if not self._dirty:
            return
        self._dirty = False

        if self._bg:
            d.blit(self._bg, 0, PLAY_TOP, self._bg_w, self._bg_h)
        else:
            d.rect(0, PLAY_TOP, PLAY_W, PLAY_H, api.rgb(*self._rgb), fill=True)

        self._draw_header(d)
        widgets.draw_hint(d, "arrows=pick  B=slot  C=preset  A=apply")
        self._draw_cursor(d)
        self._draw_palette_bar(d)

        # ── compact pill toast notification ──────────────────────────────────
        if self._saved_flash > 0:
            msg = getattr(self, "_saved_msg", "Theme Applied!")
            mw = len(msg) * 8
            tx = (SW - mw) // 2
            ty = PLAY_BOT - 48
            d.rect(tx - 8, ty - 3, mw + 16, 14, theme.DOCK_BG, fill=True)
            d.rect(tx - 8, ty - 3, mw + 16, 14, theme.MUTED2, fill=False)
            d.text(msg, tx, ty, theme.TEXT_BRIGHT)

    # ── full palette ribbon with active slot cursor ───────────────────────
    def _draw_palette_bar(self, d):
        swatches = [
            ("PRI", self._slots["PRI"]),
            ("BG", self._slots["BG"]),
            ("CARD", self._slots["CARD"]),
            ("SEC", self._slots["SEC"]),
            ("ACC", self._slots["ACC"]),
        ]

        pw = 56
        ph = 18
        gap = 4
        total_w = len(swatches) * pw + (len(swatches) - 1) * gap
        start_x = (SW - total_w) // 2
        y = PLAY_BOT - ph - 4

        # Background ribbon
        d.rect(start_x - 4, y - 2, total_w + 8, ph + 4, theme.DOCK_BG, fill=True)
        d.rect(start_x - 4, y - 2, total_w + 8, ph + 4, theme.MUTED2, fill=False)

        for i, (label, rgb_tuple) in enumerate(swatches):
            sx = start_x + i * (pw + gap)
            c_val = api.rgb(*rgb_tuple)
            is_active_slot = i == self._slot_idx

            d.rect(sx, y, pw, ph, c_val, fill=True)

            if is_active_slot:
                d.rect(sx - 1, y - 1, pw + 2, ph + 2, api.WHITE, fill=False)
                d.rect(sx - 2, y - 2, pw + 4, ph + 4, theme.PRIMARY, fill=False)
            else:
                d.rect(sx, y, pw, ph, theme.MUTED2, fill=False)

            lum = theme.get_perceived_luminance(*rgb_tuple)
            lbl_c = api.rgb(24, 24, 32) if lum >= 150 else api.WHITE

            slot_text = ">%s<" % label if is_active_slot else label
            lx = sx + (pw - len(slot_text) * 8) // 2
            ly = y + (ph - 8) // 2
            d.text(slot_text, lx, ly, lbl_c)

    # ── header pieces ─────────────────────────────────────────────────────
    def _draw_header(self, d):
        H = widgets.HEADER_H
        fg = theme.STATUS_TEXT
        d.rect(0, 0, SW, H, theme.STATUS_BG, fill=True)
        d.rect(0, H - 1, SW, 1, theme.STATUS_ACCENT, fill=True)
        d.text("COLOR", 6, (H - 8) // 2 + 1, fg)

        cur_slot = SLOT_KEYS[self._slot_idx]
        cur_rgb = self._slots[cur_slot]
        sw_sz = 14
        sw_x = 52
        sw_y = (H - sw_sz) // 2 + 1
        d.rect(sw_x - 1, sw_y - 1, sw_sz + 2, sw_sz + 2, fg, fill=True)
        d.rect(sw_x, sw_y, sw_sz, sw_sz, api.rgb(*cur_rgb), fill=True)

        if getattr(self, "_active_preset_id", None):
            _readout = "%s [%s]" % (theme.PRESETS[self._active_preset_id].name, cur_slot)
        else:
            _readout = "%s: %d %d %d" % (cur_slot, cur_rgb[0], cur_rgb[1], cur_rgb[2])
        slot_title = SLOT_TITLES[cur_slot]
        d.text(slot_title, SW - 6 - len(slot_title) * 8, (H - 8) // 2 + 1, fg)

    # ── crosshair drawing ────────────────────────────────────────────────
    def _draw_cursor(self, d):
        cx = int(self._cx)
        cy = int(self._cy) + PLAY_TOP
        # Outer dark ring + inner white ring + 1-px black dot in the middle.
        # Two colour layers make the cursor visible on ANY background.
        r1, r2 = 7, 5
        d.rect(cx - r1, cy, 2 * r1 + 1, 1, api.BLACK, fill=True)
        d.rect(cx, cy - r1, 1, 2 * r1 + 1, api.BLACK, fill=True)
        d.rect(cx - r2, cy, 2 * r2 + 1, 1, api.WHITE, fill=True)
        d.rect(cx, cy - r2, 1, 2 * r2 + 1, api.WHITE, fill=True)
        # Small open square at the centre, dark outline + light interior
        d.rect(cx - 2, cy - 2, 5, 5, api.BLACK, fill=False)
        d.rect(cx - 1, cy - 1, 3, 3, api.WHITE, fill=False)

    def on_exit(self):
        """Free color splash buffers and sweep GC on exit."""
        self._splash_data = None
        self._bg = None
        try:
            import gc

            gc.collect()
        except Exception:
            pass
