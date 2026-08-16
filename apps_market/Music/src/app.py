"""Spotify — Real-time Spotify Connect & Hierarchical Media Player for Oreo OS.

Features:
  • Hierarchical Tree Library (Liked Songs, Top Tracks, Recently Played, User Playlists).
  • Deep Navigation State Preservation (Sub-folder index and scroll memory).
  • Memory-Safe Lazy Fetching & Bounded Local Caching (ESP32-S3 PSRAM safe).
  • Fully Asynchronous Zero-Lag Polling (Runs in decoupled background workers).
  • 60fps / 30fps Instant Optimistic UI (Volume, Play/Pause, Skip respond with 0ms latency).
  • Interaction Lockout: Server polling never overwrites user volume adjustments.
  • Smooth Sub-second Scrubber Interpolation & Text Marquee.
  • Manifest-driven app branding ("Spotify").
  • High-Resolution Album Cover Art rendering with bounded 5-slot memory caching.
  • Instant Cloud Pairing QR Screen with 6-character PIN code.

Controls:
  PLAYER VIEW:
    A        Play / Pause toggle (instant toggle)
    RIGHT    Next track (Skip)
    LEFT     Previous track
    UP       Volume Up (+5%, instant 0ms response)
    DOWN     Volume Down (-5%, instant 0ms response)
    B        Toggle Spotify Tree Library Drawer
    C        Unlink / Disconnect Spotify
    HOME     Exit to launcher drawer

  TREE LIBRARY VIEW:
    UP/DOWN  Navigate folders, playlists, or tracks
    A / >    Open folder / playlist / Play track
    B / <    Back up folder level / Return to Player
    C        Unlink / Disconnect Spotify
"""

import time
import unicodedata
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
COL_WARN     = api.rgb(240, 160,  40)  # Offline / Warning amber

DEFAULT_LIBRARY_TRACKS = [
    {"title": "Hola Amigo",      "artist": "KR$NA, Seedhe Maut",     "album": "FAR FROM OVER", "duration": 226, "category": "Top",    "uri": "spotify:track:5W17yyFN1l8JL5MNUCvrYS"},
    {"title": "Sweater Weather", "artist": "The Neighbourhood",      "album": "I Love You.",   "duration": 240, "category": "Liked",  "uri": "spotify:track:6jhzQyn6cwPHc85PE4qBp0"},
    {"title": "Starboy",         "artist": "The Weeknd, Daft Punk",  "album": "Starboy",      "duration": 230, "category": "Liked",  "uri": "spotify:track:7MXVkk9YMctZqd1Srtv4MB"},
    {"title": "Midnight City",   "artist": "M83",                    "album": "Hurry Up",      "duration": 243, "category": "Recent", "uri": "spotify:track:6GyFP1nfCDB8lbD2bG0Hq9"},
    {"title": "G-Class",         "artist": "YUNG SAMMY, Urban Poet", "album": "G-Class",      "duration": 166, "category": "Recent", "uri": "spotify:track:2yBum3qnYBlzeGjpWQLenu"},
    {"title": "Blinding Lights", "artist": "The Weeknd",             "album": "After Hours",   "duration": 200, "category": "Top",    "uri": "spotify:track:0VjIjW4GlUZAMYd2vXMi3b"},
]


def _is_wifi_up():
    try:
        from oreoWare import wifi
        return bool(wifi.is_connected())
    except Exception:
        pass
    try:
        import native_wifi
        return bool(native_wifi.is_connected())
    except Exception:
        pass
    return True


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


def _clean_text(s):
    """Sanitize Unicode & diacritics into readable ASCII characters safely."""
    if not s:
        return ""
    try:
        s_norm = "".join(c for c in unicodedata.normalize("NFKD", str(s)) if unicodedata.category(c) != "Mn")
        cleaned = "".join(c if 32 <= ord(c) <= 126 else "" for c in s_norm)
        while "  " in cleaned:
            cleaned = cleaned.replace("  ", " ")
        return cleaned.strip() or str(s)
    except Exception:
        return str(s)


def _marquee(text, max_chars, scroll_offset):
    text = _clean_text(text)
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
    d.rect(x + 3, y + 2, 4, 6, color, fill=True)
    d.rect(x + 7, y + 1, 4, 8, color, fill=True)


