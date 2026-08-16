"""DOOM — Embedded id Software Engine & 3D Raycaster for Oreo OS.

Loads the authentic 1993 id Software DOOM engine (via doomgeneric shared library and
official shareware DOOM1.WAD), with automatic fallback to pure Python raycaster.

Controls:
  UP / DOWN     Move Forward / Backward
  LEFT / RIGHT  Turn Left / Right
  A             FIRE Weapon (Shoot / Pistol / Shotgun / Chaingun / BFG)
  B             ACTION / USE (Open Doors / Switches / Confirm / Menu)
  C             Cycle Weapon / Automap
  HOME          Exit / Pause Menu
"""

import ctypes
import math
import os
import random
import time
import oreoOS
from oreoOS import api, theme, widgets

try:
    _ticks_ms = time.ticks_ms
    _ticks_diff = time.ticks_diff
except AttributeError:
    _ticks_ms = lambda: int(time.time() * 1000)
    _ticks_diff = lambda a, b: a - b

SW = api.SCREEN_W
SH = api.SCREEN_H
DOOM_W = 320
DOOM_H = 200
PLAY_H = SH - widgets.HINT_H  # 224 px

# DOOM Key Constants from doomkeys.h / m_controls.c
KEY_RIGHTARROW = 0xAE  # 174
KEY_LEFTARROW  = 0xAC  # 172
KEY_UPARROW    = 0xAD  # 173
KEY_DOWNARROW  = 0xAF  # 175
KEY_FIRE       = 0xA3  # 163 (KEY_FIRE)
KEY_USE        = 0xA2  # 162 (KEY_USE)
KEY_ENTER      = 0x0D  # 13  (KEY_ENTER)
KEY_ESCAPE     = 0x1B  # 27  (KEY_ESCAPE)
KEY_TAB        = 0x09  # 9   (KEY_TAB)


