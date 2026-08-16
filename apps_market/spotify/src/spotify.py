"""Spotify Web API Client for MicroPython & Desktop Oreo OS.

Handles authentication, playback state querying, and transport controls
(Play, Pause, Next, Previous, Volume, Shuffle, Repeat) with automatic token
refreshing over standard TLS sockets.
"""

import time

try:
    import socket as _socket
    import ssl    as _ssl
    _RAW_OK = True
except ImportError:
    _RAW_OK = False

try:
    import json as _json
except ImportError:
    import ujson as _json

try:
    import ubinascii as _binascii
except ImportError:
    import binascii as _binascii


STATE_FILE = "state_spotify.json"


def _base64_encode(s):
    try:
        return _binascii.b2a_base64(s.encode('utf-8')).decode('utf-8').strip()
    except Exception:
        return ""


def load_persisted_credentials():
    for fpath in (STATE_FILE, "apps_market/spotify/" + STATE_FILE, "apps/spotify/" + STATE_FILE):
        try:
            with open(fpath, "r") as f:
                data = _json.loads(f.read())
                token = data.get("token") or data.get("access_token")
                refresh_token = data.get("refresh_token")
                client_id = data.get("client_id")
                client_secret = data.get("client_secret")
                if isinstance(token, str) and token.strip() and not token.startswith("{"):
                    pass
                else:
                    token = None
                if isinstance(refresh_token, str) and refresh_token.strip() and not refresh_token.startswith("{"):
                    pass
                else:
                    refresh_token = None
                if token or refresh_token:
                    return (token, refresh_token, client_id, client_secret)
        except Exception:
            pass
    return (None, None, None, None)


def save_credentials(token=None, refresh_token=None, client_id=None, client_secret=None):
    try:
        if isinstance(token, dict):
            d = token
            if d.get("status") == "pending":
                return False
            token = d.get("token") or d.get("access_token")
            refresh_token = d.get("refresh_token") or refresh_token
            client_id = d.get("client_id") or client_id
            client_secret = d.get("client_secret") or client_secret

        cur_t, cur_rt, cur_ci, cur_cs = load_persisted_credentials()
        final_token = token if (isinstance(token, str) and token.strip()) else cur_t
        final_rt = refresh_token if (isinstance(refresh_token, str) and refresh_token.strip()) else cur_rt
        final_ci = client_id or cur_ci
        final_cs = client_secret or cur_cs

        if not final_token and not final_rt:
            return False

        data = {
            "access_token": final_token,
            "token": final_token,
            "refresh_token": final_rt,
            "client_id": final_ci,
            "client_secret": final_cs,
            "updated_at": int(time.time() if hasattr(time, 'time') else 0),
        }
        with open(STATE_FILE, "w") as f:
            f.write(_json.dumps(data))
        return True
    except Exception:
        return False


def clear_credentials():
    """Wipe saved Spotify tokens and credentials from disk."""
    for fpath in (STATE_FILE, "apps_market/spotify/" + STATE_FILE, "apps/spotify/" + STATE_FILE):
        try:
            import os
            if os.path.exists(fpath):
                os.remove(fpath)
        except Exception:
            pass
    try:
        with open(STATE_FILE, "w") as f:
            f.write("{}")
    except Exception:
        pass
    return True


_COVER_CACHE = {}

def create_relay_session():
    """Request a 6-character PIN session from oreo-delta.vercel.app."""
    base_url = "https://oreo-delta.vercel.app/api/spotify/session"
    try:
        from oreoOS import config
        base_url = getattr(config, "SPOTIFY_RELAY_URL", "https://oreo-delta.vercel.app") + "/api/spotify/session"
    except Exception:
        pass

    try:
        import urllib.request
        req = urllib.request.Request(base_url, headers={"User-Agent": "OreoBadge/1.0"})
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            data = _json.loads(resp.read().decode())
            if data.get("status") == "ok":
                return data.get("code"), data.get("url")
    except Exception:
        pass
    return None, "https://oreo-delta.vercel.app/spotify"


