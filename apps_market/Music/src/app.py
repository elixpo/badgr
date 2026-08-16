"""Music — Spotify Connect & Media Player for Oreo OS.

Features:
  • Real-time Spotify Playback Sync (Track, Artist, Album, Duration, Progress, Volume).
  • High-Resolution Album Cover Art photo rendering with memory caching.
  • Smooth, natural left-scrolling marquee with start/end reading pauses.
  • Spacious 240x240 layout with dedicated timeline card & transport controls.
  • Full hardware controls (Play/Pause, Skip Next/Prev, Volume adjustment).
  • Offline Demo fallback playlist when not linked to Spotify.

Controls:
  A        Play / Pause toggle
  RIGHT    Next track (Skip)
  LEFT     Previous track
  UP       Volume Up (+5%)
  DOWN     Volume Down (-5%)
  B        Toggle Mode (Spotify <-> Demo)
  C        Open / Close Setup QR Screen
  HOME     Exit to launcher drawer
"""

import time
import oreoOS
from oreoOS import api, theme, widgets

try:
    from .spotify import SpotifyClient, fetch_cover_art_rgb565, create_relay_session, poll_relay_session, save_credentials
    from .qr import QRCode
except Exception:
    try:
        from apps_market.Music.src.spotify import SpotifyClient, fetch_cover_art_rgb565, create_relay_session, poll_relay_session, save_credentials
        from apps_market.Music.src.qr import QRCode
    except Exception:
        from apps.Music.src.spotify import SpotifyClient, fetch_cover_art_rgb565, create_relay_session, poll_relay_session, save_credentials
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
COL_SPOTIFY  = api.rgb(29,  185, 84)   # Signature Spotify Green
COL_BG       = api.rgb(14,  15,  20)   # Deep OLED Midnight
COL_CARD     = api.rgb(24,  26,  34)   # Card background
COL_CARD_BD  = api.rgb(44,  48,  64)   # Card border
COL_MUTED    = api.rgb(150, 155, 170)  # Subtext / timer
COL_BAR_BG   = api.rgb(38,  40,  52)   # Empty progress / vol bar
COL_CYAN     = api.rgb(80,  200, 255)  # Device pill cyan

DEMO_TRACKS = [
    {"title": "Starboy",         "artist": "The Weeknd, Daft Punk", "album": "Starboy", "duration": 230},
    {"title": "Midnight City",   "artist": "M83",                  "album": "Hurry Up", "duration": 244},
    {"title": "Resonance",       "artist": "HOME",                 "album": "Odyssey",  "duration": 212},
    {"title": "Get Lucky",       "artist": "Daft Punk, Pharrell",  "album": "RAM",      "duration": 248},
    {"title": "Blinding Lights", "artist": "The Weeknd",           "album": "After Hrs","duration": 200},
]


def _format_time(seconds):
    m = int(seconds) // 60
    s = int(seconds) % 60
    return "%02d:%02d" % (m, s)


def _marquee(text, max_chars, scroll_offset):
    if len(text) <= max_chars:
        return text
    overflow = len(text) - max_chars
    cycle = overflow + 8
    idx = int(scroll_offset) % cycle
    if idx < 3:
        return text[:max_chars]
    elif idx < 3 + overflow:
        shift = idx - 3
        return text[shift:shift + max_chars]
    else:
        return text[overflow:overflow + max_chars]


