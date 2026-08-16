"""Spotify — Real-time Spotify Connect & Media Player for Oreo OS.

Features:
  • Real-time Spotify Playback Sync (Track, Artist, Album, Duration, Progress, Volume).
  • Minimal, uncluttered transport controls (Prev, Play/Pause, Next, Speaker & Volume slider).
  • Buffered & debounced volume engine (350ms settle timer for rapid/long presses).
  • Interactive Library & Playlist Drawer (B button) with instant track switching.
  • Manifest-driven app branding ("Spotify" from manifest.json).
  • High-Resolution Album Cover Art photo rendering with memory caching.
  • Dynamic streaming device badge and marquee title scrolling.
  • Offline Demo fallback playlist when not linked to Spotify.

Controls:
  PLAYER VIEW:
    A        Play / Pause toggle
    RIGHT    Next track (Skip)
    LEFT     Previous track
    UP       Volume Up (+5%, buffered)
    DOWN     Volume Down (-5%, buffered)
    B        Toggle Library Drawer
    C        Open Setup QR Screen
    HOME     Exit to launcher drawer

  LIBRARY VIEW:
    UP/DOWN  Scroll through tracks / playlists
    A        Play selected track & return to player
    B        Return to player view
    C        Open Setup QR Screen
"""

import time
import oreoOS
from oreoOS import api, theme, widgets

try:
    from .spotify import SpotifyClient, fetch_cover_art_rgb565, create_relay_session, poll_relay_session, save_credentials, clear_credentials
    from .qr import QRCode
except Exception:
    try:
        from apps_market.Music.src.spotify import SpotifyClient, fetch_cover_art_rgb565, create_relay_session, poll_relay_session, save_credentials, clear_credentials
        from apps_market.Music.src.qr import QRCode
    except Exception:
        from apps.Music.src.spotify import SpotifyClient, fetch_cover_art_rgb565, create_relay_session, poll_relay_session, save_credentials, clear_credentials
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

DEFAULT_LIBRARY_TRACKS = [
    {"title": "G-Class",         "artist": "YUNG SAMMY, Urban Poet", "album": "G-Class",        "duration": 166, "category": "Rap",       "uri": "spotify:track:2yBum3qnYBlzeGjpWQLenu"},
    {"title": "Chalo Chalein",   "artist": "Ritviz, Seedhe Maut",    "album": "Chalo Chalein",  "duration": 184, "category": "Hip-Hop",   "uri": "spotify:track:6m0uNvHh5zG9FJmbxVxD1N"},
    {"title": "Hola Amigo",      "artist": "KR$NA, Seedhe Maut",     "album": "FAR FROM OVER",   "duration": 226, "category": "Hip-Hop",   "uri": "spotify:track:5W17yyFN1l8JL5MNUCvrYS"},
    {"title": "Nanchaku",        "artist": "Seedhe Maut, MC Stan",   "album": "Nayaab",          "duration": 193, "category": "Hip-Hop",   "uri": "spotify:track:3d4wYjp1fwSQmfOOEd5P0w"},
    {"title": "Starboy",         "artist": "The Weeknd, Daft Punk",  "album": "Starboy",        "duration": 230, "category": "Synthwave", "uri": "spotify:track:7MXVkk9YMctZqd1Srtv4MB"},
    {"title": "Midnight City",   "artist": "M83",                    "album": "Hurry Up",        "duration": 243, "category": "Synthwave", "uri": "spotify:track:6GyFP1nfCDB8lbD2bG0Hq9"},
    {"title": "Resonance",       "artist": "HOME",                   "album": "Odyssey",         "duration": 212, "category": "Lo-Fi",     "uri": "spotify:track:2NHkwSwm6C6eAX3z6xm7Uy"},
    {"title": "Get Lucky",       "artist": "Daft Punk, Pharrell",    "album": "RAM",             "duration": 369, "category": "Funk",      "uri": "spotify:track:69kOkLUCkxIZYexIgSG8rq"},
    {"title": "Blinding Lights", "artist": "The Weeknd",             "album": "After Hours",     "duration": 200, "category": "Synthwave", "uri": "spotify:track:0VjIjW4GlUZAMYd2vXMi3b"},
    {"title": "Do I Wanna Know?","artist": "Arctic Monkeys",         "album": "AM",              "duration": 272, "category": "Indie",     "uri": "spotify:track:5FVd6KXrgO9B3JPmC8OPst"},
    {"title": "Sweater Weather", "artist": "The Neighbourhood",      "album": "I Love You.",     "duration": 301, "category": "Indie",     "uri": "spotify:track:6jhzQyn6cwPHc85PE4qBp0"},
]