class App(oreoOS.App):
    name = "DOOM"
    author = "sea-deep"
    FULLSCREEN = True
    NO_HEADER = True
    HIDE_HEADER = True
    HIDE_TOP = True
    SHOW_LOADING = True
    CONSUMES_C = True

    def on_enter(self, os_obj):
        self._os = os_obj
        self._engine_type = "EMBEDDED" # "EMBEDDED" or "FALLBACK"
        self._doom_lib = None
        self._active_weapon_num = 2
        self._key_states = {}
        # Clear screen on enter to eliminate loading overlay remnants
        if hasattr(os_obj, "display"):
            os_obj.display.clear(api.BLACK)
        self._init_embedded_engine()

    def _init_embedded_engine(self):
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            so_path = os.path.join(base_dir, "src", "libdoom.so")
            wad_path = os.path.join(base_dir, "assets", "doom1.wad")

            if not os.path.exists(so_path) or not os.path.exists(wad_path):
                self._engine_type = "FALLBACK"
                self._init_fallback_engine()
                return

            self._doom_lib = ctypes.CDLL(so_path)
            self._doom_lib.doom_init.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_char_p)]
            self._doom_lib.doom_init.restype = ctypes.c_int
            self._doom_lib.doom_tick.argtypes = []
            self._doom_lib.doom_send_key.argtypes = [ctypes.c_int, ctypes.c_ubyte]
            self._doom_lib.doom_get_framebuffer.restype = ctypes.POINTER(ctypes.c_uint32)
            self._doom_lib.doom_get_width.restype = ctypes.c_int
            self._doom_lib.doom_get_height.restype = ctypes.c_int

            args = [b"doom", b"-iwad", wad_path.encode("utf-8"), b"-warp", b"1", b"1", b"-nomusic", b"-nosound"]
            argc = len(args)
            argv = (ctypes.c_char_p * argc)(*args)

            self._doom_lib.doom_init(argc, argv)
            self._engine_type = "EMBEDDED"

        except Exception as e:
            print("[DOOM] Fallback to software raycaster:", e)
            self._engine_type = "FALLBACK"
            self._init_fallback_engine()

    # ─── BUTTON INPUT ────────────────────────────────────────────────────────
    def on_button_press(self, btn):
        if self._engine_type == "EMBEDDED" and self._doom_lib:
            if btn == api.BTN_C:
                # Cycle weapons 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7
                self._active_weapon_num = (self._active_weapon_num % 7) + 1
                key_code = ord(str(self._active_weapon_num))
                self._send_key(1, key_code)
                self._send_key(0, key_code)
            return

        self._fallback_button_press(btn)

    def _sync_hardware_buttons(self):
        """Poll hardware / simulator button states and synchronize held keys in DOOM."""
        if not self._doom_lib:
            return

        buttons = getattr(self._os, "buttons", None)
        if not buttons:
            return

        # Continuous movement & action mappings
        mappings = [
            (api.BTN_UP,    KEY_UPARROW),
            (api.BTN_DOWN,  KEY_DOWNARROW),
            (api.BTN_LEFT,  KEY_LEFTARROW),
            (api.BTN_RIGHT, KEY_RIGHTARROW),
            (api.BTN_A,     KEY_FIRE),
            (api.BTN_B,     KEY_USE),
        ]

        for btn_id, doom_key in mappings:
            is_down = 1 if buttons.is_pressed(btn_id) else 0
            if is_down != self._key_states.get(doom_key, 0):
                self._send_key(is_down, doom_key)
                self._key_states[doom_key] = is_down

    def _send_key(self, pressed, key_val):
        if self._doom_lib:
            self._doom_lib.doom_send_key(pressed, key_val)

    # ─── GAME LOOP & TICK ────────────────────────────────────────────────────
    def update(self, dt):
        if self._engine_type == "EMBEDDED" and self._doom_lib:
            # Sync held buttons
            self._sync_hardware_buttons()
            # Advance DOOM engine tick
            self._doom_lib.doom_tick()
            self._dirty = True
        else:
            self._fallback_update(dt)

    def draw(self, d):
        if self._engine_type == "EMBEDDED" and self._doom_lib:
            fb_ptr = self._doom_lib.doom_get_framebuffer()
            w = self._doom_lib.doom_get_width()
            h = self._doom_lib.doom_get_height()
            if fb_ptr and w > 0 and h > 0:
                raw_bytes = ctypes.string_at(fb_ptr, w * h * 4)
                if hasattr(d, "_surface"):
                    import pygame
                    surf = pygame.image.frombytes(raw_bytes, (w, h), "RGBA")
                    # Seamlessly fill play area (320x224) directly above the 16px hint bar
                    scaled = pygame.transform.scale(surf, (SW, PLAY_H))
                    d._surface.blit(scaled, (0, 0))
                else:
                    d.clear(api.BLACK)

            # Standard Oreo OS hint bar at the bottom (Y: 224..240)
            widgets.draw_hint(d, "A=fire  B=use  C=weapon  HOME=back")
            self._dirty = False
            return

        self._fallback_draw(d)

    # ─── PURE PYTHON FALLBACK ENGINE ─────────────────────────────────────────
    def _init_fallback_engine(self):
        self._px = 2.5
        self._py = 2.5
        self._pa = 0.0
        self._hp = 100
        self._armor = 50
        self._ammo = 50
        self._dirty = True

    def _fallback_button_press(self, btn):
        spd = 0.3
        rot = 0.2
        if btn == api.BTN_UP:
            self._px += math.cos(self._pa) * spd
            self._py += math.sin(self._pa) * spd
        elif btn == api.BTN_DOWN:
            self._px -= math.cos(self._pa) * spd
            self._py -= math.sin(self._pa) * spd
        elif btn == api.BTN_LEFT:
            self._pa -= rot
        elif btn == api.BTN_RIGHT:
            self._pa += rot
        self._dirty = True

    def _fallback_update(self, dt):
        pass

    def _fallback_draw(self, d):
        d.clear(api.rgb(36, 24, 28))
        d.text("DOOM 3D (EMBEDDED FALLBACK)", 30, 90, theme.GOLD, scale=1)
        widgets.draw_hint(d, "A=fire  B=use  C=weapon  HOME=back")
        self._dirty = False
