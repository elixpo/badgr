import pygame
import sys
from oreoOS import api

# Make window smaller (2x zoom instead of 3x)
ZOOM = 2

pygame.init()
_screen = pygame.display.set_mode((api.SCREEN_W * ZOOM, api.SCREEN_H * ZOOM))
pygame.display.set_caption("OreoOS Native Sandbox")

# --- Font decoding for _draw_char ---
import base64
_font_b64 = "AAAAAAAAAAAYPDwYGAAYAGZmJAAAAAAAbGz+bP5sbAAYPmA8BnwYAADGzBgwZsYAOGxodtzMdgAYGDAAAAAAAAwYMDAwGAwAMBgMDAwYMAAAZjz/PGYAAAAYGH4YGAAAAAAAAAAYGDAAAAB+AAAAAAAAAAAAGBgABgwYMGDAgAA8Zm52ZmY8ABg4GBgYGH4APGYGHDBg/gA8ZgYcBmY8AAwcPGz+DAwA/mB8BgZmPAA8ZmB8ZmY8AP4GDBgwMDAAPGZmPGZmPAA8ZmY+BmY8AAAYGAAAGBgAABgYAAAYGDAGDBgwGAwGAAAAfgB+AAAAYDAYDBgwYAA8ZgYcGAAYADxmbm5gZjwAGDxmZn5mZgB8ZmZ8ZmZ8ADxmYGBgZjwAeGxmZmZseAD+YGB8YGD+AP5gYHxgYGAAPGZgbmZmPABmZmZ+ZmZmADwYGBgYGDwABgYGBgZmPABmbHhweGxmAGBgYGBgYP4AY3d/a2NjYwBmdn5+bmZmADxmZmZmZjwAfGZmfGBgYAA8ZmZmbjwCAHxmZnx4bGYAPGZgPAZmPAB+GBgYGBgYAGZmZmZmZjwAZmZmZmY8GABjY2Nrf3djAGZmPBg8ZmYAZmZmPBgYGAD+BgwYMGD+ADwwMDAwMDwAgMBgMBgMBgA8DAwMDAw8ABg8ZgAAAAAAAAAAAAAAAP8wGAwAAAAAAAAAPAY+Zj4AYGB8ZmZmfAAAADxmYGY8AAYGPmZmZj4AAAA8Zn5gPAAcMDB8MDAwAAAAPmZmPgY8YGB8ZmZmZgAYADgYGBg8AAYABgYGZjwAYGBmbHhsZgA4GBgYGBg8AAAA7P7W1tYAAAB8ZmZmZgAAADxmZmY8AAAAfGZmfGBgAAA+ZmY+BgYAAHxmYGBgAAAAPGA8BjwAMDB8MDAwHAAAAGZmZmY+AAAAZmZmPBgAAABja393YwAAAGY8GDxmAAAAZmZmPgY8AAD+DBgw/gAOGBhwGBgOABgYGAAYGBgAcBgYDhgYcAB23AAAAAAAAAAAAAAAAAAA"
_font_data = base64.b64decode(_font_b64)

def _rgb565_to_rgb(c):
    r = ((c >> 11) & 0x1F) * 255 // 31
    g = ((c >> 5) & 0x3F) * 255 // 63
    b = (c & 0x1F) * 255 // 31
    return (r, g, b)

def _swap(c):
    return ((c & 0xFF) << 8) | ((c >> 8) & 0xFF)

_LUT_565_TO_RGB = bytearray(65536 * 3)
for c in range(65536):
    r = ((c >> 11) & 0x1F) * 255 // 31
    g = ((c >> 5) & 0x3F) * 255 // 63
    b = (c & 0x1F) * 255 // 31
    _LUT_565_TO_RGB[c * 3]     = r
    _LUT_565_TO_RGB[c * 3 + 1] = g
    _LUT_565_TO_RGB[c * 3 + 2] = b

_clock = pygame.time.Clock()

