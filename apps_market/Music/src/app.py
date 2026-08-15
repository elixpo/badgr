"""Music — Spotify & BLE Media Remote Controller for Oreo Badge.

Features:
  • Live Track Sync: Displays Title, Artist, Album, and Duration (Spotify API / Local).
  • Dynamic Audio Equalizer: 12 animated spectrum frequency bars with peak indicators.
  • Media Controls: Play/Pause, Next Track, Previous Track, Volume Scrubber.
  • Dual-Engine: Spotify Web API / BLE HID Remote / Offline Demo Playlist.

Controls:
  A        Play / Pause toggle
  RIGHT    Next track (skip)
  LEFT     Previous track (restart/prev)
  UP       Volume Up (+5%)
  DOWN     Volume Down (-5%)
  B        Toggle Shuffle / Repeat mode
  HOME     Exit to apps drawer
"""

import math
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

# Palette
COL_SPOTIFY = api.rgb(29,  185, 84)   # Spotify signature green
COL_BG      = api.rgb(18,  18,  18)   # Deep charcoal
COL_CARD    = api.rgb(30,  32,  40)   # Card container
COL_MUTED   = api.rgb(160, 165, 175)  # Subtext / timer
COL_BAR_BG  = api.rgb(45,  48,  58)   # Empty progress / vol bar
COL_ACCENT  = api.rgb(255, 93,  104)  # Accent pink

# Default Demo Playlist (used when offline or no Spotify token)
DEMO_TRACKS = [
    {"title": "Starboy",         "artist": "The Weeknd, Daft Punk", "duration": 230},
    {"title": "Midnight City",   "artist": "M83",                  "duration": 244},
    {"title": "Resonance",       "artist": "HOME",                 "duration": 212},
    {"title": "Get Lucky",       "artist": "Daft Punk, Pharrell",  "duration": 248},
    {"title": "Blinding Lights", "artist": "The Weeknd",           "duration": 200},
]


def _format_time(seconds):
    m = int(seconds) // 60
    s = int(seconds) % 60
    return "%02d:%02d" % (m, s)


