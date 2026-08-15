"""Music — Spotify Connect & BLE Media Remote for Oreo OS.

Zero-Config Onboarding:
  • Displays a dynamic QR Code for http://<badge-ip>/spotify on phone.
  • 1-Tap phone setup pushes OAuth credentials directly to badge over LAN.
  • Live playback sync (Track, Artist, Album, Progress, Volume, Device).
  • 60fps smooth progress bar interpolation + animated 12-band equalizer.
  • Offline demo fallback playlist for testing.

Controls:
  A        Play / Pause toggle (or enter Demo mode on setup screen)
  RIGHT    Next track (skip)
  LEFT     Previous track (restart/prev)
  UP       Volume Up (+5%)
  DOWN     Volume Down (-5%)
  B        Toggle Mode (Spotify <-> Demo)
  C        Open / Close Setup QR Screen
  HOME     Exit to launcher drawer
"""

import math
import time
import oreoOS
from oreoOS import api, theme, widgets

try:
    from .spotify import SpotifyClient
    from .qr import QRCode
except Exception:
    try:
        from apps_market.Music.src.spotify import SpotifyClient
        from apps_market.Music.src.qr import QRCode
    except Exception:
        from apps.Music.src.spotify import SpotifyClient
        from apps.Music.src.qr import QRCode

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


def _get_badge_ip():
    try:
        from oreoWare import wifi
        ip = wifi.ip()
        if ip and ip != "0.0.0.0":
            return ip
    except Exception:
        pass
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "192.168.4.1"


