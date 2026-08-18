"""Native Pygame Display & Hardware Interface for oreoSim.

Provides high-performance desktop emulation for:
  • ST7789V 320x240 RGB565 IPS LCD with pre-baked 65536-entry color LUT
  • Zero-latency chroma-key (0xF81F) transparency sprite blitter
  • D-Pad, tactile push buttons, capacitive touch (C & HOME) with WASD / Arrow keys
  • F11 dynamic window zoom (1x / 2x scale)
  • Robust coordinate bounds protection
"""

import os
import sys
import time

import pygame

from oreoOS import api

# Default scale factor
ZOOM = 1

pygame.init()
_screen = pygame.display.set_mode((api.SCREEN_W * ZOOM, api.SCREEN_H * ZOOM))
pygame.display.set_caption("OreoOS Native Simulator (oreoSim)")

# --- Font decoding for _draw_char ---
import base64

_font_b64 = "AAAAAAAAAAAYPDwYGAAYAGZmJAAAAAAAbGz+bP5sbAAYPmA8BnwYAADGzBgwZsYAOGxodtzMdgAYGDAAAAAAAAwYMDAwGAwAMBgMDAwYMAAAZjz/PGYAAAAYGH4YGAAAAAAAAAAYGDAAAAB+AAAAAAAAAAAAGBgABgwYMGDAgAA8Zm52ZmY8ABg4GBgYGH4APGYGHDBg/gA8ZgYcBmY8AAwcPGz+DAwA/mB8BgZmPAA8ZmB8ZmY8AP4GDBgwMDAAPGZmPGZmPAA8ZmY+BmY8AAAYGAAAGBgAABgYAAAYGDAGDBgwGAwGAAAAfgB+AAAAYDAYDBgwYAA8ZgYcGAAYADxmbm5gZjwAGDxmZn5mZgB8ZmZ8ZmZ8ADxmYGBgZjwAeGxmZmZseAD+YGB8YGD+AP5gYHxgYGAAPGZgbmZmPABmZmZ+ZmZmADwYGBgYGDwABgYGBgZmPABmbHhweGxmAGBgYGBgYP4AY3d/a2NjYwBmdn5+bmZmADxmZmZmZjwAfGZmfGBgYAA8ZmZmbjwCAHxmZnx4bGYAPGZgPAZmPAB+GBgYGBgYAGZmZmZmZjwAZmZmZmY8GABjY2Nrf3djAGZmPBg8ZmYAZmZmPBgYGAD+BgwYMGD+ADwwMDAwMDwAgMBgMBgMBgA8DAwMDAw8ABg8ZgAAAAAAAAAAAAAAAP8wGAwAAAAAAAAAPAY+Zj4AYGB8ZmZmfAAAADxmYGY8AAYGPmZmZj4AAAA8Zn5gPAAcMDB8MDAwAAAAPmZmPgY8YGB8ZmZmZgAYADgYGBg8AAYABgYGZjwAYGBmbHhsZgA4GBgYGBg8AAAA7P7W1tYAAAB8ZmZmZgAAADxmZmY8AAAAfGZmfGBgAAA+ZmY+BgYAAHxmYGBgAAAAPGA8BjwAMDB8MDAwHAAAAGZmZmY+AAAAZmZmPBgAAABja393YwAAAGY8GDxmAAAAZmZmPgY8AAD+DBgw/gAOGBhwGBgOABgYGAAYGBgAcBgYDhgYcAB23AAAAAAAAAAAAAAAAAAA"
_font_data = base64.b64decode(_font_b64)


def _rgb565_to_rgb(c):
    try:
        c_int = int(c) & 0xFFFF
        r = ((c_int >> 11) & 0x1F) * 255 // 31
        g = ((c_int >> 5) & 0x3F) * 255 // 63
        b = (c_int & 0x1F) * 255 // 31
        return (r, g, b)
    except Exception:
        return (0, 0, 0)


_LUT_565_TO_RGB = bytearray(65536 * 3)
for c in range(65536):
    r = ((c >> 11) & 0x1F) * 255 // 31
    g = ((c >> 5) & 0x3F) * 255 // 63
    b = (c & 0x1F) * 255 // 31
    _LUT_565_TO_RGB[c * 3] = r
    _LUT_565_TO_RGB[c * 3 + 1] = g
    _LUT_565_TO_RGB[c * 3 + 2] = b

_clock = pygame.time.Clock()