def _get_manifest_name():
    for p in ("apps/Music/manifest.json", "apps_market/Music/manifest.json"):
        try:
            import json
            with open(p) as f:
                d = json.load(f)
                if "name" in d:
                    return d["name"]
        except Exception:
            pass
    return "Spotify"


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
    d.rect(x, y, 2, 10, color, fill=True)
    for col in range(5):
        h = (col + 1) * 2
        d.rect(x + 3 + col, y + (10 - h) // 2, 1, h, color, fill=True)
    for col in range(5):
        h = (col + 1) * 2
        d.rect(x + 8 + col, y + (10 - h) // 2, 1, h, color, fill=True)


def _draw_icon_next(d, x, y, color):
    for col in range(5):
        h = 10 - col * 2
        d.rect(x + col, y + (10 - h) // 2, 1, h, color, fill=True)
    for col in range(5):
        h = 10 - col * 2
        d.rect(x + 5 + col, y + (10 - h) // 2, 1, h, color, fill=True)
    d.rect(x + 11, y, 2, 10, color, fill=True)


def _draw_icon_play(d, x, y, color):
    for col in range(5):
        h = 12 - col * 2
        d.rect(x + col * 2, y + col, 2, h, color, fill=True)


def _draw_icon_pause(d, x, y, color):
    d.rect(x, y, 3, 12, color, fill=True)
    d.rect(x + 6, y, 3, 12, color, fill=True)


def _draw_icon_speaker(d, x, y, color, vol=100):
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


class App(oreoOS.App):
    name = _get_manifest_name()
    author = "sea-deep"
    SHOW_LOADING = True
    CONSUMES_C = True

    def on_enter(self, os):
        self._os = os
        self._spotify = SpotifyClient()
        self._mode = "SPOTIFY" if self._spotify.is_configured() else "DEMO"
        self._view_mode = "PLAYER"

        # Library Navigation State
        self._lib_idx = 0
        self._lib_scroll = 0
        self._library_tracks = list(DEFAULT_LIBRARY_TRACKS)

        # Player State
        t0 = self._library_tracks[0]
        self._title = t0["title"]
        self._artist = t0["artist"]
        self._album = t0["album"]
        self._duration = t0["duration"]
        self._progress = 0.0
        self._volume = 80
        self._is_playing = False
        self._device_name = ""

        # Cover Art State
        self._cover_art = None
        self._last_image_url = ""
        self._cover_size = 72

        # Polling & Timers
        self._last_poll = _ticks_ms()
        self._poll_interval = 2500
        self._poll_skip_until = 0
        self._title_scroll_t = 0.0
        self._dirty = True

        # QR Link Session State
        self._show_qr = False
        self._qr_session_id = None
        self._qr_url = None
        self._qr_matrix = None
        self._qr_poll_t = _ticks_ms()

        # Volume Buffer & Debounce State
        self._vol_buffered = False
        self._vol_settle_t = 0
        self._last_synced_vol = self._volume
        self._vol_syncing = False

        # Toast Message State
        self._toast_msg = ""
        self._toast_until = 0

        if self._mode == "SPOTIFY":
            self._poll_spotify()
            self._load_spotify_user_library()

    def _load_spotify_user_library(self):
        """Asynchronously fetch user's Spotify tracks to merge into the library."""
        def _worker():
            try:
                user_tracks = self._spotify.get_user_tracks(10)
                if user_tracks:
                    # Merge with default tracks
                    merged = user_tracks + [t for t in DEFAULT_LIBRARY_TRACKS if not any(u["title"].lower() == t["title"].lower() for u in user_tracks)]
                    self._library_tracks = merged
                    self._dirty = True
            except Exception:
                pass
        try:
            import threading
            threading.Thread(target=_worker, daemon=True).start()
        except Exception:
            pass

    def _set_volume_async(self, vol):
        if self._mode != "SPOTIFY":
            return
        def _worker():
            try:
                self._spotify.set_volume(vol)
            except Exception:
                pass
        try:
            import threading
            threading.Thread(target=_worker, daemon=True).start()
        except Exception:
            self._spotify.set_volume(vol)

    def _start_qr_session(self):
        self._qr_session_id, self._qr_url = create_relay_session()
        if self._qr_url:
            self._qr_matrix = QRCode.encode(self._qr_url)
            self._show_qr = True
        self._dirty = True

    def _poll_spotify(self):
        if self._mode != "SPOTIFY":
            return
        state = self._spotify.get_playback()
        if state:
            title = state.get("title", "")
            if title and title != "No Active Playback":
                self._title = title
                self._artist = state.get("artist", self._artist)
                self._album = state.get("album", "")
                self._is_playing = state.get("is_playing", self._is_playing)
                self._duration = state.get("duration_s", self._duration)
                self._progress = state.get("progress_s", self._progress)
                # Only update volume from server if not actively buffering local user presses
                if not self._vol_buffered:
                    self._volume = state.get("volume", self._volume)
                    self._last_synced_vol = self._volume
                self._device_name = state.get("device_name", "")

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
            elif btn == api.BTN_C:
                self._show_qr = False
                if self._spotify.reload_persisted():
                    self._mode = "SPOTIFY"
                    self._poll_spotify()
            self._dirty = True
            return

        # ── Toggle QR / Disconnect Screen (BTN_C) ─────────────────────────
        if btn == api.BTN_C:
            if self._show_qr:
                self._show_qr = False
            elif self._mode == "SPOTIFY":
                # Disconnect & wipe Spotify credentials
                self._spotify.disconnect()
                self._mode = "DEMO"
                self._library_tracks = list(DEFAULT_LIBRARY_TRACKS)
                self._lib_idx = 0
                self._lib_scroll = 0
                t0 = self._library_tracks[0]
                self._title = t0["title"]
                self._artist = t0["artist"]
                self._album = t0["album"]
                self._duration = t0["duration"]
                self._progress = 0.0
                self._is_playing = False
                self._cover_art = None
                self._device_name = "Offline"
                self._toast_msg = "SPOTIFY UNLINKED"
                self._toast_until = _ticks_ms() + 2500
            else:
                self._start_qr_session()
            self._dirty = True
            return

        # ── Library View Controls ─────────────────────────────────────────
        if self._view_mode == "LIBRARY":
            if btn == api.BTN_B:
                self._view_mode = "PLAYER"
                self._dirty = True
                return
            elif btn == api.BTN_UP:
                if self._lib_idx > 0:
                    self._lib_idx -= 1
                    if self._lib_idx < self._lib_scroll:
                        self._lib_scroll = self._lib_idx
                    self._dirty = True
                return
            elif btn == api.BTN_DOWN:
                if self._lib_idx < len(self._library_tracks) - 1:
                    self._lib_idx += 1
                    if self._lib_idx >= self._lib_scroll + 5:
                        self._lib_scroll = self._lib_idx - 4
                    self._dirty = True
                return
            elif btn == api.BTN_A:
                # Select & Play
                t = self._library_tracks[self._lib_idx]
                self._title = t["title"]
                self._artist = t["artist"]
                self._album = t["album"]
                self._duration = t["duration"]
                self._progress = 0.0
                self._is_playing = True
                self._cover_art = None
                self._title_scroll_t = 0.0
                self._view_mode = "PLAYER"
                self._poll_skip_until = _ticks_ms() + 3500

                if self._mode == "SPOTIFY":
                    track_target = t.get("uri") or (t["title"] + " " + t["artist"])
                    def _play_worker(target):
                        try:
                            self._spotify.play_track(target)
                        except Exception:
                            pass
                    try:
                        import threading
                        threading.Thread(target=_play_worker, args=(track_target,), daemon=True).start()
                    except Exception:
                        self._spotify.play_track(track_target)
                self._dirty = True
                return
            return

        # ── Player View Controls ──────────────────────────────────────────
        if btn == api.BTN_B:
            # Open Library Drawer
            self._view_mode = "LIBRARY"
            self._load_spotify_user_library()
            self._dirty = True

        elif btn == api.BTN_A:
            # Play / Pause toggle
            if self._mode == "SPOTIFY":
                if self._is_playing:
                    self._is_playing = False
                    try:
                        import threading
                        threading.Thread(target=self._spotify.pause, daemon=True).start()
                    except Exception:
                        pass
                else:
                    self._is_playing = True
                    try:
                        import threading
                        threading.Thread(target=self._spotify.play, daemon=True).start()
                    except Exception:
                        pass
            else:
                self._is_playing = not self._is_playing
            self._dirty = True

        elif btn == api.BTN_RIGHT:
            # Skip Next
            if self._mode == "SPOTIFY":
                try:
                    import threading
                    threading.Thread(target=self._spotify.next_track, daemon=True).start()
                except Exception:
                    pass
            else:
                self._lib_idx = (self._lib_idx + 1) % len(self._library_tracks)
                t = self._library_tracks[self._lib_idx]
                self._title, self._artist, self._album, self._duration = t["title"], t["artist"], t["album"], t["duration"]
                self._progress = 0.0
                self._cover_art = None
                self._title_scroll_t = 0.0
            self._dirty = True

        elif btn == api.BTN_LEFT:
            # Skip Prev
            if self._mode == "SPOTIFY":
                try:
                    import threading
                    threading.Thread(target=self._spotify.prev_track, daemon=True).start()
                except Exception:
                    pass
            else:
                self._lib_idx = (self._lib_idx - 1) % len(self._library_tracks)
                t = self._library_tracks[self._lib_idx]
                self._title, self._artist, self._album, self._duration = t["title"], t["artist"], t["album"], t["duration"]
                self._progress = 0.0
                self._cover_art = None
                self._title_scroll_t = 0.0
            self._dirty = True

        elif btn == api.BTN_UP:
            # Volume Up (Buffered & debounced for fast/long presses)
            self._volume = min(100, self._volume + 5)
            self._vol_buffered = True
            self._vol_settle_t = _ticks_ms() + 350
            self._dirty = True

        elif btn == api.BTN_DOWN:
            # Volume Down (Buffered & debounced for fast/long presses)
            self._volume = max(0, self._volume - 5)
            self._vol_buffered = True
            self._vol_settle_t = _ticks_ms() + 350
            self._dirty = True

    def update(self, dt):
        now = _ticks_ms()

        # Volume Settle Buffer Flush (Debounce Dispatcher)
        if self._vol_buffered and _ticks_diff(now, self._vol_settle_t) >= 0:
            self._vol_buffered = False
            if self._volume != self._last_synced_vol:
                self._last_synced_vol = self._volume
                self._set_volume_async(self._volume)

        # Update QR Pairing Session
        if self._show_qr and self._qr_session_id:
            if _ticks_diff(now, self._qr_poll_t) > 2000:
                self._qr_poll_t = now
                creds = poll_relay_session(self._qr_session_id)
                if creds:
                    save_credentials(creds)
                    self._spotify.reload_persisted()
                    self._show_qr = False
                    self._mode = "SPOTIFY"
                    self._poll_spotify()
                    self._dirty = True

        # Periodic Spotify Playback Polling (respecting selection grace period)
        if not self._show_qr and self._mode == "SPOTIFY":
            if _ticks_diff(now, self._poll_skip_until) >= 0:
                if _ticks_diff(now, self._last_poll) > self._poll_interval:
                    self._last_poll = now
                    self._poll_spotify()

        # Smooth Playback Progress Simulation
        if self._is_playing:
            self._progress += dt
            if self._duration > 0 and self._progress >= self._duration:
                if self._mode == "SPOTIFY":
                    self._poll_spotify()
                else:
                    self._progress = 0.0
            self._dirty = True

        # Smooth Text Marquee Ticker
        self._title_scroll_t += dt * 3.5
        self._dirty = True

    def draw(self, d):
        if not self._dirty:
            return

        d.clear(COL_BG)

        # ── QR Code Pairing Modal ─────────────────────────────────────────
        if self._show_qr:
            self._draw_qr_screen(d)
            self._dirty = False
            return

        # ── Library Drawer View ───────────────────────────────────────────
        if self._view_mode == "LIBRARY":
            self._draw_library(d)
            self._dirty = False
            return

        # ── Now Playing View ──────────────────────────────────────────────
        self._draw_player(d)
        self._dirty = False

    def _draw_player(self, d):
        # 1. Header with Manifest App Name ("SPOTIFY" / "SPOTIFY CONNECT")
        app_title = "SPOTIFY CONNECT" if self._mode == "SPOTIFY" else (self.name.upper() if self.name else "SPOTIFY")
        widgets.draw_header(d, app_title)

        # 2. Hero Album Cover Art + Track Metadata
        csz = self._cover_size
        cover_box_x = 8
        cover_box_y = widgets.HEADER_H + 5

        # Cover Art Photo Frame (76x76 container)
        d.rect(cover_box_x - 2, cover_box_y - 2, csz + 4, csz + 4, COL_CARD_BD, fill=True)
        d.rect(cover_box_x - 2, cover_box_y - 2, csz + 4, csz + 4, COL_SPOTIFY if self._is_playing else COL_CARD_BD, fill=False)

        if self._cover_art:
            d.blit(self._cover_art, cover_box_x, cover_box_y, csz, csz)
        else:
            # Retro Vinyl Graphic Placeholder
            d.rect(cover_box_x, cover_box_y, csz, csz, api.rgb(20, 22, 28), fill=True)
            cx = cover_box_x + csz // 2
            cy = cover_box_y + csz // 2
            d.rect(cx - 28, cy - 28, 56, 56, api.rgb(36, 40, 52), fill=False)
            d.rect(cx - 18, cy - 18, 36, 36, api.rgb(48, 54, 70), fill=False)
            d.rect(cx - 11, cy - 11, 22, 22, COL_SPOTIFY, fill=True)
            d.rect(cx - 3, cy - 3, 6, 6, api.BLACK, fill=True)

        # Metadata Card (Full space utilization: 26 chars)
        meta_x = cover_box_x + csz + 6
        meta_w = SW - meta_x - 8
        meta_y = cover_box_y - 2
        meta_h = csz + 4

        d.rect(meta_x, meta_y, meta_w, meta_h, COL_CARD, fill=True)
        d.rect(meta_x, meta_y, meta_w, meta_h, COL_CARD_BD, fill=False)

        max_chars = (meta_w - 14) // 8

        # Line 1: Title (smooth marquee)
        display_title = _marquee(self._title, max_chars, self._title_scroll_t)
        d.text(display_title, meta_x + 7, meta_y + 7, api.WHITE)

        # Line 2: Artist (smooth marquee)
        display_artist = _marquee(self._artist, max_chars, self._title_scroll_t * 0.8)
        d.text(display_artist, meta_x + 7, meta_y + 23, COL_SPOTIFY)

        # Line 3: Album
        album_str = self._album or "Single"
        if len(album_str) > max_chars:
            album_str = album_str[:max_chars - 2] + ".."
        d.text(album_str, meta_x + 7, meta_y + 39, COL_MUTED)

        # Line 4: Device Streaming Pill Badge
        dev_tag = self._device_name or ("Spotify Connect" if self._mode == "SPOTIFY" else "Local Badge")
        if len(dev_tag) > max_chars - 3:
            dev_tag = dev_tag[:max_chars - 5] + ".."
        pill_w = len(dev_tag) * 8 + 14
        d.rect(meta_x + 7, meta_y + 54, pill_w, 13, COL_CARD_BD, fill=True)
        d.rect(meta_x + 7, meta_y + 54, pill_w, 13, COL_SPOTIFY, fill=False)
        d.rect(meta_x + 11, meta_y + 58, 3, 3, COL_SPOTIFY, fill=True)
        d.text(dev_tag, meta_x + 18, meta_y + 57, COL_CYAN)

        # 3. Playback Timeline Card
        prog_card_y = cover_box_y + csz + 8
        prog_card_h = 46
        d.rect(8, prog_card_y, SW - 16, prog_card_h, COL_CARD, fill=True)
        d.rect(8, prog_card_y, SW - 16, prog_card_h, COL_CARD_BD, fill=False)

        # Time Labels
        cur_time_str = _format_time(self._progress)
        tot_time_str = _format_time(self._duration)
        d.text(cur_time_str, 16, prog_card_y + 8, api.WHITE)
        d.text(tot_time_str, SW - 16 - len(tot_time_str) * 8, prog_card_y + 8, api.WHITE)

        # State Pill Badge
        status_label = "PLAYING" if self._is_playing else "PAUSED"
        stat_w = len(status_label) * 8
        stat_x = (SW - stat_w) // 2
        d.text(status_label, stat_x, prog_card_y + 8, COL_SPOTIFY if self._is_playing else theme.GOLD)

        # Timeline Scrubber Bar
        bar_x = 16
        bar_y = prog_card_y + 26
        bar_w = SW - 32
        ratio = min(1.0, max(0.0, self._progress / max(1.0, self._duration)))
        fill_w = int(bar_w * ratio)

        d.rect(bar_x, bar_y, bar_w, 6, COL_BAR_BG, fill=True)
        if fill_w > 0:
            d.rect(bar_x, bar_y, fill_w, 6, COL_SPOTIFY, fill=True)
        knob_x = min(bar_x + bar_w - 3, max(bar_x, bar_x + fill_w))
        d.rect(knob_x - 2, bar_y - 2, 5, 10, api.WHITE, fill=True)

        # 4. Minimal Transport Controls & Volume Footer
        ctrl_y = prog_card_y + prog_card_h + 6
        ctrl_h = 36
        d.rect(8, ctrl_y, SW - 16, ctrl_h, COL_CARD, fill=True)
        d.rect(8, ctrl_y, SW - 16, ctrl_h, COL_CARD_BD, fill=False)

        # Transport: Prev Track
        _draw_icon_prev(d, 28, ctrl_y + 13, api.WHITE)

        # Transport: Hero Play/Pause Capsule Button
        btn_x = 58
        btn_y = ctrl_y + 6
        btn_w = 34
        btn_h = 24
        d.rect(btn_x, btn_y, btn_w, btn_h, COL_SPOTIFY, fill=True)
        d.rect(btn_x, btn_y, btn_w, btn_h, theme.PRIMARY, fill=False)
        icon_fg = api.rgb(20, 22, 28)
        if self._is_playing:
            _draw_icon_pause(d, btn_x + 12, btn_y + 6, icon_fg)
        else:
            _draw_icon_play(d, btn_x + 13, btn_y + 6, icon_fg)

        # Transport: Next Track
        _draw_icon_next(d, 108, ctrl_y + 13, api.WHITE)

        # Volume Section: Speaker Icon + Progress Slider Bar + % Readout
        _draw_icon_speaker(d, 160, ctrl_y + 13, COL_SPOTIFY, self._volume)
        vx = 182
        vy = ctrl_y + 16
        vw = 72
        vh = 5
        d.rect(vx, vy, vw, vh, COL_BAR_BG, fill=True)
        v_fill = int((self._volume / 100) * vw)
        if v_fill > 0:
            d.rect(vx, vy, v_fill, vh, COL_SPOTIFY, fill=True)
        d.rect(vx + min(vw - 2, max(0, v_fill - 1)), vy - 2, 3, 9, api.WHITE, fill=True)
        d.text("%d%%" % self._volume, 264, ctrl_y + 14, api.WHITE)

        # 5. Toast Notification Overlay if active
        now = _ticks_ms()
        if self._toast_until > 0 and _ticks_diff(now, self._toast_until) < 0:
            tw = len(self._toast_msg) * 8 + 24
            tx = (SW - tw) // 2
            ty = widgets.HEADER_H + 6
            d.rect(tx, ty, tw, 22, api.rgb(20, 22, 28), fill=True)
            d.rect(tx, ty, tw, 22, theme.GOLD, fill=False)
            d.text(self._toast_msg, tx + 12, ty + 7, theme.GOLD)

        # 6. Bottom Hint Bar
        c_act = "C:Unlink" if self._mode == "SPOTIFY" else "C:Link"
        widgets.draw_hint(d, "A:Play  <>:Skip  ^v:Vol  B:Lib  " + c_act)

    def _draw_library(self, d):
        # Header
        widgets.draw_header(d, "LIBRARY")

        # Container Card
        card_x = 8
        card_y = widgets.HEADER_H + 4
        card_w = SW - 16
        card_h = SH - widgets.HEADER_H - widgets.HINT_H - 8
        d.rect(card_x, card_y, card_w, card_h, COL_CARD, fill=True)
        d.rect(card_x, card_y, card_w, card_h, COL_CARD_BD, fill=False)

        # Track List (5 items per page)
        row_h = 34
        visible_count = 5
        tracks = self._library_tracks
        for i in range(visible_count):
            item_idx = self._lib_scroll + i
            if item_idx >= len(tracks):
                break
            t = tracks[item_idx]
            ry = card_y + 4 + i * (row_h + 2)
            rx = card_x + 4
            rw = card_w - 14

            is_selected = (item_idx == self._lib_idx)
            is_active_track = (t["title"].lower() == self._title.lower())

            # Row Background
            if is_selected:
                d.rect(rx, ry, rw, row_h, api.rgb(38, 44, 60), fill=True)
                d.rect(rx, ry, 3, row_h, COL_SPOTIFY, fill=True)
            else:
                d.rect(rx, ry, rw, row_h, api.rgb(20, 22, 28), fill=True)

            # Track Number / Equalizer Icon
            if is_active_track and self._is_playing:
                d.rect(rx + 8, ry + 12, 2, 8, COL_SPOTIFY, fill=True)
                d.rect(rx + 12, ry + 8, 2, 12, COL_SPOTIFY, fill=True)
                d.rect(rx + 16, ry + 14, 2, 6, COL_SPOTIFY, fill=True)
            else:
                num_str = "%02d" % (item_idx + 1)
                d.text(num_str, rx + 8, ry + 12, COL_SPOTIFY if is_selected else COL_MUTED)

            # Track Title
            t_color = api.WHITE if is_selected else api.rgb(210, 215, 225)
            d.text(t["title"][:18], rx + 28, ry + 6, t_color)

            # Artist + Category
            cat = t.get("category", "Track")
            sub_str = "%s / %s" % (t["artist"][:14], cat)
            d.text(sub_str, rx + 28, ry + 20, COL_SPOTIFY if is_selected else COL_MUTED)

            # Duration
            dur_str = _format_time(t["duration"])
            d.text(dur_str, rx + rw - len(dur_str) * 8 - 4, ry + 12, COL_MUTED)

        # Right Scrollbar
        sb_x = card_x + card_w - 6
        sb_y = card_y + 6
        sb_h = card_h - 12
        d.rect(sb_x, sb_y, 2, sb_h, COL_BAR_BG, fill=True)
        total_items = len(tracks)
        thumb_h = max(14, int((visible_count / total_items) * sb_h))
        thumb_y = sb_y + int((self._lib_scroll / max(1, total_items - visible_count)) * (sb_h - thumb_h))
        d.rect(sb_x - 1, thumb_y, 4, thumb_h, COL_SPOTIFY, fill=True)

        # Hint Bar
        c_act = "C:Unlink" if self._mode == "SPOTIFY" else "C:Link"
        widgets.draw_hint(d, "A:Play  ^v:Select  B:Player  " + c_act)

    def _draw_qr_screen(self, d):
        widgets.draw_header(d, "LINK SPOTIFY")
        d.rect(10, widgets.HEADER_H + 4, SW - 20, SH - widgets.HEADER_H - widgets.HINT_H - 8, COL_CARD, fill=True)
        d.rect(10, widgets.HEADER_H + 4, SW - 20, SH - widgets.HEADER_H - widgets.HINT_H - 8, COL_CARD_BD, fill=False)

        if self._qr_matrix:
            mat = self._qr_matrix
            rows = len(mat)
            cols = len(mat[0])
            mod_sz = 3
            qr_w = cols * mod_sz
            qr_h = rows * mod_sz
            qx = 22
            qy = widgets.HEADER_H + 18

            # White quiet-zone backing
            d.rect(qx - 4, qy - 4, qr_w + 8, qr_h + 8, api.WHITE, fill=True)
            for r in range(rows):
                for c in range(cols):
                    if mat[r][c]:
                        d.rect(qx + c * mod_sz, qy + r * mod_sz, mod_sz, mod_sz, api.BLACK, fill=True)

            # Instructions
            tx = qx + qr_w + 14
            d.text("SCAN TO LINK", tx, qy, COL_SPOTIFY)
            d.text("1. Scan QR code", tx, qy + 18, api.WHITE)
            d.text("2. Authorize app", tx, qy + 32, api.WHITE)
            d.text("3. Syncs instantly", tx, qy + 46, COL_CYAN)
            d.text("Waiting login...", tx, qy + 66, theme.GOLD)
        else:
            d.text("Generating Link...", 80, 110, COL_SPOTIFY)

        widgets.draw_hint(d, "A/B:Cancel  C:Refresh")