def _draw_icon_next(d, x, y, color):
    d.rect(x, y + 1, 4, 8, color, fill=True)
    d.rect(x + 4, y + 2, 4, 6, color, fill=True)
    d.rect(x + 9, y, 2, 10, color, fill=True)


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
        self._view_mode = "PLAYER"

        # WiFi State
        self._wifi_online = _is_wifi_up()
        self._last_wifi_check = _ticks_ms()

        # Hierarchical Tree Navigation State
        self._tree_state = "ROOT"   # "ROOT" (Folders) | "PLAYLISTS" (Playlists) | "TRACKS" (Track List)
        self._tree_parent_state = "ROOT"
        self._tree_idx = 0
        self._tree_scroll = 0
        self._selected_root_idx = 0
        self._selected_playlist_idx = 0
        self._tree_title = "LIBRARY"
        self._tree_loading = False

        # Tree Data Caches
        self._tree_folders = [
            {"id": "liked",     "label": "Liked Songs",     "icon": "DIR",  "count": 0},
            {"id": "top",       "label": "Top Tracks",      "icon": "DIR",  "count": 0},
            {"id": "recent",    "label": "Recently Played", "icon": "DIR",  "count": 0},
            {"id": "playlists", "label": "Playlists",       "icon": "DIR",  "count": 0},
        ]
        self._folder_tracks_cache = {
            "liked": list(DEFAULT_LIBRARY_TRACKS),
            "top": [],
            "recent": [],
        }
        self._playlists_cache = []
        self._current_track_list = list(DEFAULT_LIBRARY_TRACKS)

        # Player State
        self._title = "Spotify Connect"
        self._artist = "Open Spotify / Pick Song"
        self._album = "Spotify"
        self._duration = 0.0
        self._progress = 0.0
        self._volume = 80
        self._is_playing = False
        self._device_name = "Spotify Connect"

        # Cover Art State
        self._cover_art = None
        self._last_image_url = ""
        self._cover_size = 72

        # Non-blocking Polling Worker Lock & Timers
        self._poll_in_progress = False
        self._last_poll_t = _ticks_ms()
        self._poll_interval = 2200
        self._poll_skip_until = 0
        self._title_scroll_t = 0.0
        self._dirty = True

        # QR Link Session State
        self._show_qr = False
        self._qr_session_id = None
        self._qr_url = None
        self._qr_matrix = None
        self._qr_poll_t = _ticks_ms()

        # High-Responsiveness Volume Engine
        self._vol_buffered = False
        self._vol_settle_t = 0
        self._vol_user_interacting_until = 0
        self._last_synced_vol = self._volume

        # Toast Message State
        self._toast_msg = ""
        self._toast_until = 0

        if self._spotify.is_configured():
            self._trigger_async_poll()
            self._prefetch_library_tree()
        else:
            self._start_qr_session()

    def _prefetch_library_tree(self):
        """Asynchronously pre-fetch folder counts and tracks for the tree."""
        if not self._spotify.is_configured():
            return
        self._tree_loading = True

        def _worker():
            try:
                # 1. Fetch Liked Tracks
                liked = self._spotify.get_saved_tracks(25)
                if liked:
                    self._folder_tracks_cache["liked"] = liked
                    self._tree_folders[0]["count"] = len(liked)
                else:
                    self._tree_folders[0]["count"] = len(DEFAULT_LIBRARY_TRACKS)

                # 2. Fetch Top Tracks
                top = self._spotify.get_top_tracks(20)
                if top:
                    self._folder_tracks_cache["top"] = top
                    self._tree_folders[1]["count"] = len(top)

                # 3. Fetch Recently Played
                recents = self._spotify.get_recently_played(20)
                if recents:
                    self._folder_tracks_cache["recent"] = recents
                    self._tree_folders[2]["count"] = len(recents)

                # 4. Fetch User Playlists
                pls = self._spotify.get_user_playlists(20)
                if pls:
                    self._playlists_cache = pls
                    self._tree_folders[3]["count"] = len(pls)

                # Update current active list if on Liked
                if self._tree_state == "TRACKS" and self._tree_title == "LIKED SONGS":
                    self._current_track_list = self._folder_tracks_cache["liked"]

                self._dirty = True
            except Exception:
                pass
            finally:
                self._tree_loading = False
                self._dirty = True

        try:
            import threading
            threading.Thread(target=_worker, daemon=True).start()
        except Exception:
            self._tree_loading = False

    def _open_folder(self, folder_id, label):
        """Open a folder in the tree view and load its tracks or playlists."""
        self._selected_root_idx = self._tree_idx

        if folder_id == "playlists":
            self._tree_state = "PLAYLISTS"
            self._tree_idx = self._selected_playlist_idx
            self._tree_scroll = max(0, self._tree_idx - 3)
            self._dirty = True

            # Trigger fresh load if cache is empty
            if not self._playlists_cache and self._spotify.is_configured():
                self._tree_loading = True
                def _load_pls_worker():
                    try:
                        pls = self._spotify.get_user_playlists(20)
                        if pls:
                            self._playlists_cache = pls
                            self._tree_folders[3]["count"] = len(pls)
                    except Exception:
                        pass
                    finally:
                        self._tree_loading = False
                        self._dirty = True
                try:
                    import threading
                    threading.Thread(target=_load_pls_worker, daemon=True).start()
                except Exception:
                    self._tree_loading = False
            return

        # Regular Track Folder (liked, top, recent)
        self._tree_parent_state = "ROOT"
        self._tree_state = "TRACKS"
        self._tree_title = label.upper()
        self._tree_idx = 0
        self._tree_scroll = 0

        cached_tracks = self._folder_tracks_cache.get(folder_id, [])
        if cached_tracks:
            self._current_track_list = cached_tracks
        else:
            self._current_track_list = list(DEFAULT_LIBRARY_TRACKS)
        self._dirty = True

        # Fetch fresh in background if empty
        if not cached_tracks and self._spotify.is_configured():
            self._tree_loading = True
            def _load_worker():
                try:
                    if folder_id == "liked":
                        res = self._spotify.get_saved_tracks(25)
                    elif folder_id == "top":
                        res = self._spotify.get_top_tracks(25)
                    elif folder_id == "recent":
                        res = self._spotify.get_recently_played(25)
                    else:
                        res = []
                    if res:
                        self._folder_tracks_cache[folder_id] = res
                        self._current_track_list = res
                except Exception:
                    pass
                finally:
                    self._tree_loading = False
                    self._dirty = True
            try:
                import threading
                threading.Thread(target=_load_worker, daemon=True).start()
            except Exception:
                self._tree_loading = False

    def _open_playlist(self, pl):
        """Open a specific playlist from the playlists list."""
        self._selected_playlist_idx = self._tree_idx
        self._tree_parent_state = "PLAYLISTS"
        self._tree_title = _clean_text(pl.get("name", "PLAYLIST")).upper()
        self._tree_state = "TRACKS"
        self._tree_idx = 0
        self._tree_scroll = 0
        self._current_track_list = []
        self._tree_loading = True
        self._dirty = True

        pl_id = pl.get("id")
        pl_uri = pl.get("uri")
        def _worker():
            try:
                tracks = self._spotify.get_playlist_tracks(pl_id, 25)
                if tracks:
                    for tr in tracks:
                        tr["context_uri"] = pl_uri
                    self._current_track_list = tracks
                else:
                    self._current_track_list = []
            except Exception:
                self._current_track_list = []
            finally:
                self._tree_loading = False
                self._dirty = True
        try:
            import threading
            threading.Thread(target=_worker, daemon=True).start()
        except Exception:
            self._tree_loading = False

    def _set_volume_async(self, vol):
        if not self._spotify.is_configured():
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
            pass

    def _start_qr_session(self):
        def _worker():
            sid, url = create_relay_session()
            if url:
                mat = QRCode.encode(url)
                self._qr_session_id = sid
                self._qr_url = url
                self._qr_matrix = mat
                self._show_qr = True
                self._dirty = True
        try:
            import threading
            threading.Thread(target=_worker, daemon=True).start()
        except Exception:
            self._qr_session_id, self._qr_url = create_relay_session()
            if self._qr_url:
                self._qr_matrix = QRCode.encode(self._qr_url)
                self._show_qr = True
        self._show_qr = True
        self._dirty = True

    def _trigger_async_poll(self):
        """Non-blocking background poller that keeps UI running at 60fps / 30fps."""
        if self._poll_in_progress or not self._spotify.is_configured():
            return
        self._poll_in_progress = True

        def _worker():
            try:
                state = self._spotify.get_playback()
                if not self._spotify.is_configured():
                    self._start_qr_session()
                    return

                if state:
                    now = _ticks_ms()
                    active = state.get("active", False)
                    server_playing = bool(state.get("is_playing", False))
                    self._device_name = state.get("device_name", "Spotify Connect")

                    if _ticks_diff(now, self._poll_skip_until) >= 0:
                        self._is_playing = server_playing

                    title = state.get("title", "")
                    if active and title and title not in ("No Active Playback", "Ready", "Spotify Connected", "No Active Device"):
                        self._title = _clean_text(title)
                        self._artist = _clean_text(state.get("artist", self._artist))
                        self._album = _clean_text(state.get("album", ""))
                        self._duration = state.get("duration_s", self._duration)

                        server_progress = state.get("progress_s", 0.0)
                        if abs(self._progress - server_progress) > 2.0 or not self._is_playing:
                            self._progress = server_progress

                        if _ticks_diff(now, self._vol_user_interacting_until) >= 0:
                            self._volume = state.get("volume", self._volume)
                            self._last_synced_vol = self._volume

                        img_url = state.get("image_url", "")
                        if img_url and img_url != self._last_image_url:
                            self._last_image_url = img_url
                            try:
                                self._cover_art = fetch_cover_art_rgb565(img_url, self._cover_size, self._cover_size)
                            except Exception:
                                self._cover_art = None
                    else:
                        if not active:
                            self._is_playing = False
                            self._title = state.get("title", "No Active Device")
                            self._artist = state.get("artist", "Open Spotify on phone/PC")
                            self._album = "Spotify Connect"
                            self._cover_art = None
                            self._progress = 0.0
                            self._duration = 0.0
            except Exception:
                pass
            finally:
                self._poll_in_progress = False
                self._dirty = True

        try:
            import threading
            threading.Thread(target=_worker, daemon=True).start()
        except Exception:
            self._poll_in_progress = False

    def on_button_press(self, btn):
        # ── QR Modal Handling ─────────────────────────────────────────────
        if self._show_qr:
            if btn in (api.BTN_A, api.BTN_B):
                if self._spotify.is_configured():
                    self._show_qr = False
            elif btn == api.BTN_C:
                if self._spotify.reload_persisted():
                    self._show_qr = False
                    self._trigger_async_poll()
                    self._prefetch_library_tree()
                else:
                    self._start_qr_session()
            self._dirty = True
            return

        # ── Toggle QR / Disconnect Button (BTN_C) ─────────────────────────
        if btn == api.BTN_C:
            if self._spotify.is_configured():
                self._spotify.disconnect()
                self._current_track_list = list(DEFAULT_LIBRARY_TRACKS)
                self._tree_state = "ROOT"
                self._tree_idx = 0
                self._tree_scroll = 0
                self._title = "Spotify Connect"
                self._artist = "Scan QR to Pair"
                self._album = "Ready"
                self._duration = 0.0
                self._progress = 0.0
                self._is_playing = False
                self._cover_art = None
                self._device_name = "Offline"
                self._start_qr_session()
            else:
                self._start_qr_session()
            self._dirty = True
            return

        # ── Hierarchical Tree Library View ────────────────────────────────
        if self._view_mode == "LIBRARY":
            # 1. ROOT State (Folder Selection)
            if self._tree_state == "ROOT":
                if btn in (api.BTN_B, api.BTN_LEFT):
                    self._view_mode = "PLAYER"
                    self._dirty = True
                    return
                elif btn == api.BTN_UP:
                    if self._tree_idx > 0:
                        self._tree_idx -= 1
                        if self._tree_idx < self._tree_scroll:
                            self._tree_scroll = self._tree_idx
                        self._dirty = True
                    return
                elif btn == api.BTN_DOWN:
                    if self._tree_idx < len(self._tree_folders) - 1:
                        self._tree_idx += 1
                        if self._tree_idx >= self._tree_scroll + 5:
                            self._tree_scroll = self._tree_idx - 4
                        self._dirty = True
                    return
                elif btn in (api.BTN_A, api.BTN_RIGHT):
                    # Enter Folder
                    f = self._tree_folders[self._tree_idx]
                    self._open_folder(f["id"], f["label"])
                    return

            # 2. PLAYLISTS State (List of User Playlists)
            elif self._tree_state == "PLAYLISTS":
                if btn in (api.BTN_B, api.BTN_LEFT):
                    self._tree_state = "ROOT"
                    self._tree_idx = 3  # Return cursor to Playlists item
                    self._tree_scroll = 0
                    self._dirty = True
                    return
                elif btn == api.BTN_UP:
                    if self._tree_idx > 0:
                        self._tree_idx -= 1
                        if self._tree_idx < self._tree_scroll:
                            self._tree_scroll = self._tree_idx
                        self._dirty = True
                    return
                elif btn == api.BTN_DOWN:
                    if self._playlists_cache and self._tree_idx < len(self._playlists_cache) - 1:
                        self._tree_idx += 1
                        if self._tree_idx >= self._tree_scroll + 5:
                            self._tree_scroll = self._tree_idx - 4
                        self._dirty = True
                    return
                elif btn in (api.BTN_A, api.BTN_RIGHT):
                    # Open selected playlist
                    if self._playlists_cache:
                        pl = self._playlists_cache[self._tree_idx]
                        self._open_playlist(pl)
                    return

            # 3. TRACKS State (Track List inside Folder or Playlist)
            elif self._tree_state == "TRACKS":
                if btn in (api.BTN_B, api.BTN_LEFT):
                    # Back up to playlists if opened from a playlist, else root
                    if self._tree_parent_state == "PLAYLISTS":
                        self._tree_state = "PLAYLISTS"
                        self._tree_idx = self._selected_playlist_idx
                        self._tree_scroll = max(0, self._selected_playlist_idx - 3)
                    else:
                        self._tree_state = "ROOT"
                        self._tree_idx = self._selected_root_idx
                        self._tree_scroll = max(0, self._selected_root_idx - 3)
                    self._dirty = True
                    return
                elif btn == api.BTN_UP:
                    if self._tree_idx > 0:
                        self._tree_idx -= 1
                        if self._tree_idx < self._tree_scroll:
                            self._tree_scroll = self._tree_idx
                        self._dirty = True
                    return
                elif btn == api.BTN_DOWN:
                    if self._current_track_list and self._tree_idx < len(self._current_track_list) - 1:
                        self._tree_idx += 1
                        if self._tree_idx >= self._tree_scroll + 5:
                            self._tree_scroll = self._tree_idx - 4
                        self._dirty = True
                    return
                elif btn == api.BTN_A:
                    # Select & Play song
                    if self._current_track_list:
                        t = self._current_track_list[self._tree_idx]
                        self._title = _clean_text(t["title"])
                        self._artist = _clean_text(t["artist"])
                        self._album = _clean_text(t["album"])
                        self._duration = t["duration"]
                        self._progress = 0.0
                        self._is_playing = True
                        self._cover_art = None
                        self._title_scroll_t = 0.0
                        self._view_mode = "PLAYER"
                        self._poll_skip_until = _ticks_ms() + 3000

                        track_target = t.get("uri") or (t["title"] + " " + t["artist"])
                        context_target = t.get("context_uri")
                        def _play_worker(target, ctx):
                            try:
                                if target and str(target).startswith("spotify:track:"):
                                    self._spotify.play(uris=[str(target)])
                                else:
                                    self._spotify.play_track(target)
                                time.sleep(0.8)
                                self._trigger_async_poll()
                            except Exception:
                                pass
                        try:
                            import threading
                            threading.Thread(target=_play_worker, args=(track_target, context_target), daemon=True).start()
                        except Exception:
                            pass
                    self._dirty = True
                    return
            return

        # ── Player View Controls (0ms Latency Optimistic Responses) ────────
        now = _ticks_ms()

        if btn == api.BTN_B:
            # Open Tree Library Drawer
            self._view_mode = "LIBRARY"
            self._tree_state = "ROOT"
            self._tree_idx = self._selected_root_idx
            self._tree_scroll = max(0, self._selected_root_idx - 3)
            self._prefetch_library_tree()
            self._dirty = True

        elif btn == api.BTN_A:
            # Instant 0ms Play / Pause toggle
            self._is_playing = not self._is_playing
            self._poll_skip_until = now + 2500
            current_target = None
            if self._current_track_list:
                t = self._current_track_list[0]
                current_target = t.get("uri") or (t["title"] + " " + t["artist"])

            def _toggle_worker(should_play, target):
                try:
                    if should_play:
                        res = self._spotify.play()
                        if not res and target:
                            self._spotify.play_track(target)
                    else:
                        self._spotify.pause()
                    time.sleep(0.6)
                    self._trigger_async_poll()
                except Exception:
                    pass
            try:
                import threading
                threading.Thread(target=_toggle_worker, args=(self._is_playing, current_target), daemon=True).start()
            except Exception:
                pass
            self._dirty = True

        elif btn == api.BTN_RIGHT:
            self._poll_skip_until = now + 2000
            def _next_worker():
                try:
                    self._spotify.next_track()
                    time.sleep(0.8)
                    self._trigger_async_poll()
                except Exception:
                    pass
            try:
                import threading
                threading.Thread(target=_next_worker, daemon=True).start()
            except Exception:
                pass
            self._dirty = True

        elif btn == api.BTN_LEFT:
            self._poll_skip_until = now + 2000
            def _prev_worker():
                try:
                    self._spotify.prev_track()
                    time.sleep(0.8)
                    self._trigger_async_poll()
                except Exception:
                    pass
            try:
                import threading
                threading.Thread(target=_prev_worker, daemon=True).start()
            except Exception:
                pass
            self._dirty = True

        elif btn == api.BTN_UP:
            self._volume = min(100, self._volume + 5)
            self._vol_buffered = True
            self._vol_settle_t = now + 250
            self._vol_user_interacting_until = now + 1500
            self._dirty = True

        elif btn == api.BTN_DOWN:
            self._volume = max(0, self._volume - 5)
            self._vol_buffered = True
            self._vol_settle_t = now + 250
            self._vol_user_interacting_until = now + 1500
            self._dirty = True

    def update(self, dt):
        now = _ticks_ms()

        # Check WiFi status periodically
        if _ticks_diff(now, self._last_wifi_check) > 2500:
            self._last_wifi_check = now
            self._wifi_online = _is_wifi_up()

        # Volume Debounce Flush
        if self._vol_buffered and _ticks_diff(now, self._vol_settle_t) >= 0:
            self._vol_buffered = False
            if self._volume != self._last_synced_vol:
                self._last_synced_vol = self._volume
                self._set_volume_async(self._volume)

        # Update QR Pairing Session
        if self._show_qr and self._qr_session_id:
            if _ticks_diff(now, self._qr_poll_t) > 2000:
                self._qr_poll_t = now
                def _qr_check():
                    try:
                        creds = poll_relay_session(self._qr_session_id)
                        if creds and creds.get("status") != "pending":
                            save_credentials(creds)
                            if self._spotify.reload_persisted():
                                self._show_qr = False
                                self._trigger_async_poll()
                                self._prefetch_library_tree()
                                self._dirty = True
                    except Exception:
                        pass
                try:
                    import threading
                    threading.Thread(target=_qr_check, daemon=True).start()
                except Exception:
                    pass

        # Periodic Asynchronous Playback Polling
        if not self._show_qr and self._spotify.is_configured():
            if _ticks_diff(now, self._poll_skip_until) >= 0:
                if _ticks_diff(now, self._last_poll_t) > self._poll_interval:
                    self._last_poll_t = now
                    self._trigger_async_poll()

        # Smooth Sub-second Playback Progress
        if self._is_playing:
            self._progress += dt
            if self._duration > 0 and self._progress >= self._duration:
                self._trigger_async_poll()
            self._dirty = True

        # Smooth Text Marquee Ticker
        self._title_scroll_t += dt * 3.5
        if len(self._title) > 16 or len(self._artist) > 16:
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

        # ── Hierarchical Tree Library View ────────────────────────────────
        if self._view_mode == "LIBRARY":
            self._draw_library_tree(d)
            self._dirty = False
            return

        # ── Now Playing View ──────────────────────────────────────────────
        self._draw_player(d)
        self._dirty = False

    def _draw_player(self, d):
        app_title = "SPOTIFY CONNECT" if self._spotify.is_configured() else "SPOTIFY"
        widgets.draw_header(d, app_title)

        csz = self._cover_size
        cover_box_x = 8
        cover_box_y = widgets.HEADER_H + 5

        d.rect(cover_box_x - 2, cover_box_y - 2, csz + 4, csz + 4, COL_CARD_BD, fill=True)
        d.rect(cover_box_x - 2, cover_box_y - 2, csz + 4, csz + 4, COL_SPOTIFY if self._is_playing else COL_CARD_BD, fill=False)

        if self._cover_art:
            d.blit(self._cover_art, cover_box_x, cover_box_y, csz, csz)
        else:
            d.rect(cover_box_x, cover_box_y, csz, csz, api.rgb(20, 22, 28), fill=True)
            cx = cover_box_x + csz // 2
            cy = cover_box_y + csz // 2
            d.rect(cx - 28, cy - 28, 56, 56, api.rgb(36, 40, 52), fill=False)
            d.rect(cx - 18, cy - 18, 36, 36, api.rgb(48, 54, 70), fill=False)
            d.rect(cx - 11, cy - 11, 22, 22, COL_SPOTIFY, fill=True)
            d.rect(cx - 3, cy - 3, 6, 6, api.BLACK, fill=True)

        meta_x = cover_box_x + csz + 6
        meta_w = SW - meta_x - 8
        meta_y = cover_box_y - 2
        meta_h = csz + 4

        d.rect(meta_x, meta_y, meta_w, meta_h, COL_CARD, fill=True)
        d.rect(meta_x, meta_y, meta_w, meta_h, COL_CARD_BD, fill=False)

        max_chars = (meta_w - 14) // 8

        display_title = _marquee(self._title, max_chars, self._title_scroll_t)
        d.text(display_title, meta_x + 7, meta_y + 7, api.WHITE)

        display_artist = _marquee(self._artist, max_chars, self._title_scroll_t * 0.8)
        d.text(display_artist, meta_x + 7, meta_y + 23, COL_SPOTIFY)

        album_str = _clean_text(self._album or "Single")
        if len(album_str) > max_chars:
            album_str = album_str[:max_chars - 2] + ".."
        d.text(album_str, meta_x + 7, meta_y + 39, COL_MUTED)

        dev_tag = _clean_text(self._device_name or "Spotify Connect")
        if len(dev_tag) > max_chars - 3:
            dev_tag = dev_tag[:max_chars - 5] + ".."
        pill_w = len(dev_tag) * 8 + 14
        d.rect(meta_x + 7, meta_y + 54, pill_w, 13, COL_CARD_BD, fill=True)
        d.rect(meta_x + 7, meta_y + 54, pill_w, 13, COL_SPOTIFY, fill=False)
        d.rect(meta_x + 11, meta_y + 58, 3, 3, COL_SPOTIFY, fill=True)
        d.text(dev_tag, meta_x + 18, meta_y + 57, COL_CYAN)

        prog_card_y = cover_box_y + csz + 8
        prog_card_h = 46
        d.rect(8, prog_card_y, SW - 16, prog_card_h, COL_CARD, fill=True)
        d.rect(8, prog_card_y, SW - 16, prog_card_h, COL_CARD_BD, fill=False)

        cur_time_str = _format_time(self._progress)
        tot_time_str = _format_time(self._duration)
        d.text(cur_time_str, 16, prog_card_y + 8, api.WHITE)
        d.text(tot_time_str, SW - 16 - len(tot_time_str) * 8, prog_card_y + 8, api.WHITE)

        status_label = "PLAYING" if self._is_playing else "PAUSED"
        stat_w = len(status_label) * 8
        stat_x = (SW - stat_w) // 2
        d.text(status_label, stat_x, prog_card_y + 8, COL_SPOTIFY if self._is_playing else theme.GOLD)

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

        ctrl_y = prog_card_y + prog_card_h + 6
        ctrl_h = 36
        d.rect(8, ctrl_y, SW - 16, ctrl_h, COL_CARD, fill=True)
        d.rect(8, ctrl_y, SW - 16, ctrl_h, COL_CARD_BD, fill=False)

        _draw_icon_prev(d, 28, ctrl_y + 13, api.WHITE)

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

        _draw_icon_next(d, 108, ctrl_y + 13, api.WHITE)

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

        now = _ticks_ms()
        if self._toast_until > 0 and _ticks_diff(now, self._toast_until) < 0:
            tw = len(self._toast_msg) * 8 + 24
            tx = (SW - tw) // 2
            ty = widgets.HEADER_H + 6
            d.rect(tx, ty, tw, 22, api.rgb(20, 22, 28), fill=True)
            d.rect(tx, ty, tw, 22, theme.GOLD, fill=False)
            d.text(self._toast_msg, tx + 12, ty + 7, theme.GOLD)

        c_act = "C:Unlink" if self._spotify.is_configured() else "C:Link"
        widgets.draw_hint(d, "A:Play  <>:Skip  ^v:Vol  B:Lib  " + c_act)

    def _draw_library_tree(self, d):
        # 1. Header (Clean concise section title)
        if self._tree_state == "ROOT":
            header_str = "LIBRARY"
        elif self._tree_state == "PLAYLISTS":
            header_str = "PLAYLISTS"
        else:
            header_str = self._tree_title[:14]
        widgets.draw_header(d, header_str)

        card_x = 8
        card_y = widgets.HEADER_H + 4
        card_w = SW - 16
        card_h = SH - widgets.HEADER_H - widgets.HINT_H - 8
        d.rect(card_x, card_y, card_w, card_h, COL_CARD, fill=True)
        d.rect(card_x, card_y, card_w, card_h, COL_CARD_BD, fill=False)

        # ── STATE 1: ROOT FOLDERS TREE ────────────────────────────────────
        if self._tree_state == "ROOT":
            folders = self._tree_folders
            row_h = 34
            for i, f in enumerate(folders):
                ry = card_y + 4 + i * (row_h + 2)
                rx = card_x + 4
                rw = card_w - 8
                is_sel = (i == self._tree_idx)

                if is_sel:
                    d.rect(rx, ry, rw, row_h, api.rgb(38, 44, 60), fill=True)
                    d.rect(rx, ry, 3, row_h, COL_SPOTIFY, fill=True)
                else:
                    d.rect(rx, ry, rw, row_h, api.rgb(20, 22, 28), fill=True)

                # Folder Icon graphic
                fx = rx + 8
                fy = ry + 11
                d.rect(fx, fy, 4, 2, COL_SPOTIFY, fill=True)
                d.rect(fx, fy + 2, 14, 9, COL_SPOTIFY if is_sel else COL_MUTED, fill=False)
                d.rect(fx + 2, fy + 4, 10, 5, COL_SPOTIFY if is_sel else COL_MUTED, fill=True)

                # Folder Label
                lbl_color = api.WHITE if is_sel else api.rgb(210, 215, 225)
                d.text(f["label"], rx + 30, ry + 8, lbl_color)

                # Item Count / Status
                cnt = f.get("count", 0)
                sub_str = f"{cnt} tracks" if f["id"] != "playlists" else f"{cnt} playlists"
                d.text(sub_str, rx + 30, ry + 20, COL_SPOTIFY if is_sel else COL_MUTED)

                # Right Arrow
                d.text(">", rx + rw - 14, ry + 12, COL_SPOTIFY if is_sel else COL_MUTED)

            widgets.draw_hint(d, "A:Open  ^v:Select  B:Player  C:Unlink")
            return

        # ── STATE 2: PLAYLIST LIST ────────────────────────────────────────
        if self._tree_state == "PLAYLISTS":
            pls = self._playlists_cache
            if self._tree_loading and not pls:
                d.text("Loading Playlists...", card_x + 36, card_y + 50, COL_SPOTIFY)
                d.text("Fetching from Spotify...", card_x + 36, card_y + 70, COL_MUTED)
            elif not pls:
                d.text("No Playlists Found", card_x + 36, card_y + 50, COL_MUTED)
                d.text("Create one in Spotify", card_x + 36, card_y + 70, COL_SPOTIFY)
                d.text("Press B for Library", card_x + 36, card_y + 90, COL_MUTED)
            else:
                row_h = 34
                vis_count = 5
                for i in range(vis_count):
                    item_idx = self._tree_scroll + i
                    if item_idx >= len(pls): break
                    pl = pls[item_idx]
                    ry = card_y + 4 + i * (row_h + 2)
                    rx = card_x + 4
                    rw = card_w - 14
                    is_sel = (item_idx == self._tree_idx)

                    if is_sel:
                        d.rect(rx, ry, rw, row_h, api.rgb(38, 44, 60), fill=True)
                        d.rect(rx, ry, 3, row_h, COL_SPOTIFY, fill=True)
                    else:
                        d.rect(rx, ry, rw, row_h, api.rgb(20, 22, 28), fill=True)

                    # Playlist Icon
                    d.text(">", rx + 8, ry + 12, COL_SPOTIFY if is_sel else COL_MUTED)

                    # Playlist Name (Cleaned)
                    p_name = _clean_text(pl.get("name", "Playlist"))[:18]
                    d.text(p_name, rx + 24, ry + 6, api.WHITE if is_sel else api.rgb(210, 215, 225))

                    # Track count
                    t_cnt = pl.get("tracks_count", 0)
                    owner = _clean_text(pl.get("owner", "Spotify"))[:12]
                    d.text(f"{t_cnt} tracks / {owner}", rx + 24, ry + 20, COL_SPOTIFY if is_sel else COL_MUTED)

                # Scrollbar
                if len(pls) > vis_count:
                    sb_x = card_x + card_w - 6
                    sb_y = card_y + 6
                    sb_h = card_h - 12
                    d.rect(sb_x, sb_y, 2, sb_h, COL_BAR_BG, fill=True)
                    thumb_h = max(14, int((vis_count / len(pls)) * sb_h))
                    thumb_y = sb_y + int((self._tree_scroll / max(1, len(pls) - vis_count)) * (sb_h - thumb_h))
                    d.rect(sb_x - 1, thumb_y, 4, thumb_h, COL_SPOTIFY, fill=True)

            widgets.draw_hint(d, "A:Open  ^v:Select  B:Folders  C:Unlink")
            return

        # ── STATE 3: TRACK LIST (Inside Category or Playlist) ─────────────
        tracks = self._current_track_list
        if self._tree_loading and not tracks:
            d.text("Loading Tracks...", card_x + 36, card_y + 50, COL_SPOTIFY)
            d.text("Fetching playlist...", card_x + 36, card_y + 70, COL_MUTED)
        elif not tracks:
            d.text("Playlist is empty", card_x + 36, card_y + 50, COL_MUTED)
            d.text("Press B to go back", card_x + 36, card_y + 70, COL_SPOTIFY)
        else:
            row_h = 34
            visible_count = 5
            for i in range(visible_count):
                item_idx = self._tree_scroll + i
                if item_idx >= len(tracks): break
                t = tracks[item_idx]
                ry = card_y + 4 + i * (row_h + 2)
                rx = card_x + 4
                rw = card_w - 14

                is_selected = (item_idx == self._tree_idx)
                clean_t_title = _clean_text(t.get("title", "Track"))
                is_active_track = (clean_t_title.lower() == self._title.lower())

                if is_selected:
                    d.rect(rx, ry, rw, row_h, api.rgb(38, 44, 60), fill=True)
                    d.rect(rx, ry, 3, row_h, COL_SPOTIFY, fill=True)
                else:
                    d.rect(rx, ry, rw, row_h, api.rgb(20, 22, 28), fill=True)

                if is_active_track and self._is_playing:
                    d.rect(rx + 8, ry + 12, 2, 8, COL_SPOTIFY, fill=True)
                    d.rect(rx + 12, ry + 8, 2, 12, COL_SPOTIFY, fill=True)
                    d.rect(rx + 16, ry + 14, 2, 6, COL_SPOTIFY, fill=True)
                else:
                    num_str = "%02d" % (item_idx + 1)
                    d.text(num_str, rx + 8, ry + 12, COL_SPOTIFY if is_selected else COL_MUTED)

                t_color = api.WHITE if is_selected else api.rgb(210, 215, 225)
                d.text(clean_t_title[:18], rx + 28, ry + 6, t_color)

                clean_artist = _clean_text(t.get("artist", "Artist"))
                cat = t.get("category", "Spotify")
                sub_str = ("%s / %s" % (clean_artist[:14], cat))[:22]
                d.text(sub_str, rx + 28, ry + 20, COL_SPOTIFY if is_selected else COL_MUTED)

                dur_str = _format_time(t.get("duration", 0))
                d.text(dur_str, rx + rw - len(dur_str) * 8 - 4, ry + 12, COL_MUTED)

            if len(tracks) > visible_count:
                sb_x = card_x + card_w - 6
                sb_y = card_y + 6
                sb_h = card_h - 12
                d.rect(sb_x, sb_y, 2, sb_h, COL_BAR_BG, fill=True)
                total_items = len(tracks)
                thumb_h = max(14, int((visible_count / total_items) * sb_h))
                thumb_y = sb_y + int((self._tree_scroll / max(1, total_items - visible_count)) * (sb_h - thumb_h))
                d.rect(sb_x - 1, thumb_y, 4, thumb_h, COL_SPOTIFY, fill=True)

        widgets.draw_hint(d, "A:Play  ^v:Select  B:Back  C:Unlink")

    def _draw_qr_screen(self, d):
        widgets.draw_header(d, "LINK SPOTIFY")
        card_w = SW - 20
        card_h = SH - widgets.HEADER_H - widgets.HINT_H - 8
        d.rect(10, widgets.HEADER_H + 4, card_w, card_h, COL_CARD, fill=True)
        d.rect(10, widgets.HEADER_H + 4, card_w, card_h, COL_CARD_BD, fill=False)

        if self._qr_matrix:
            mat = self._qr_matrix
            rows = len(mat)
            cols = len(mat[0])
            mod_sz = 3
            qr_w = cols * mod_sz
            qr_h = rows * mod_sz
            qx = 16
            qy = widgets.HEADER_H + 14

            d.rect(qx - 4, qy - 4, qr_w + 8, qr_h + 8, api.WHITE, fill=True)
            for r in range(rows):
                for c in range(cols):
                    if mat[r][c]:
                        d.rect(qx + c * mod_sz, qy + r * mod_sz, mod_sz, mod_sz, api.BLACK, fill=True)

            tx = qx + qr_w + 14
            d.text("SCAN QR CODE", tx, qy + 2, COL_SPOTIFY)
            d.text("or visit on web:", tx, qy + 18, COL_MUTED)

            code_str = str(self._qr_session_id or "------").upper()
            pin_box_w = max(100, len(code_str) * 16 + 24)
            d.rect(tx, qy + 32, pin_box_w, 32, api.rgb(38, 44, 60), fill=True)
            d.rect(tx, qy + 32, pin_box_w, 32, theme.GOLD, fill=False)
            d.text(code_str, tx + 12, qy + 40, theme.GOLD, scale=2)

            d.text("oreo-delta.vercel.app", tx, qy + 72, api.WHITE)
            d.text("/spotify", tx, qy + 84, api.WHITE)
            d.text("Waiting login...", tx, qy + 102, COL_CYAN)
        else:
            d.text("Generating Link...", 80, 110, COL_SPOTIFY)

        widgets.draw_hint(d, "A/B:Cancel  C:Refresh")