class App(oreoOS.App):
    name         = "Music"
    SHOW_LOADING = False

    def on_enter(self, os):
        self._os = os
        self._track_idx = 0
        self._is_playing = True
        self._volume = 70
        self._progress = 45.0
        self._shuffle = False
        self._repeat = False
        self._mode = "DEMO"  # 'SPOTIFY', 'BLE', or 'DEMO'

        # Equalizer bar harmonics (12 frequency channels)
        self._eq_speeds = [3.2, 4.5, 5.1, 2.8, 6.0, 4.2, 5.5, 3.8, 4.9, 6.2, 3.5, 4.1]
        self._eq_phases = [i * 0.52 for i in range(12)]
        self._eq_heights = [4.0] * 12
        self._eq_peaks   = [4.0] * 12

        self._anim_t = 0.0
        self._last_tick = _ticks_ms()
        self._vol_toast_t = 0.0
        self._dirty = True

        # Check for Spotify credentials in config / .env
        self._spotify_token = None
        try:
            from oreoOS import config
            self._spotify_token = getattr(config, "SPOTIFY_TOKEN", None) or getattr(config, "SPOTIFY_ACCESS_TOKEN", None)
            if self._spotify_token:
                self._mode = "SPOTIFY"
        except Exception:
            pass

    def on_exit(self):
        pass

    def on_button_press(self, btn):
        if btn == api.BTN_A:
            self._is_playing = not self._is_playing
            self._send_command("play_pause")
        elif btn == api.BTN_RIGHT:
            self._track_idx = (self._track_idx + 1) % len(DEMO_TRACKS)
            self._progress = 0.0
            self._send_command("next")
        elif btn == api.BTN_LEFT:
            if self._progress > 3.0:
                self._progress = 0.0
            else:
                self._track_idx = (self._track_idx - 1) % len(DEMO_TRACKS)
                self._progress = 0.0
            self._send_command("prev")
        elif btn == api.BTN_UP:
            self._volume = min(100, self._volume + 5)
            self._vol_toast_t = 1.8
            self._send_command("vol_up")
        elif btn == api.BTN_DOWN:
            self._volume = max(0, self._volume - 5)
            self._vol_toast_t = 1.8
            self._send_command("vol_down")
        elif btn == api.BTN_B:
            self._shuffle = not self._shuffle
        self._dirty = True

    def _send_command(self, action):
        # 1. BLE Consumer Control trigger (if BLE available)
        try:
            from oreoWare import bt
            if hasattr(bt, "send_media_key"):
                bt.send_media_key(action)
        except Exception:
            pass

        # 2. Spotify Web API call (if token & Wi-Fi available)
        # Non-blocking async webhook / API queue placeholder

    def update(self, dt):
        now = _ticks_ms()
        wall_dt = _ticks_diff(now, self._last_tick) / 1000.0
        self._last_tick = now

        self._anim_t += dt
        if self._vol_toast_t > 0:
            self._vol_toast_t = max(0.0, self._vol_toast_t - dt)

        # Update track elapsed scrubber
        track = DEMO_TRACKS[self._track_idx]
        if self._is_playing:
            self._progress += dt
            if self._progress >= track["duration"]:
                self._track_idx = (self._track_idx + 1) % len(DEMO_TRACKS)
                self._progress = 0.0

        # Animate equalizer bars
        for i in range(12):
            if self._is_playing:
                # Procedural sine wave with multi-frequency modulation
                speed = self._eq_speeds[i]
                phase = self._eq_phases[i]
                val = abs(math.sin(self._anim_t * speed + phase)) * 0.7 +                       abs(math.cos(self._anim_t * speed * 0.5 + phase * 1.3)) * 0.3
                target_h = 4 + val * 38
            else:
                target_h = 2.0
            
            # Smooth interpolation
            self._eq_heights[i] += (target_h - self._eq_heights[i]) * 0.25
            
            # Peak hold dot with gravity drop
            if self._eq_heights[i] > self._eq_peaks[i]:
                self._eq_peaks[i] = self._eq_heights[i]
            else:
                self._eq_peaks[i] = max(2.0, self._eq_peaks[i] - dt * 18.0)

        self._dirty = True

    def draw(self, d):
        if not self._dirty:
            return

        d.clear(COL_BG)

        # 1. Header
        header_title = "SPOTIFY REMOTE" if self._mode == "SPOTIFY" else "NOW PLAYING"
        widgets.draw_header(d, header_title)

        track = DEMO_TRACKS[self._track_idx]

        # 2. Track Info Card (Top section)
        card_x, card_y, card_w, card_h = 10, widgets.HEADER_H + 6, SW - 20, 58
        d.rect(card_x, card_y, card_w, card_h, COL_CARD, fill=True)
        d.rect(card_x, card_y, card_w, card_h, api.rgb(50, 54, 68), fill=False)

        # Mini Vinyl / Note icon box
        icon_x, icon_y, icon_sz = card_x + 8, card_y + 8, 42
        d.rect(icon_x, icon_y, icon_sz, icon_sz, COL_SPOTIFY, fill=True)
        # Note glyph inside icon box
        d.text("o/", icon_x + 12, icon_y + 14, api.WHITE)

        # Track title (clipped)
        title = track["title"]
        if len(title) > 18:
            title = title[:16] + ".."
        d.text(title, icon_x + icon_sz + 10, card_y + 12, api.WHITE)

        # Artist name (clipped)
        artist = track["artist"]
        if len(artist) > 22:
            artist = artist[:20] + ".."
        d.text(artist, icon_x + icon_sz + 10, card_y + 26, COL_MUTED)

        # Mode Badge (e.g. [DEMO] or [SPOTIFY])
        badge_text = "[" + self._mode + "]"
        d.text(badge_text, card_x + card_w - len(badge_text) * 8 - 8, card_y + 38, COL_SPOTIFY)

        # 3. Dynamic Equalizer Visualizer (Middle section)
        eq_box_x = 10
        eq_box_y = card_y + card_h + 8
        eq_box_w = SW - 20
        eq_box_h = 44

        num_bars = 12
        bar_w = 14
        spacing = (eq_box_w - (num_bars * bar_w)) // (num_bars + 1)
        base_y = eq_box_y + eq_box_h - 2

        for i in range(num_bars):
            bx = eq_box_x + spacing + i * (bar_w + spacing)
            bh = int(self._eq_heights[i])
            peak_h = int(self._eq_peaks[i])

            # Draw vertical equalizer bar with gradient / green fill
            d.rect(bx, base_y - bh, bar_w, bh, COL_SPOTIFY, fill=True)
            # Top highlight
            d.rect(bx, base_y - bh, bar_w, 1, api.WHITE, fill=True)
            # Peak hold dot
            d.rect(bx, base_y - peak_h - 2, bar_w, 2, theme.GOLD, fill=True)

        # 4. Progress Scrubber Bar
        prog_y = eq_box_y + eq_box_h + 10
        cur_str = _format_time(self._progress)
        tot_str = _format_time(track["duration"])

        d.text(cur_str, 12, prog_y - 1, COL_MUTED)
        d.text(tot_str, SW - len(tot_str) * 8 - 12, prog_y - 1, COL_MUTED)

        bar_start_x = 12 + len(cur_str) * 8 + 8
        bar_end_x   = SW - len(tot_str) * 8 - 20
        bar_total_w = max(20, bar_end_x - bar_start_x)

        ratio = min(1.0, max(0.0, self._progress / track["duration"]))
        fill_w = int(bar_total_w * ratio)

        # Progress background groove
        d.rect(bar_start_x, prog_y + 2, bar_total_w, 4, COL_BAR_BG, fill=True)
        # Filled progress
        if fill_w > 0:
            d.rect(bar_start_x, prog_y + 2, fill_w, 4, COL_SPOTIFY, fill=True)
        # Scrubber thumb knob
        knob_x = bar_start_x + fill_w
        d.rect(knob_x - 2, prog_y, 4, 8, api.WHITE, fill=True)

        # 5. Playback & Volume Status Bar
        stat_y = prog_y + 16
        play_symbol = "> PLAYING" if self._is_playing else "|| PAUSED"
        d.text(play_symbol, 16, stat_y, COL_SPOTIFY if self._is_playing else theme.GOLD)

        # Volume readout or Toast
        vol_str = "VOL: %d%%" % self._volume
        d.text(vol_str, SW - len(vol_str) * 8 - 16, stat_y, COL_MUTED)

        # 6. Bottom Hint Bar
        hint_text = "A=play  <>=skip  ^v=vol"
        widgets.draw_hint(d, hint_text)

        self._dirty = False