def _sprite_to_surface(sprite, w, h):
    if isinstance(sprite, tuple):
        sprite = sprite[0]
    
    import struct
    words = struct.unpack_from(">%dH" % (w * h), sprite)
    rgb_bytes = bytearray(w * h * 3)
    lut = _LUT_565_TO_RGB
    has_transparent = False
    for i, c in enumerate(words):
        if c == 0xF81F:
            rgb_bytes[i * 3]     = 255
            rgb_bytes[i * 3 + 1] = 0
            rgb_bytes[i * 3 + 2] = 255
            has_transparent = True
        else:
            p = c * 3
            rgb_bytes[i * 3]     = lut[p]
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

    def clear(self, color=api.BLACK):
        self._surface.fill(_rgb565_to_rgb(color))
        self._dirty = True

    def pixel(self, x, y, color):
        if 0 <= x < api.SCREEN_W and 0 <= y < api.SCREEN_H:
            self._surface.set_at((x, y), _rgb565_to_rgb(color))
            self._dirty = True

    def line(self, x0, y0, x1, y1, color):
        pygame.draw.line(self._surface, _rgb565_to_rgb(color), (x0, y0), (x1, y1))
        self._dirty = True

    def rect(self, x, y, w, h, color, fill=False):
        width = 0 if fill else 1
        pygame.draw.rect(self._surface, _rgb565_to_rgb(color), (x, y, w, h), width)
        self._dirty = True

    def text(self, s, x, y, color=api.WHITE, scale=1):
        rgb_color = _rgb565_to_rgb(color)
        import unicodedata
        s_norm = "".join(c for c in unicodedata.normalize("NFKD", str(s)) if unicodedata.category(c) != "Mn")
        for i, ch in enumerate(s_norm):
            idx = ord(ch) - 32
            if idx < 0 or idx >= 96: idx = 63  # '?' or '_' fallback for unrenderable
            offset = idx * 8
            for py in range(8):
                row = _font_data[offset + py]
                if not row: continue
                for px in range(8):
                    if row & (1 << (7 - px)):
                        self._surface.fill(rgb_color, (x + (i*8 + px)*scale, y + py*scale, scale, scale))
        self._dirty = True

    def blit(self, sprite, x, y, w, h):
        surf = _sprite_to_surface(sprite, w, h)
        self._surface.blit(surf, (x, y))
        self._dirty = True

    def blit_scale(self, sprite, x, y, w, h, scale, dim=0.0):
        surf = _sprite_to_surface(sprite, w, h)
        scaled = pygame.transform.scale(surf, (w * scale, h * scale))
        self._surface.blit(scaled, (x, y))
        self._dirty = True

    def present(self):
        _clock.tick(60)
        if not self._dirty: return
        self._dirty = False
        scaled_surf = pygame.transform.scale(self._surface, (api.SCREEN_W * ZOOM, api.SCREEN_H * ZOOM))
        _screen.blit(scaled_surf, (0, 0))
        pygame.display.flip()

_KEYMAP = [
    (pygame.K_ESCAPE, api.BTN_HOME),
    (pygame.K_SPACE, api.BTN_HOME),
    (pygame.K_RETURN, api.BTN_A),
    (pygame.K_z, api.BTN_A),
    (pygame.K_a, api.BTN_A),
    (pygame.K_x, api.BTN_B),
    (pygame.K_b, api.BTN_B),
    (pygame.K_c, api.BTN_C),
    (pygame.K_UP, api.BTN_UP),
    (pygame.K_DOWN, api.BTN_DOWN),
    (pygame.K_LEFT, api.BTN_LEFT),
    (pygame.K_RIGHT, api.BTN_RIGHT),
]

class Buttons:
    def __init__(self):
        self._curr = {b: 0 for b in api.BUTTONS}
        self._prev = {b: 0 for b in api.BUTTONS}
        import time
        self._press_time = {b: 0 for b in api.BUTTONS}
        self._time = time

    def update(self):
        self._prev = self._curr.copy()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit(0)
                
        keys = pygame.key.get_pressed()
        
        now = self._time.time() * 1000
        # Reset curr for this frame so overlapping keys don't overwrite with 0
        for b in api.BUTTONS:
            self._curr[b] = 0
            
        for key, btn in _KEYMAP:
            is_pressed = 1 if keys[key] else 0
            if is_pressed:
                if not self._curr[btn]:
                    self._press_time[btn] = now
                self._curr[btn] = 1

    def is_pressed(self, btn):
        return self._curr[btn] == 1

    def just_pressed(self, btn):
        return self._curr[btn] == 1 and self._prev[btn] == 0

    def just_released(self, btn):
        return self._curr[btn] == 0 and self._prev[btn] == 1

    def pressed_for_ms(self, btn):
        if not self._curr[btn]:
            return 0
        return int((self._time.time() * 1000) - self._press_time[btn])

def reboot():
    print("Reboot requested!")
    sys.exit(0)

class Pin:
    OUT = 1
    def __init__(self, *a, **k): pass
    def value(self, v): pass

class PWM:
    def __init__(self, *a, **k): pass
    def freq(self, f): pass
    def duty_u16(self, d): pass

class Battery:
    def percent(self): return 100
    def is_charging(self): return True

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
        return self._settings.get(key, default)

    def settings_set(self, key, value):
        self._settings[key] = value