class App(oreoOS.App):
    name         = "Music"
    SHOW_LOADING = False
    CONSUMES_C   = True

    def on_enter(self, os):
        self._os = os
        self._is_playing = True
        self._volume = 70
        self._progress = 45.0
        self._duration = 230.0
        self._title = "Starboy"
        self._artist = "The Weeknd, Daft Punk"
        self._album = "Starboy"
        self._device_name = ""
        self._shuffle = False
        self._repeat = "off"
        self._track_idx = 0

        self._mode = "DEMO"  # 'SPOTIFY' or 'DEMO'
        self._show_qr = False

        # Equalizer bar harmonics (12 frequency channels)
        self._eq_speeds = [3.2, 4.5, 5.1, 2.8, 6.0, 4.2, 5.5, 3.8, 4.9, 6.2, 3.5, 4.1]
        self._eq_phases = [i * 0.52 for i in range(12)]
        self._eq_heights = [4.0] * 12
        self._eq_peaks   = [4.0] * 12

        self._anim_t = 0.0
        self._last_tick = _ticks_ms()
        self._last_poll_ms = 0
        self._last_check_token_ms = 0
        self._vol_toast_t = 0.0
        self._dirty = True

        # QR Code state
        self._qr_url = ""
        self._qr_matrix = None

        # Initialize Spotify Client
        token = None
        refresh_token = None
        client_id = None
        client_secret = None

        try:
            from oreoOS import config
            token = getattr(config, "SPOTIFY_TOKEN", None) or getattr(config, "SPOTIFY_ACCESS_TOKEN", None)
            refresh_token = getattr(config, "SPOTIFY_REFRESH_TOKEN", None)
            client_id = getattr(config, "SPOTIFY_CLIENT_ID", None)
            client_secret = getattr(config, "SPOTIFY_CLIENT_SECRET", None)
        except Exception:
            pass

        self._spotify = SpotifyClient(token=token, refresh_token=refresh_token,
                                      client_id=client_id, client_secret=client_secret)

        if self._spotify.is_configured():
            self._mode = "SPOTIFY"
            self._poll_spotify()
        else:
            # Generate QR code for local portal
            self._build_qr()
            self._show_qr = True

    def on_exit(self):
        pass

    def _build_qr(self):
        ip = _get_badge_ip()
        self._qr_url = "http://" + ip + "/spotify"
        try:
            self._qr_matrix = QRCode.encode(self._qr_url)
        except Exception:
            self._qr_matrix = None

    def _poll_spotify(self):
        if not self._spotify.is_configured():
            return
        state = self._spotify.get_playback()
        if state and state.get("connected"):
            if state.get("active"):
                self._title = state.get("title", self._title)
                self._artist = state.get("artist", self._artist)
                self._album = state.get("album", "")
                self._is_playing = state.get("is_playing", self._is_playing)
                self._duration = state.get("duration_s", self._duration)
                self._progress = state.get("progress_s", self._progress)
                self._volume = state.get("volume", self._volume)
                self._device_name = state.get("device_name", "")
                self._shuffle = state.get("shuffle", False)
                self._repeat = state.get("repeat", "off")
            else:
                self._title = "No Active Playback"
                self._artist = "Open Spotify on phone/PC"
                self._is_playing = False
        self._dirty = True

    def on_button_press(self, btn):
        if self._show_qr:
            if btn in (api.BTN_A, api.BTN_B):
                # Switch to demo mode
                self._show_qr = False
                self._mode = "DEMO"
            elif btn == api.BTN_C:
                self._show_qr = False
            self._dirty = True
            return

        if btn == api.BTN_A:
            self._is_playing = not self._is_playing
            if self._mode == "SPOTIFY" and self._spotify.is_configured():
                if self._is_playing:
                    self._spotify.play()
                else:
                    self._spotify.pause()
        elif btn == api.BTN_RIGHT:
            if self._mode == "SPOTIFY" and self._spotify.is_configured():
                self._spotify.next_track()
                self._progress = 0.0
                self._last_poll_ms = _ticks_ms() - 2000
            else:
                self._track_idx = (self._track_idx + 1) % len(DEMO_TRACKS)
                t = DEMO_TRACKS[self._track_idx]
                self._title, self._artist, self._duration = t["title"], t["artist"], t["duration"]
                self._progress = 0.0
        elif btn == api.BTN_LEFT:
            if self._mode == "SPOTIFY" and self._spotify.is_configured():
                self._spotify.prev_track()
                self._progress = 0.0
                self._last_poll_ms = _ticks_ms() - 2000
            else:
                self._track_idx = (self._track_idx - 1) % len(DEMO_TRACKS)
                t = DEMO_TRACKS[self._track_idx]
                self._title, self._artist, self._duration = t["title"], t["artist"], t["duration"]
                self._progress = 0.0
        elif btn == api.BTN_UP:
            self._volume = min(100, self._volume + 5)
            self._vol_toast_t = 1.8
            if self._mode == "SPOTIFY" and self._spotify.is_configured():
                self._spotify.set_volume(self._volume)
        elif btn == api.BTN_DOWN:
            self._volume = max(0, self._volume - 5)
            self._vol_toast_t = 1.8
            if self._mode == "SPOTIFY" and self._spotify.is_configured():
                self._spotify.set_volume(self._volume)
        elif btn == api.BTN_B:
            if self._mode == "SPOTIFY":
                self._mode = "DEMO"
            else:
                if self._spotify.is_configured():
                    self._mode = "SPOTIFY"
                else:
                    self._build_qr()
                    self._show_qr = True
        elif btn == api.BTN_C:
            self._build_qr()
            self._show_qr = not self._show_qr

        self._dirty = True

    def update(self, dt):
        now = _ticks_ms()
        self._last_tick = now

        self._anim_t += dt
        if self._vol_toast_t > 0:
            self._vol_toast_t = max(0.0, self._vol_toast_t - dt)

        # Check for newly saved token from local web portal
        if _ticks_diff(now, self._last_check_token_ms) > 1500:
            self._last_check_token_ms = now
            if not self._spotify.is_configured():
                if self._spotify.reload_persisted():
                    self._mode = "SPOTIFY"
                    self._show_qr = False
                    self._poll_spotify()

        # Smooth local progress interpolation
        if self._is_playing and not self._show_qr:
            self._progress += dt
            if self._progress >= self._duration:
                if self._mode == "DEMO":
                    self._track_idx = (self._track_idx + 1) % len(DEMO_TRACKS)
                    t = DEMO_TRACKS[self._track_idx]
                    self._title, self._artist, self._duration = t["title"], t["artist"], t["duration"]
                self._progress = 0.0

        # Periodic Spotify sync
        if self._mode == "SPOTIFY" and self._spotify.is_configured():
            if _ticks_diff(now, self._last_poll_ms) > 2500:
                self._last_poll_ms = now
                self._poll_spotify()

        # Animate Equalizer bars
        for i in range(12):
            if self._is_playing and not self._show_qr:
                speed = self._eq_speeds[i]
                phase = self._eq_phases[i]
                val = abs(math.sin(self._anim_t * speed + phase)) * 0.7 +                       abs(math.cos(self._anim_t * speed * 0.5 + phase * 1.3)) * 0.3
                target_h = 4 + val * 38
            else:
                target_h = 2.0

            self._eq_heights[i] += (target_h - self._eq_heights[i]) * 0.25
            if self._eq_heights[i] > self._eq_peaks[i]:
                self._eq_peaks[i] = self._eq_heights[i]
            else:
                self._eq_peaks[i] = max(2.0, self._eq_peaks[i] - dt * 18.0)

        self._dirty = True

    def draw(self, d):
        if not self._dirty:
            return

        d.clear(COL_BG)

        # ── QR Code Setup Screen ──────────────────────────────────────────
        if self._show_qr:
            widgets.draw_header(d, "LINK SPOTIFY")

            card_x, card_y, card_w, card_h = 16, widgets.HEADER_H + 6, SW - 32, SH - widgets.HEADER_H - widgets.HINT_H - 12
            d.rect(card_x, card_y, card_w, card_h, COL_CARD, fill=True)
            d.rect(card_x, card_y, card_w, card_h, COL_SPOTIFY, fill=False)

            # Draw QR Code if available
            if self._qr_matrix:
                n = len(self._qr_matrix)
                # Maximize size within card
                scale = max(2, min(4, (card_h - 48) // n))
                qr_px = n * scale
                qr_x = card_x + (card_w - qr_px) // 2
                qr_y = card_y + 8

                # White background container
                pad = 4
                d.rect(qr_x - pad, qr_y - pad, qr_px + pad * 2, qr_px + pad * 2, api.WHITE, fill=True)

                for r in range(n):
                    row = self._qr_matrix[r]
                    for c in range(n):
                        if row[c]:
                            d.rect(qr_x + c * scale, qr_y + r * scale, scale, scale, api.BLACK, fill=True)

                text_y = qr_y + qr_px + pad + 8
            else:
                text_y = card_y + 30

            caption = "Scan with phone camera"
            d.text(caption, card_x + (card_w - len(caption) * 8) // 2, text_y, COL_SPOTIFY)

            url_txt = self._qr_url
            if len(url_txt) > 30: url_txt = url_txt[:28] + ".."
            d.text(url_txt, card_x + (card_w - len(url_txt) * 8) // 2, text_y + 16, api.WHITE)

            widgets.draw_hint(d, "A=demo mode  C=close")
            self._dirty = False
            return

        # ── Normal Player Screen ──────────────────────────────────────────
        header_title = "SPOTIFY CONNECT" if self._mode == "SPOTIFY" else "NOW PLAYING (DEMO)"
        widgets.draw_header(d, header_title)

        # Track Card
        card_x, card_y, card_w, card_h = 10, widgets.HEADER_H + 6, SW - 20, 58
        d.rect(card_x, card_y, card_w, card_h, COL_CARD, fill=True)
        d.rect(card_x, card_y, card_w, card_h, api.rgb(50, 54, 68), fill=False)

        # Icon box
        icon_x, icon_y, icon_sz = card_x + 8, card_y + 8, 42
        d.rect(icon_x, icon_y, icon_sz, icon_sz, COL_SPOTIFY, fill=True)
        d.text("o/", icon_x + 12, icon_y + 14, api.WHITE)

        # Title
        title_str = self._title
        if len(title_str) > 18: title_str = title_str[:16] + ".."
        d.text(title_str, icon_x + icon_sz + 10, card_y + 12, api.WHITE)

        # Artist
        artist_str = self._artist
        if len(artist_str) > 22: artist_str = artist_str[:20] + ".."
        d.text(artist_str, icon_x + icon_sz + 10, card_y + 26, COL_MUTED)

        # Device tag
        tag = "[" + (self._device_name or self._mode) + "]"
        if len(tag) > 16: tag = tag[:14] + "..]"
        d.text(tag, card_x + card_w - len(tag) * 8 - 8, card_y + 38, COL_SPOTIFY)

        # Equalizer
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

            d.rect(bx, base_y - bh, bar_w, bh, COL_SPOTIFY, fill=True)
            d.rect(bx, base_y - bh, bar_w, 1, api.WHITE, fill=True)
            d.rect(bx, base_y - peak_h - 2, bar_w, 2, theme.GOLD, fill=True)

        # Scrubber
        prog_y = eq_box_y + eq_box_h + 10
        cur_str = _format_time(self._progress)
        tot_str = _format_time(self._duration)

        d.text(cur_str, 12, prog_y - 1, COL_MUTED)
        d.text(tot_str, SW - len(tot_str) * 8 - 12, prog_y - 1, COL_MUTED)

        bar_start_x = 12 + len(cur_str) * 8 + 8
        bar_end_x   = SW - len(tot_str) * 8 - 20
        bar_total_w = max(20, bar_end_x - bar_start_x)

        ratio = min(1.0, max(0.0, self._progress / max(1.0, self._duration)))
        fill_w = int(bar_total_w * ratio)

        d.rect(bar_start_x, prog_y + 2, bar_total_w, 4, COL_BAR_BG, fill=True)
        if fill_w > 0:
            d.rect(bar_start_x, prog_y + 2, fill_w, 4, COL_SPOTIFY, fill=True)
        knob_x = bar_start_x + fill_w
        d.rect(knob_x - 2, prog_y, 4, 8, api.WHITE, fill=True)

        # Status
        stat_y = prog_y + 16
        play_symbol = "> PLAYING" if self._is_playing else "|| PAUSED"
        d.text(play_symbol, 16, stat_y, COL_SPOTIFY if self._is_playing else theme.GOLD)

        vol_str = "VOL: %d%%" % self._volume
        d.text(vol_str, SW - len(vol_str) * 8 - 16, stat_y, COL_MUTED)

        widgets.draw_hint(d, "A=play  <>=skip  ^v=vol  C=link")
        self._dirty = False
