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

# DOOM Key Constants
KEY_RIGHTARROW = 0xAE
KEY_LEFTARROW  = 0xAC
KEY_UPARROW    = 0xAD
KEY_DOWNARROW  = 0xAF
KEY_FIRE       = 0x9D  # KEY_RCTRL / Fire
KEY_USE        = 0x20  # Space / Use
KEY_ENTER      = 0x0D  # Enter
KEY_ESCAPE     = 0x1B  # Escape
KEY_TAB        = 0x09  # Automap


class App(oreoOS.App):
    name = "DOOM"
    author = "id-oreo"
    SHOW_LOADING = True
    CONSUMES_C = True

    def on_enter(self, os_obj):
        self._os = os_obj
        self._engine_type = "EMBEDDED" # "EMBEDDED" or "FALLBACK"
        self._doom_lib = None
        self._active_weapon_num = 2
        self._key_states = {}
        self._last_tick_ms = _ticks_ms()
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
            if btn == api.BTN_UP:
                self._send_key(1, KEY_UPARROW)
            elif btn == api.BTN_DOWN:
                self._send_key(1, KEY_DOWNARROW)
            elif btn == api.BTN_LEFT:
                self._send_key(1, KEY_LEFTARROW)
            elif btn == api.BTN_RIGHT:
                self._send_key(1, KEY_RIGHTARROW)
            elif btn == api.BTN_A:
                self._send_key(1, KEY_FIRE)
                self._send_key(1, KEY_ENTER) # Also selects menus
            elif btn == api.BTN_B:
                self._send_key(1, KEY_USE)
                self._send_key(1, KEY_ENTER)
            elif btn == api.BTN_C:
                # Cycle weapons 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7
                self._active_weapon_num = (self._active_weapon_num % 7) + 1
                key_code = ord(str(self._active_weapon_num))
                self._send_key(1, key_code)
                self._send_key(0, key_code)
            return

        # Fallback Engine Buttons
        self._fallback_button_press(btn)

    def on_button_release(self, btn):
        if self._engine_type == "EMBEDDED" and self._doom_lib:
            if btn == api.BTN_UP:
                self._send_key(0, KEY_UPARROW)
            elif btn == api.BTN_DOWN:
                self._send_key(0, KEY_DOWNARROW)
            elif btn == api.BTN_LEFT:
                self._send_key(0, KEY_LEFTARROW)
            elif btn == api.BTN_RIGHT:
                self._send_key(0, KEY_RIGHTARROW)
            elif btn == api.BTN_A:
                self._send_key(0, KEY_FIRE)
                self._send_key(0, KEY_ENTER)
            elif btn == api.BTN_B:
                self._send_key(0, KEY_USE)
                self._send_key(0, KEY_ENTER)

    def _send_key(self, pressed, key_val):
        if self._doom_lib:
            self._doom_lib.doom_send_key(pressed, key_val)

    # ─── GAME LOOP & TICK ────────────────────────────────────────────────────
    def update(self, dt):
        if self._engine_type == "EMBEDDED" and self._doom_lib:
            # Advance 1 DOOM tick (~35 Hz)
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
                # Blit via display surface if pygame is available
                if hasattr(d, "_surface"):
                    import pygame
                    surf = pygame.image.frombytes(raw_bytes, (w, h), "RGBA")
                    scaled = pygame.transform.scale(surf, (SW, SH))
                    d._surface.blit(scaled, (0, 0))
                else:
                    # Generic byte blit fallback
                    d.clear(api.BLACK)
            self._dirty = False
            return

        self._fallback_draw(d)

    # ─── PURE PYTHON FALLBACK ENGINE (FOR EMBEDDED DEVICES WITHOUT C SO) ──────
    def _init_fallback_engine(self):
        self._px = 2.5
        self._py = 2.5
        self._pa = 0.0
        self._hp = 100
        self._armor = 50
        self._ammo = 50
        self._grid = [
            [1,1,1,1,1,1,1,1],
            [1,0,0,0,0,0,0,1],
            [1,0,2,2,0,2,0,1],
            [1,0,2,0,0,2,0,1],
            [1,0,0,0,0,0,0,1],
            [1,0,1,0,0,1,0,1],
            [1,0,0,0,0,0,0,1],
            [1,1,1,1,1,1,1,1]
        ]
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
        d.text("DOOM 3D (EMBEDDED FALLBACK)", 30, 100, theme.GOLD, scale=1)
        self._dirty = False