def poll_relay_session(code):
    """Poll oreo-delta.vercel.app to check if the session code was authorized."""
    if not code:
        return None
    base_url = "https://oreo-delta.vercel.app/api/spotify/poll?code=" + str(code)
    try:
        from oreoOS import config
        base_url = getattr(config, "SPOTIFY_RELAY_URL", "https://oreo-delta.vercel.app") + "/api/spotify/poll?code=" + str(code)
    except Exception:
        pass

    try:
        import urllib.request
        req = urllib.request.Request(base_url, headers={"User-Agent": "OreoBadge/1.0"})
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            return _json.loads(resp.read().decode())
    except Exception:
        pass
    return None


def fetch_cover_art_rgb565(url, target_w=64, target_h=64):
    if not url:
        return None
    cache_key = "%s_%d_%d" % (url, target_w, target_h)
    if cache_key in _COVER_CACHE:
        return _COVER_CACHE[cache_key]

    try:
        import urllib.request
        import io
        import gc
        try:
            import PIL.Image as Image
            req = urllib.request.Request(url, headers={"User-Agent": "OreoBadge/1.0"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = resp.read()
            img = Image.open(io.BytesIO(data)).convert("RGB").resize((target_w, target_h))
            raw = bytearray(target_w * target_h * 2)
            idx = 0
            for y in range(target_h):
                for x in range(target_w):
                    r, g, b = img.getpixel((x, y))
                    rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                    raw[idx] = (rgb565 >> 8) & 0xFF
                    raw[idx + 1] = rgb565 & 0xFF
                    idx += 2
            
            # Bound cache size to 5 items to prevent heap bloat on ESP32-S3
            if len(_COVER_CACHE) >= 5:
                oldest = next(iter(_COVER_CACHE))
                del _COVER_CACHE[oldest]
                gc.collect()

            _COVER_CACHE[cache_key] = raw
            return raw
        except ImportError:
            pass
    except Exception:
        pass
    return None


class SpotifyClient:
    API_HOST  = "api.spotify.com"
    AUTH_HOST = "accounts.spotify.com"
    PORT      = 443
    TIMEOUT_S = 3.5

    def __init__(self, token=None, refresh_token=None, client_id=None, client_secret=None):
        self.token          = token
        self.refresh_token  = refresh_token
        self.client_id      = client_id
        self.client_secret  = client_secret
        self.last_sync_ms   = 0
        self.device_name    = ""
        self.last_error     = ""

        if not self.is_configured():
            self.reload_persisted()

    def is_configured(self):
        return bool(self.token or (self.refresh_token and self.client_id) or self.refresh_token)

    def reload_persisted(self):
        t, rt, ci, cs = load_persisted_credentials()
        if t:  self.token = t
        if rt: self.refresh_token = rt
        if ci: self.client_id = ci
        if cs: self.client_secret = cs
        return self.is_configured()

    def disconnect(self):
        """Wipe memory tokens and clear persisted credentials on disk."""
        self.token = None
        self.refresh_token = None
        self.client_id = None
        self.client_secret = None
        self.device_name = ""
        clear_credentials()

    def _http_request(self, host, method, path, headers=None, body_data=None):
        if not _RAW_OK:
            return 0, None

        headers = headers or {}
        headers.setdefault("Host", host)
        headers.setdefault("User-Agent", "OreoBadge-Spotify/1.0")
        headers.setdefault("Accept", "application/json")
        headers.setdefault("Connection", "close")

        if body_data:
            b_bytes = body_data.encode('utf-8') if isinstance(body_data, str) else body_data
            headers["Content-Length"] = str(len(b_bytes))
        else:
            headers["Content-Length"] = "0"
            b_bytes = b""

        s = None
        try:
            # 1. DNS & Connect
            raw = None
            for res in _socket.getaddrinfo(host, self.PORT):
                af, socktype, proto, _, sa = res
                try:
                    raw = _socket.socket(af, socktype, proto)
                    raw.settimeout(self.TIMEOUT_S)
                    raw.connect(sa)
                    break
                except Exception:
                    if raw is not None:
                        try: raw.close()
                        except Exception: pass
                    raw = None

            if raw is None:
                self.last_error = "DNS/Connect failed"
                return 0, None

            # 2. SSL Handshake
            if hasattr(_ssl, "create_default_context"):
                ctx = _ssl.create_default_context()
                s = ctx.wrap_socket(raw, server_hostname=host)
            else:
                s = _ssl.wrap_socket(raw)

            s.settimeout(self.TIMEOUT_S)

            # 3. Write Request
            req_lines = ["%s %s HTTP/1.1" % (method, path)]
            for k, v in headers.items():
                req_lines.append("%s: %s" % (k, v))
            req_lines.append("")
            req_lines.append("")
            header_str = "\r\n".join(req_lines)
            s.write(header_str.encode('utf-8'))
            if b_bytes:
                s.write(b_bytes)

            # 4. Read Response
            resp = b""
            while True:
                try:
                    chunk = s.read(1024)
                    if not chunk:
                        break
                    resp += chunk
                except Exception:
                    break

            s.close()
            s = None

            if not resp:
                return 0, None

            # 5. Parse Status & Body
            header_end = resp.find(b"\r\n\r\n")
            if header_end < 0:
                header_part = resp
                body_part = b""
            else:
                header_part = resp[:header_end]
                body_part = resp[header_end + 4:]

            first_line = header_part.split(b"\r\n", 1)[0].decode('utf-8', 'ignore')
            parts = first_line.split(" ")
            status = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0

            return status, body_part

        except Exception as e:
            self.last_error = str(e)
            if s is not None:
                try: s.close()
                except Exception: pass
            return 0, None

    def refresh_access_token(self):
        if not self.refresh_token:
            return False

        if self.client_secret:
            auth_str = _base64_encode("%s:%s" % (self.client_id or "", self.client_secret or ""))
            headers = {
                "Authorization": "Basic " + auth_str,
                "Content-Type": "application/x-www-form-urlencoded"
            }
            body = "grant_type=refresh_token&refresh_token=" + self.refresh_token
        else:
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            body = "grant_type=refresh_token&refresh_token=" + self.refresh_token
            if self.client_id:
                body += "&client_id=" + self.client_id

        status, resp_bytes = self._http_request(self.AUTH_HOST, "POST", "/api/token", headers, body)

        if status == 200 and resp_bytes:
            try:
                data = _json.loads(resp_bytes.decode('utf-8'))
                new_token = data.get("access_token")
                if new_token:
                    self.token = new_token
                    save_credentials(token=new_token, refresh_token=self.refresh_token, client_id=self.client_id, client_secret=self.client_secret)
                    return True
            except Exception:
                pass
        return False

    def get_devices(self):
        """Fetch list of available Spotify devices."""
        if not self.token and not self.refresh_access_token():
            return []
        headers = {"Authorization": "Bearer " + str(self.token)}
        status, body = self._http_request(self.API_HOST, "GET", "/v1/me/player/devices", headers)
        if status == 401 and self.refresh_access_token():
            headers = {"Authorization": "Bearer " + str(self.token)}
            status, body = self._http_request(self.API_HOST, "GET", "/v1/me/player/devices", headers)
        if status == 200 and body:
            try:
                data = _json.loads(body.decode('utf-8'))
                return data.get("devices", []) or []
            except Exception:
                pass
        return []

    def get_playback(self):
        if not self.token:
            if not self.refresh_access_token():
                return None

        headers = {"Authorization": "Bearer " + str(self.token)}
        status, body = self._http_request(self.API_HOST, "GET", "/v1/me/player", headers)

        if status == 401:
            if self.refresh_access_token():
                headers = {"Authorization": "Bearer " + str(self.token)}
                status, body = self._http_request(self.API_HOST, "GET", "/v1/me/player", headers)
            else:
                self.token = None
                self.refresh_token = None
                clear_credentials()
                return None

        if status == 403:
            return {
                "connected":   True,
                "active":      True,
                "is_playing":  False,
                "title":       "Spotify Connected",
                "artist":      "Open Spotify on device",
                "album":       "",
                "image_url":   "",
                "duration_s":  0,
                "progress_s":  0,
                "volume":      70,
                "device_name": "Ready",
                "shuffle":     False,
                "repeat":      "off"
            }

        # 1. If /v1/me/player returned 200 with track item
        if status == 200 and body:
            try:
                data = _json.loads(body.decode('utf-8'))
                item = data.get("item")
                if item:
                    artists = item.get("artists", [])
                    artist_names = ", ".join(a.get("name", "") for a in artists) or "Unknown Artist"
                    images = (item.get("album") or {}).get("images", [])
                    image_url = images[-1].get("url", "") if images else ""

                    dev = data.get("device", {})
                    is_active = bool(data.get("is_playing", False)) or bool(dev.get("is_active", False))
                    self.device_name = dev.get("name", "Spotify") if dev else "Spotify (Ready)"

                    return {
                        "connected":   True,
                        "active":      is_active,
                        "is_playing":  bool(data.get("is_playing", False)),
                        "title":       item.get("name", ""),
                        "artist":      artist_names,
                        "album":       (item.get("album") or {}).get("name", ""),
                        "image_url":   image_url,
                        "duration_s":  (item.get("duration_ms", 0) or 0) / 1000.0,
                        "progress_s":  (data.get("progress_ms", 0) or 0) / 1000.0,
                        "volume":      dev.get("volume_percent", 70),
                        "device_name": self.device_name,
                        "shuffle":     bool(data.get("shuffle_state", False)),
                        "repeat":      data.get("repeat_state", "off"),
                    }
            except Exception:
                pass

        # 2. Fallback: Query /v1/me/player/currently-playing (reliable for Web Player & desktop apps)
        status_cp, body_cp = self._http_request(self.API_HOST, "GET", "/v1/me/player/currently-playing", headers)
        if status_cp == 200 and body_cp:
            try:
                data_cp = _json.loads(body_cp.decode('utf-8'))
                item = data_cp.get("item")
                if item:
                    artists = item.get("artists", [])
                    artist_names = ", ".join(a.get("name", "") for a in artists) or "Unknown Artist"
                    images = (item.get("album") or {}).get("images", [])
                    image_url = images[-1].get("url", "") if images else ""

                    devs = self.get_devices()
                    dev_name = "Spotify (Ready)"
                    vol = 70
                    if devs:
                        for d in devs:
                            if d.get("is_active"):
                                dev_name = d.get("name", dev_name)
                                vol = d.get("volume_percent", 70)
                                break
                        else:
                            dev_name = devs[0].get("name", dev_name)
                            vol = devs[0].get("volume_percent", 70)

                    return {
                        "connected":   True,
                        "active":      True,
                        "is_playing":  bool(data_cp.get("is_playing", False)),
                        "title":       item.get("name", ""),
                        "artist":      artist_names,
                        "album":       (item.get("album") or {}).get("name", ""),
                        "image_url":   image_url,
                        "duration_s":  (item.get("duration_ms", 0) or 0) / 1000.0,
                        "progress_s":  (data_cp.get("progress_ms", 0) or 0) / 1000.0,
                        "volume":      vol,
                        "device_name": dev_name,
                        "shuffle":     False,
                        "repeat":      "off",
                    }
            except Exception:
                pass

        # 3. Truly idle / stopped state
        devs = self.get_devices()
        dev_name = "Spotify (Ready)"
        if devs:
            for d in devs:
                if d.get("is_active"):
                    dev_name = d.get("name", dev_name)
                    break
            else:
                dev_name = devs[0].get("name", dev_name)

        return {
            "connected":   True,
            "active":      False,
            "is_playing":  False,
            "title":       "",
            "artist":      "",
            "album":       "",
            "image_url":   "",
            "duration_s":  0,
            "progress_s":  0,
            "volume":      70,
            "device_name": dev_name,
            "repeat":      "off"
        }

    def play(self, uris=None, context_uri=None):
        if context_uri:
            body = _json.dumps({"context_uri": context_uri})
            return self._send_control("PUT", "/v1/me/player/play", body_data=body)
        elif uris:
            body = _json.dumps({"uris": uris})
            return self._send_control("PUT", "/v1/me/player/play", body_data=body)
        return self._send_control("PUT", "/v1/me/player/play")

    def pause(self):
        return self._send_control("PUT", "/v1/me/player/pause")

    def next_track(self):
        return self._send_control("POST", "/v1/me/player/next")

    def prev_track(self):
        return self._send_control("POST", "/v1/me/player/previous")

    def set_volume(self, volume_pct):
        pct = max(0, min(100, int(volume_pct)))
        return self._send_control("PUT", "/v1/me/player/volume?volume_percent=%d" % pct)

    def get_saved_tracks(self, limit=25):
        """Fetch user's Liked / Saved Songs from Spotify."""
        if not self.token and not self.refresh_access_token():
            return []
        headers = {"Authorization": "Bearer " + str(self.token)}
        status, body = self._http_request(self.API_HOST, "GET", "/v1/me/tracks?limit=%d" % limit, headers)
        if status == 401 and self.refresh_access_token():
            headers = {"Authorization": "Bearer " + str(self.token)}
            status, body = self._http_request(self.API_HOST, "GET", "/v1/me/tracks?limit=%d" % limit, headers)
        tracks = []
        if status == 200 and body:
            try:
                data = _json.loads(body.decode('utf-8'))
                for entry in data.get("items", []) or []:
                    if not entry or not isinstance(entry, dict): continue
                    tr = entry.get("track") or {}
                    if not tr or not isinstance(tr, dict): continue
                    name = tr.get("name")
                    if not name: continue
                    artists_list = tr.get("artists", []) or []
                    artists = ", ".join(a.get("name", "") for a in artists_list if isinstance(a, dict) and a.get("name"))
                    album_info = tr.get("album") or {}
                    album_name = album_info.get("name", "") if isinstance(album_info, dict) else ""
                    tracks.append({
                        "title": name,
                        "artist": artists or "Unknown Artist",
                        "album": album_name,
                        "duration": int((tr.get("duration_ms", 0) or 0) / 1000),
                        "uri": tr.get("uri", ""),
                        "category": "Liked"
                    })
            except Exception:
                pass
        return tracks

    def get_top_tracks(self, limit=25):
        """Fetch user's Top Tracks / Heavy Rotation from Spotify."""
        if not self.token and not self.refresh_access_token():
            return []
        headers = {"Authorization": "Bearer " + str(self.token)}
        status, body = self._http_request(self.API_HOST, "GET", "/v1/me/top/tracks?limit=%d" % limit, headers)
        if status == 401 and self.refresh_access_token():
            headers = {"Authorization": "Bearer " + str(self.token)}
            status, body = self._http_request(self.API_HOST, "GET", "/v1/me/top/tracks?limit=%d" % limit, headers)
        tracks = []
        if status == 200 and body:
            try:
                data = _json.loads(body.decode('utf-8'))
                for tr in data.get("items", []) or []:
                    if not tr or not isinstance(tr, dict): continue
                    name = tr.get("name")
                    if not name: continue
                    artists_list = tr.get("artists", []) or []
                    artists = ", ".join(a.get("name", "") for a in artists_list if isinstance(a, dict) and a.get("name"))
                    album_info = tr.get("album") or {}
                    album_name = album_info.get("name", "") if isinstance(album_info, dict) else ""
                    tracks.append({
                        "title": name,
                        "artist": artists or "Unknown Artist",
                        "album": album_name,
                        "duration": int((tr.get("duration_ms", 0) or 0) / 1000),
                        "uri": tr.get("uri", ""),
                        "category": "Top"
                    })
            except Exception:
                pass
        return tracks

    def get_recently_played(self, limit=25):
        """Fetch user's Recently Played tracks from Spotify."""
        if not self.token and not self.refresh_access_token():
            return []
        headers = {"Authorization": "Bearer " + str(self.token)}
        status, body = self._http_request(self.API_HOST, "GET", "/v1/me/player/recently-played?limit=%d" % limit, headers)
        if status == 401 and self.refresh_access_token():
            headers = {"Authorization": "Bearer " + str(self.token)}
            status, body = self._http_request(self.API_HOST, "GET", "/v1/me/player/recently-played?limit=%d" % limit, headers)
        tracks = []
        seen = set()
        if status == 200 and body:
            try:
                data = _json.loads(body.decode('utf-8'))
                for entry in data.get("items", []) or []:
                    if not entry or not isinstance(entry, dict): continue
                    tr = entry.get("track") or {}
                    if not tr or not isinstance(tr, dict): continue
                    name = tr.get("name")
                    if not name or name in seen: continue
                    seen.add(name)
                    artists_list = tr.get("artists", []) or []
                    artists = ", ".join(a.get("name", "") for a in artists_list if isinstance(a, dict) and a.get("name"))
                    album_info = tr.get("album") or {}
                    album_name = album_info.get("name", "") if isinstance(album_info, dict) else ""
                    tracks.append({
                        "title": name,
                        "artist": artists or "Unknown Artist",
                        "album": album_name,
                        "duration": int((tr.get("duration_ms", 0) or 0) / 1000),
                        "uri": tr.get("uri", ""),
                        "category": "Recent"
                    })
            except Exception:
                pass
        return tracks

    def get_user_playlists(self, limit=20):
        """Fetch user's Playlists from Spotify."""
        if not self.token and not self.refresh_access_token():
            return []
        headers = {"Authorization": "Bearer " + str(self.token)}
        status, body = self._http_request(self.API_HOST, "GET", "/v1/me/playlists?limit=%d" % limit, headers)
        if status == 401 and self.refresh_access_token():
            headers = {"Authorization": "Bearer " + str(self.token)}
            status, body = self._http_request(self.API_HOST, "GET", "/v1/me/playlists?limit=%d" % limit, headers)
        playlists = []
        if status == 200 and body:
            try:
                data = _json.loads(body.decode('utf-8'))
                for pl in data.get("items", []) or []:
                    if not pl or not isinstance(pl, dict): continue
                    name = pl.get("name")
                    if not name: continue
                    items_info = pl.get("items") or {}
                    tracks_info = pl.get("tracks") or {}
                    t_count = 0
                    if isinstance(items_info, dict) and "total" in items_info:
                        t_count = items_info.get("total", 0)
                    elif isinstance(tracks_info, dict) and "total" in tracks_info:
                        t_count = tracks_info.get("total", 0)
                    elif "total_tracks" in pl:
                        t_count = pl.get("total_tracks", 0)
                    owner_info = pl.get("owner") or {}
                    owner_name = owner_info.get("display_name", "Spotify") if isinstance(owner_info, dict) else "Spotify"
                    playlists.append({
                        "name": name,
                        "id": pl.get("id", ""),
                        "uri": pl.get("uri", ""),
                        "tracks_count": t_count,
                        "owner": owner_name
                    })
            except Exception:
                pass
        return playlists

    def get_playlist_tracks(self, playlist_id, limit=25):
        """Fetch tracks inside a specific user playlist."""
        if not playlist_id:
            return []
        if not self.token and not self.refresh_access_token():
            return []
        headers = {"Authorization": "Bearer " + str(self.token)}
        status, body = self._http_request(self.API_HOST, "GET", "/v1/playlists/%s/tracks?limit=%d" % (playlist_id, limit), headers)
        if status == 401 and self.refresh_access_token():
            headers = {"Authorization": "Bearer " + str(self.token)}
            status, body = self._http_request(self.API_HOST, "GET", "/v1/playlists/%s/tracks?limit=%d" % (playlist_id, limit), headers)
        tracks = []
        if status == 200 and body:
            try:
                data = _json.loads(body.decode('utf-8'))
                for entry in data.get("items", []) or []:
                    if not entry or not isinstance(entry, dict): continue
                    tr = entry.get("track") or {}
                    if not tr or not isinstance(tr, dict): continue
                    name = tr.get("name")
                    if not name: continue
                    artists_list = tr.get("artists", []) or []
                    artists = ", ".join(a.get("name", "") for a in artists_list if isinstance(a, dict) and a.get("name"))
                    album_info = tr.get("album") or {}
                    album_name = album_info.get("name", "") if isinstance(album_info, dict) else ""
                    tracks.append({
                        "title": name,
                        "artist": artists or "Unknown Artist",
                        "album": album_name,
                        "duration": int((tr.get("duration_ms", 0) or 0) / 1000),
                        "uri": tr.get("uri", ""),
                        "category": "Playlist"
                    })
            except Exception:
                pass
        return tracks

    def get_user_tracks(self, limit=20):
        """Convenience method combining Saved, Top, and Recent tracks."""
        saved = self.get_saved_tracks(limit)
        if len(saved) >= limit:
            return saved
        top = self.get_top_tracks(limit - len(saved))
        seen = set(t["title"].lower() for t in saved)
        combined = list(saved)
        for t in top:
            if t["title"].lower() not in seen:
                seen.add(t["title"].lower())
                combined.append(t)
        return combined

    def search_track(self, query):
        """Search Spotify for a track and return metadata dict with uri."""
        if not self.token:
            if not self.refresh_access_token():
                return None
        try:
            import urllib.parse
            q = urllib.parse.quote(str(query))
        except Exception:
            q = str(query).replace(" ", "+")
        headers = {"Authorization": "Bearer " + self.token}
        status, body = self._http_request(self.API_HOST, "GET", "/v1/search?q=" + q + "&type=track&limit=1", headers)
        if status == 401 and self.refresh_access_token():
            headers = {"Authorization": "Bearer " + self.token}
            status, body = self._http_request(self.API_HOST, "GET", "/v1/search?q=" + q + "&type=track&limit=1", headers)
        if status == 200 and body:
            try:
                data = _json.loads(body.decode('utf-8'))
                items = data.get("tracks", {}).get("items", [])
                if items:
                    t = items[0]
                    artists = ", ".join(a.get("name", "") for a in t.get("artists", []))
                    images = (t.get("album") or {}).get("images", [])
                    return {
                        "title": t.get("name"),
                        "artist": artists,
                        "album": (t.get("album") or {}).get("name", ""),
                        "duration_s": (t.get("duration_ms", 0) or 0) / 1000.0,
                        "uri": t.get("uri"),
                        "image_url": images[-1].get("url", "") if images else ""
                    }
            except Exception:
                pass
        return None

    def play_track(self, uri_or_query):
        """Play a specific track on Spotify by URI or search query."""
        if not uri_or_query:
            return self.play()
        if str(uri_or_query).startswith("spotify:track:"):
            return self.play(uris=[str(uri_or_query)])
        res = self.search_track(str(uri_or_query))
        if res and res.get("uri"):
            return self.play(uris=[res["uri"]])
        return self.play()

    def _send_control(self, method, path, body_data=None):
        if not self.token:
            if not self.refresh_access_token():
                return False

        headers = {"Authorization": "Bearer " + self.token}
        if body_data:
            headers["Content-Type"] = "application/json"
        status, _ = self._http_request(self.API_HOST, method, path, headers, body_data=body_data)
        if status == 401:
            if self.refresh_access_token():
                headers = {"Authorization": "Bearer " + self.token}
                if body_data:
                    headers["Content-Type"] = "application/json"
                status, _ = self._http_request(self.API_HOST, method, path, headers, body_data=body_data)
            else:
                self.token = None
                self.refresh_token = None
                clear_credentials()
                return False

        return 200 <= status < 300