def _sprite_to_surface(sprite, w, h):
    if isinstance(sprite, (tuple, list)):
        sprite = sprite[0]

    if hasattr(sprite, "tobytes"):
        sprite_bytes = sprite.tobytes()
    elif isinstance(sprite, (bytearray, memoryview)):
        sprite_bytes = bytes(sprite)
    else:
        sprite_bytes = sprite

    import struct

    total_words = min(len(sprite_bytes) // 2, w * h)
    words = struct.unpack_from(">%dH" % total_words, sprite_bytes)
    rgb_bytes = bytearray(w * h * 3)
    lut = _LUT_565_TO_RGB
    has_transparent = False

    for i, c in enumerate(words):
        if c == 0xF81F:
            rgb_bytes[i * 3] = 255
            rgb_bytes[i * 3 + 1] = 0
            rgb_bytes[i * 3 + 2] = 255
            has_transparent = True
        else:
            p = (c & 0xFFFF) * 3
            rgb_bytes[i * 3] = lut[p]
            rgb_bytes[i * 3 + 1] = lut[p + 1]
            rgb_bytes[i * 3 + 2] = lut[p + 2]

    surf = pygame.image.frombuffer(rgb_bytes, (w, h), "RGB")
    if has_transparent:
        surf.set_colorkey((255, 0, 255))
    return surf


class Display(api.Display):
    def __init__(self):
        self._surface = pygame.Surface((api.SCREEN_W, api.SCREEN_H))
        self._dirty = True
        self._brightness = 100

    def clear(self, color=api.BLACK):
        self._surface.fill(_rgb565_to_rgb(color))
        self._dirty = True

    def pixel(self, x, y, color):
        if 0 <= x < api.SCREEN_W and 0 <= y < api.SCREEN_H:
            self._surface.set_at((int(x), int(y)), _rgb565_to_rgb(color))
            self._dirty = True

    def line(self, x0, y0, x1, y1, color):
        try:
            pygame.draw.line(
                self._surface, _rgb565_to_rgb(color), (int(x0), int(y0)), (int(x1), int(y1))
            )
            self._dirty = True
        except Exception:
            pass

    def rect(self, x, y, w, h, color, fill=False):
        try:
            x, y, w, h = int(x), int(y), int(w), int(h)
            if w <= 0 or h <= 0:
                return
            width = 0 if fill else 1
            pygame.draw.rect(self._surface, _rgb565_to_rgb(color), (x, y, w, h), width)
            self._dirty = True
        except Exception:
            pass

    def text(self, s, x, y, color=api.WHITE, scale=1):
        try:
            rgb_color = _rgb565_to_rgb(color)
            scale = max(1, int(scale))
            x, y = int(x), int(y)
            import unicodedata

            s_norm = "".join(
                c for c in unicodedata.normalize("NFKD", str(s)) if unicodedata.category(c) != "Mn"
            )
            for i, ch in enumerate(s_norm):
                idx = ord(ch) - 32
                if idx < 0 or idx >= 96:
                    idx = 63  # '?' fallback for unrenderable
                offset = idx * 8
                for py in range(8):
                    row = _font_data[offset + py]
                    if not row:
                        continue
                    for px in range(8):
                        if row & (1 << (7 - px)):
                            px_x = x + (i * 8 + px) * scale
                            px_y = y + py * scale
                            if 0 <= px_x < api.SCREEN_W and 0 <= px_y < api.SCREEN_H:
                                self._surface.fill(rgb_color, (px_x, px_y, scale, scale))
            self._dirty = True
        except Exception:
            pass

    def blit(self, sprite, x, y, w=None, h=None):
        try:
            if w is None or h is None:
                if isinstance(sprite, tuple) and len(sprite) >= 3:
                    w, h = sprite[1], sprite[2]
                else:
                    return
            surf = _sprite_to_surface(sprite, int(w), int(h))
            self._surface.blit(surf, (int(x), int(y)))
            self._dirty = True
        except Exception:
            pass

    def blit_scale(self, sprite, x, y, w, h, scale, dim=0.0):
        try:
            surf = _sprite_to_surface(sprite, int(w), int(h))
            scaled = pygame.transform.scale(surf, (int(w * scale), int(h * scale)))
            self._surface.blit(scaled, (int(x), int(y)))
            self._dirty = True
        except Exception:
            pass

    def set_brightness(self, pct):
        self._brightness = max(0, min(100, int(pct)))

    def present(self):
        global ZOOM, _screen
        _clock.tick(30)
        if not self._dirty:
            return
        self._dirty = False
        scaled_surf = pygame.transform.scale(
            self._surface, (api.SCREEN_W * ZOOM, api.SCREEN_H * ZOOM)
        )
        _screen.blit(scaled_surf, (0, 0))
        pygame.display.flip()


def toggle_zoom():
    global ZOOM, _screen
    ZOOM = 2 if ZOOM == 1 else 1
    _screen = pygame.display.set_mode((api.SCREEN_W * ZOOM, api.SCREEN_H * ZOOM))
    pygame.display.set_caption(f"OreoOS Native Simulator (oreoSim - {ZOOM}x)")


_KEYMAP = [
    # Primary controls
    (pygame.K_ESCAPE, api.BTN_HOME),
    (pygame.K_SPACE, api.BTN_HOME),
    (pygame.K_h, api.BTN_HOME),
    (pygame.K_RETURN, api.BTN_A),
    (pygame.K_z, api.BTN_A),
    (pygame.K_j, api.BTN_A),
    (pygame.K_BACKSPACE, api.BTN_B),
    (pygame.K_x, api.BTN_B),
    (pygame.K_k, api.BTN_B),
    (pygame.K_c, api.BTN_C),
    (pygame.K_l, api.BTN_C),
    (pygame.K_UP, api.BTN_UP),
    (pygame.K_w, api.BTN_UP),
    (pygame.K_DOWN, api.BTN_DOWN),
    (pygame.K_s, api.BTN_DOWN),
    (pygame.K_LEFT, api.BTN_LEFT),
    (pygame.K_a, api.BTN_LEFT),
    (pygame.K_RIGHT, api.BTN_RIGHT),
    (pygame.K_d, api.BTN_RIGHT),
]


class Buttons:
    def __init__(self):
        self._curr = {b: 0 for b in api.BUTTONS}
        self._prev = {b: 0 for b in api.BUTTONS}
        self._press_time = {b: 0 for b in api.BUTTONS}
        self._time = time

    def reset(self):
        """Cleanly release all keys and reset edge detection states (for transitions & hot-reload)."""
        for b in api.BUTTONS:
            self._curr[b] = 0
            self._prev[b] = 0
            self._press_time[b] = 0
        try:
            pygame.event.pump()
        except Exception:
            pass

    def update(self):
        self._prev = self._curr.copy()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    toggle_zoom()
            elif event.type in (
                getattr(pygame, "WINDOWFOCUSLOST", 32785),
                getattr(pygame, "WINDOWMINIMIZED", 32786),
                getattr(pygame, "ACTIVEEVENT", 1),
            ):
                # Release keys when window focus shifts
                for b in api.BUTTONS:
                    self._curr[b] = 0

        keys = pygame.key.get_pressed()
        now = self._time.time() * 1000

        for b in api.BUTTONS:
            self._curr[b] = 0

        for key, btn in _KEYMAP:
            if keys[key]:
                if not self._curr[btn]:
                    self._press_time[btn] = now
                self._curr[btn] = 1

    def is_pressed(self, btn):
        return self._curr.get(btn, 0) == 1

    def just_pressed(self, btn):
        return self._curr.get(btn, 0) == 1 and self._prev.get(btn, 0) == 0

    def just_released(self, btn):
        return self._curr.get(btn, 0) == 0 and self._prev.get(btn, 0) == 1

    def pressed_for_ms(self, btn):
        if not self._curr.get(btn, 0):
            return 0
        return int((self._time.time() * 1000) - self._press_time.get(btn, 0))


def reboot():
    print("\n\033[96m[oreoSim] Reboot requested — restarting emulator...\033[0m\n")
    try:
        pygame.display.quit()
        pygame.quit()
    except Exception:
        pass
    entry_cmd = getattr(sys, "_oreosim_entry_cmd", None) or (
        [sys.executable, os.path.abspath(sys.argv[0])] + sys.argv[1:]
    )
    os.execv(entry_cmd[0], entry_cmd)


class Pin:
    OUT = 1

    def __init__(self, *a, **k):
        pass

    def value(self, v=None):
        return 0


class PWM:
    def __init__(self, *a, **k):
        pass

    def freq(self, f=None):
        return 1000

    def duty_u16(self, d=None):
        pass


class Battery:
    def percent(self):
        return 100

    def is_charging(self):
        return True


class OS(api.OS):
    def __init__(self):
        self.display = Display()
        self.buttons = Buttons()
        self.leds = None
        self.ir = None
        self.adc = None
        self._quit_requested = False
        self._launch_request = None
        self._settings = {}

    def quit(self):
        self._quit_requested = True

    def launch(self, name):
        self._launch_request = name
        self._quit_requested = True

    def settings_get(self, key, default=None):
        try:
            from oreoOS import settings

            return settings.get(key, default)
        except Exception:
            return self._settings.get(key, default)

    def settings_set(self, key, value):
        self._settings[key] = value
        try:
            from oreoOS import settings

            settings.set(key, value)
        except Exception:
            pass