def _draw_icon_prev(d, x, y, color):
    """Draw a crisp 14x10 Previous Track glyph: bar on left + 2 left-pointing triangles."""
    # Vertical stop bar
    d.rect(x, y, 2, 10, color, fill=True)
    # Triangle 1 (pointing left)
    for col in range(5):
        h = (col + 1) * 2
        d.rect(x + 3 + col, y + (10 - h) // 2, 1, h, color, fill=True)
    # Triangle 2 (pointing left)
    for col in range(5):
        h = (col + 1) * 2
        d.rect(x + 8 + col, y + (10 - h) // 2, 1, h, color, fill=True)


def _draw_icon_next(d, x, y, color):
    """Draw a crisp 14x10 Next Track glyph: 2 right-pointing triangles + bar on right."""
    # Triangle 1 (pointing right)
    for col in range(5):
        h = 10 - col * 2
        d.rect(x + col, y + (10 - h) // 2, 1, h, color, fill=True)
    # Triangle 2 (pointing right)
    for col in range(5):
        h = 10 - col * 2
        d.rect(x + 5 + col, y + (10 - h) // 2, 1, h, color, fill=True)
    # Vertical stop bar
    d.rect(x + 11, y, 2, 10, color, fill=True)


def _draw_icon_play(d, x, y, color):
    """Draw a sharp 10x12 right-pointing Play triangle."""
    for col in range(5):
        h = 12 - col * 2
        d.rect(x + col * 2, y + col, 2, h, color, fill=True)


def _draw_icon_pause(d, x, y, color):
    """Draw two crisp 3x12 Pause bars."""
    d.rect(x, y, 3, 12, color, fill=True)
    d.rect(x + 6, y, 3, 12, color, fill=True)


def _draw_icon_speaker(d, x, y, color, vol=100):
    """Draw a 14x10 Speaker icon with dynamic volume soundwaves."""
    d.rect(x, y + 3, 3, 4, color, fill=True)
    d.rect(x + 3, y + 2, 1, 6, color, fill=True)
    d.rect(x + 4, y + 1, 1, 8, color, fill=True)
    d.rect(x + 5, y, 1, 10, color, fill=True)
    if vol > 0:
        d.rect(x + 8, y + 3, 1, 4, color, fill=True)
    if vol > 35:
        d.rect(x + 10, y + 2, 1, 6, color, fill=True)
    if vol > 70:
        d.rect(x + 12, y + 1, 1, 8, color, fill=True)


def _draw_icon_shuffle(d, x, y, color, active=False):
    """Draw 11x8 crossover arrows for Shuffle."""
    c = color if active else theme.MUTED2
    d.rect(x, y + 1, 3, 1, c, fill=True)
    d.rect(x + 3, y + 2, 2, 1, c, fill=True)
    d.rect(x + 5, y + 4, 2, 1, c, fill=True)
    d.rect(x + 7, y + 5, 3, 1, c, fill=True)
    d.rect(x, y + 5, 3, 1, c, fill=True)
    d.rect(x + 3, y + 4, 2, 1, c, fill=True)
    d.rect(x + 5, y + 2, 2, 1, c, fill=True)
    d.rect(x + 7, y + 1, 3, 1, c, fill=True)
    d.rect(x + 9, y, 2, 3, c, fill=True)
    d.rect(x + 9, y + 4, 2, 3, c, fill=True)


def _draw_icon_repeat(d, x, y, color, state="off"):
    """Draw 11x8 circular arrows for Repeat."""
    c = color if state != "off" else theme.MUTED2
    d.rect(x + 2, y, 6, 1, c, fill=True)
    d.rect(x + 1, y + 1, 1, 5, c, fill=True)
    d.rect(x + 2, y + 6, 6, 1, c, fill=True)
    d.rect(x + 8, y + 2, 1, 5, c, fill=True)
    d.rect(x + 7, y - 1, 2, 3, c, fill=True)
    d.rect(x, y + 5, 2, 3, c, fill=True)


class App(oreoOS.App):
    name         = "Spotify"
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

        self._mode = "DEMO"
        self._show_qr = False

        # Album Cover Art state
        self._cover_art = None
        self._last_image_url = ""
        self._cover_size = 72

        # Title marquee scroll state
        self._title_scroll_t = 0.0

        self._anim_t = 0.0
        self._last_tick = _ticks_ms()
        self._last_poll_ms = 0
        self._last_check_token_ms = 0
        self._vol_toast_t = 0.0
        self._dirty = True

        # QR Code state
        self._qr_url = "https://oreo.elixpo.com/spotify"
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
            self._build_qr()
            self._show_qr = True

    def on_exit(self):
        pass

    def _build_qr(self):
        try:
            pin, url = create_relay_session()
            self._session_pin = pin
            self._qr_url = url or "https://oreo.elixpo.com/spotify"
        except Exception:
            self._session_pin = None
            self._qr_url = "https://oreo.elixpo.com/spotify"

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
                new_title = state.get("title", self._title)
                if new_title != self._title:
                    self._title = new_title
                    self._title_scroll_t = 0.0

                self._artist = state.get("artist", self._artist)
                self._album = state.get("album", "")
                self._is_playing = state.get("is_playing", self._is_playing)
                self._duration = state.get("duration_s", self._duration)
                self._progress = state.get("progress_s", self._progress)
                self._volume = state.get("volume", self._volume)
                self._device_name = state.get("device_name", "")
                self._shuffle = state.get("shuffle", False)
                self._repeat = state.get("repeat", "off")

                # Fetch 72x72 Album Cover Art
                img_url = state.get("image_url", "")
                if img_url and img_url != self._last_image_url:
                    self._last_image_url = img_url
                    try:
                        self._cover_art = fetch_cover_art_rgb565(img_url, self._cover_size, self._cover_size)
                    except Exception:
                        self._cover_art = None
            else:
                self._title = "No Active Playback"
                self._artist = "Start music on phone/PC"
                self._album = "Spotify Connected"
                self._is_playing = False
                self._cover_art = None
        self._dirty = True

    def on_button_press(self, btn):
        if self._show_qr:
            if btn in (api.BTN_A, api.BTN_B):
                self._show_qr = False
                self._mode = "DEMO"
            elif btn == api.BTN_C:
                self._show_qr = False
                if self._spotify.reload_persisted():
                    self._mode = "SPOTIFY"
                    self._poll_spotify()
            self._dirty = True
            return

        if btn == api.BTN_A:
            # Play / Pause toggle
            if self._mode == "SPOTIFY":
                if self._is_playing:
                    self._spotify.pause()
                    self._is_playing = False
                else:
                    self._spotify.play()
                    self._is_playing = True
            else:
                self._is_playing = not self._is_playing

        elif btn == api.BTN_RIGHT:
            # Skip Next
            if self._mode == "SPOTIFY":
                self._spotify.next_track()
                time.sleep(0.15)
                self._poll_spotify()
            else:
                self._track_idx = (self._track_idx + 1) % len(DEMO_TRACKS)
                t = DEMO_TRACKS[self._track_idx]
                self._title, self._artist, self._album, self._duration = t["title"], t["artist"], t["album"], t["duration"]
                self._progress = 0.0
                self._cover_art = None
                self._title_scroll_t = 0.0

        elif btn == api.BTN_LEFT:
            # Skip Prev
            if self._mode == "SPOTIFY":
                self._spotify.prev_track()
                time.sleep(0.15)
                self._poll_spotify()
            else:
                self._track_idx = (self._track_idx - 1) % len(DEMO_TRACKS)
                t = DEMO_TRACKS[self._track_idx]
                self._title, self._artist, self._album, self._duration = t["title"], t["artist"], t["album"], t["duration"]
                self._progress = 0.0
                self._cover_art = None
                self._title_scroll_t = 0.0

        elif btn == api.BTN_UP:
            # Volume Up
            self._volume = min(100, self._volume + 5)
            self._vol_toast_t = 1.5
            if self._mode == "SPOTIFY":
                self._spotify.set_volume(self._volume)

        elif btn == api.BTN_DOWN:
            # Volume Down
            self._volume = max(0, self._volume - 5)
            self._vol_toast_t = 1.5
            if self._mode == "SPOTIFY":
                self._spotify.set_volume(self._volume)

        elif btn == api.BTN_B:
            # Switch Mode
            if self._mode == "SPOTIFY":
                self._mode = "DEMO"
                self._cover_art = None
            else:
                if self._spotify.is_configured():
                    self._mode = "SPOTIFY"
                    self._poll_spotify()
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

        # Check for newly saved token or poll Cloud PIN Relay while on setup screen
        if _ticks_diff(now, self._last_check_token_ms) > 1500:
            self._last_check_token_ms = now
            if self._show_qr and getattr(self, "_session_pin", None):
                try:
                    res = poll_relay_session(self._session_pin)
                    if res and res.get("status") == "authorized":
                        save_credentials(
                            token=res.get("access_token"),
                            refresh_token=res.get("refresh_token"),
                            client_id=res.get("client_id")
                        )
                        self._spotify.reload_persisted()
                        self._show_qr = False
                        self._mode = "SPOTIFY"
                        self._poll_spotify()
                        self._dirty = True
                except Exception:
                    pass
            elif self._show_qr or self._mode != "SPOTIFY":
                if self._spotify.reload_persisted():
                    self._mode = "SPOTIFY"
                    self._show_qr = False
                    self._poll_spotify()
                    self._dirty = True

        # Smooth local progress interpolation
        if self._is_playing and not self._show_qr:
            self._progress += dt
            if self._progress >= self._duration:
                if self._mode == "DEMO":
                    self._track_idx = (self._track_idx + 1) % len(DEMO_TRACKS)
                    t = DEMO_TRACKS[self._track_idx]
                    self._title, self._artist, self._album, self._duration = t["title"], t["artist"], t["album"], t["duration"]
                self._progress = 0.0

        # Periodic Spotify sync
        if self._mode == "SPOTIFY" and self._spotify.is_configured():
            if _ticks_diff(now, self._last_poll_ms) > 2500:
                self._last_poll_ms = now
                self._poll_spotify()

        # Update smooth marquee ticker scroll
        self._title_scroll_t += dt * 2.5

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

            if self._qr_matrix:
                n = len(self._qr_matrix)
                scale = max(2, min(3, (card_h - 60) // n))
                qr_px = n * scale
                qr_x = card_x + (card_w - qr_px) // 2
                qr_y = card_y + 6

                pad = 4
                d.rect(qr_x - pad, qr_y - pad, qr_px + pad * 2, qr_px + pad * 2, api.WHITE, fill=True)

                for r in range(n):
                    row = self._qr_matrix[r]
                    for c in range(n):
                        if row[c]:
                            d.rect(qr_x + c * scale, qr_y + r * scale, scale, scale, api.BLACK, fill=True)

                text_y = qr_y + qr_px + pad + 6
            else:
                text_y = card_y + 24

            if getattr(self, "_session_pin", None):
                pin_str = "PIN: " + self._session_pin
                d.text(pin_str, card_x + (card_w - len(pin_str) * 8) // 2, text_y, COL_SPOTIFY)
                caption = "Scan QR or visit:"
                d.text(caption, card_x + (card_w - len(caption) * 8) // 2, text_y + 14, api.WHITE)
                url_short = "oreo.elixpo.com/spotify"
                d.text(url_short, card_x + (card_w - len(url_short) * 8) // 2, text_y + 26, COL_CYAN)
            else:
                caption = "Scan with phone camera"
                d.text(caption, card_x + (card_w - len(caption) * 8) // 2, text_y, COL_SPOTIFY)
                url_txt = self._qr_url
                if len(url_txt) > 28: url_txt = url_txt[:26] + ".."
                d.text(url_txt, card_x + (card_w - len(url_txt) * 8) // 2, text_y + 14, api.WHITE)

            widgets.draw_hint(d, "A=demo mode  C=close")
            self._dirty = False
            return

        # ── Header ────────────────────────────────────────────────────────
        header_title = "SPOTIFY CONNECT" if self._mode == "SPOTIFY" else "NOW PLAYING"
        widgets.draw_header(d, header_title)

        # ── Hero Album Cover Art + Track Metadata ────────────────────────
        csz = self._cover_size  # 72px
        cover_box_x = 8
        cover_box_y = widgets.HEADER_H + 5

        # Draw Cover Art Photo Frame (76x76 container)
        d.rect(cover_box_x - 2, cover_box_y - 2, csz + 4, csz + 4, COL_CARD_BD, fill=True)
        d.rect(cover_box_x - 2, cover_box_y - 2, csz + 4, csz + 4, COL_SPOTIFY if self._is_playing else COL_CARD_BD, fill=False)

        if self._cover_art:
            # Real High-Resolution Album Cover Art Photo
            d.blit(self._cover_art, cover_box_x, cover_box_y, csz, csz)
        else:
            # Styled Retro Vinyl Record Graphic Placeholder
            d.rect(cover_box_x, cover_box_y, csz, csz, api.rgb(20, 22, 28), fill=True)
            cx = cover_box_x + csz // 2
            cy = cover_box_y + csz // 2
            d.rect(cx - 28, cy - 28, 56, 56, api.rgb(36, 40, 52), fill=False)
            d.rect(cx - 18, cy - 18, 36, 36, api.rgb(48, 54, 70), fill=False)
            d.rect(cx - 11, cy - 11, 22, 22, COL_SPOTIFY, fill=True)
            d.rect(cx - 3, cy - 3, 6, 6, api.BLACK, fill=True)

        # Metadata Card (Right side of cover photo)
        meta_x = cover_box_x + csz + 6
        meta_w = SW - meta_x - 8
        meta_y = cover_box_y - 2
        meta_h = csz + 4

        d.rect(meta_x, meta_y, meta_w, meta_h, COL_CARD, fill=True)
        d.rect(meta_x, meta_y, meta_w, meta_h, COL_CARD_BD, fill=False)

        # Full available text capacity (26 characters per line)
        max_chars = (meta_w - 14) // 8

        # Title: Smooth natural marquee across full width
        display_title = _marquee(self._title, max_chars, self._title_scroll_t)
        d.text(display_title, meta_x + 7, meta_y + 7, api.WHITE)

        # Artist: Full marquee across full width
        display_artist = _marquee(self._artist, max_chars, self._title_scroll_t * 0.8)
        d.text(display_artist, meta_x + 7, meta_y + 23, COL_SPOTIFY)

        # Album
        album_str = self._album or "Single"
        if len(album_str) > max_chars:
            album_str = album_str[:max_chars - 2] + ".."
        d.text(album_str, meta_x + 7, meta_y + 39, COL_MUTED)

        # Device tag with subtle container pill
        dev_tag = self._device_name or ("Spotify Connect" if self._mode == "SPOTIFY" else "Badge Player")
        if len(dev_tag) > max_chars - 3:
            dev_tag = dev_tag[:max_chars - 5] + ".."
        pill_w = len(dev_tag) * 8 + 14
        d.rect(meta_x + 7, meta_y + 54, pill_w, 13, COL_CARD_BD, fill=True)
        d.rect(meta_x + 7, meta_y + 54, pill_w, 13, COL_SPOTIFY, fill=False)
        # Active streaming dot
        d.rect(meta_x + 11, meta_y + 58, 3, 3, COL_SPOTIFY, fill=True)
        d.text(dev_tag, meta_x + 18, meta_y + 57, COL_CYAN)

        # ── Playback Progress & Timeline Card ────────────────────────────
        prog_card_y = cover_box_y + csz + 8
        prog_card_h = 46
        d.rect(8, prog_card_y, SW - 16, prog_card_h, COL_CARD, fill=True)
        d.rect(8, prog_card_y, SW - 16, prog_card_h, COL_CARD_BD, fill=False)

        # Time labels + Status
        cur_str = _format_time(self._progress)
        tot_str = _format_time(self._duration)
        d.text(cur_str, 16, prog_card_y + 8, api.WHITE)
        d.text(tot_str, SW - len(tot_str) * 8 - 16, prog_card_y + 8, COL_MUTED)

        play_label = "PLAYING" if self._is_playing else "PAUSED"
        d.text(play_label, (SW - len(play_label) * 8) // 2, prog_card_y + 8, COL_SPOTIFY if self._is_playing else theme.GOLD)

        # Progress bar
        bar_x = 16
        bar_y = prog_card_y + 26
        bar_w = SW - 32
        ratio = min(1.0, max(0.0, self._progress / max(1.0, self._duration)))
        fill_w = int(bar_w * ratio)

        d.rect(bar_x, bar_y, bar_w, 6, COL_BAR_BG, fill=True)
        if fill_w > 0:
            d.rect(bar_x, bar_y, fill_w, 6, COL_SPOTIFY, fill=True)
        # Scrub knob
        knob_x = min(bar_x + bar_w - 3, max(bar_x, bar_x + fill_w))
        d.rect(knob_x - 2, bar_y - 2, 5, 10, api.WHITE, fill=True)

        # ── Transport Controls & Volume Footer ────────────────────────────
        ctrl_y = prog_card_y + prog_card_h + 6
        ctrl_h = 36
        d.rect(8, ctrl_y, SW - 16, ctrl_h, COL_CARD, fill=True)
        d.rect(8, ctrl_y, SW - 16, ctrl_h, COL_CARD_BD, fill=False)

        # 1. Shuffle & Prev Track Glyphs
        _draw_icon_shuffle(d, 22, ctrl_y + 14, COL_SPOTIFY, self._shuffle)
        _draw_icon_prev(d, 46, ctrl_y + 13, api.WHITE)

        # 2. Hero Play/Pause Capsule Button
        btn_x = 74
        btn_y = ctrl_y + 6
        btn_w = 32
        btn_h = 24
        d.rect(btn_x, btn_y, btn_w, btn_h, COL_SPOTIFY, fill=True)
        d.rect(btn_x, btn_y, btn_w, btn_h, theme.PRIMARY, fill=False)
        icon_fg = api.rgb(20, 22, 28)
        if self._is_playing:
            _draw_icon_pause(d, btn_x + 11, btn_y + 6, icon_fg)
        else:
            _draw_icon_play(d, btn_x + 12, btn_y + 6, icon_fg)

        # 3. Next Track & Repeat Glyphs
        _draw_icon_next(d, 120, ctrl_y + 13, api.WHITE)
        _draw_icon_repeat(d, 146, ctrl_y + 14, COL_SPOTIFY, self._repeat)

        # 4. Volume Section with Speaker Icon & Dynamic Progress Slider
        _draw_icon_speaker(d, 178, ctrl_y + 13, COL_SPOTIFY, self._volume)
        vx = 200
        vy = ctrl_y + 16
        vw = 54
        vh = 5
        d.rect(vx, vy, vw, vh, COL_BAR_BG, fill=True)
        v_fill = int((self._volume / 100) * vw)
        if v_fill > 0:
            d.rect(vx, vy, v_fill, vh, COL_SPOTIFY, fill=True)
        # Volume slider thumb
        d.rect(vx + min(vw - 2, max(0, v_fill - 1)), vy - 2, 3, 9, api.WHITE, fill=True)
        # Percentage readout
        d.text("%d%%" % self._volume, 262, ctrl_y + 14, api.WHITE)

        # ── Volume Toast Overlay ──────────────────────────────────────────
        if self._vol_toast_t > 0:
            toast_w, toast_h = 130, 28
            tx = (SW - toast_w) // 2
            ty = prog_card_y + 6
            d.rect(tx, ty, toast_w, toast_h, api.BLACK, fill=True)
            d.rect(tx, ty, toast_w, toast_h, COL_SPOTIFY, fill=False)
            msg = "VOL: %d%%" % self._volume
            d.text(msg, tx + (toast_w - len(msg) * 8) // 2, ty + 10, COL_SPOTIFY)

        # ── Bottom Hints ──────────────────────────────────────────────────
        widgets.draw_hint(d, "A:Play  < >:Skip  ^ v:Vol  C:QR")
        self._dirty = False
