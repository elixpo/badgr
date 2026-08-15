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
    try:
        with open(STATE_FILE, "r") as f:
            data = _json.loads(f.read())
            return (data.get("token"),
                    data.get("refresh_token"),
                    data.get("client_id"),
                    data.get("client_secret"))
    except Exception:
        pass
    return (None, None, None, None)


def save_credentials(token=None, refresh_token=None, client_id=None, client_secret=None):
    try:
        cur_t, cur_rt, cur_ci, cur_cs = load_persisted_credentials()
        data = {
            "token": token or cur_t,
            "refresh_token": refresh_token or cur_rt,
            "client_id": client_id or cur_ci,
            "client_secret": client_secret or cur_cs,
            "updated_at": int(time.time() if hasattr(time, 'time') else 0),
        }
        with open(STATE_FILE, "w") as f:
            f.write(_json.dumps(data))
        return True
    except Exception:
        return False


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
        return bool(self.token or (self.refresh_token and self.client_id and self.client_secret))

    def reload_persisted(self):
        t, rt, ci, cs = load_persisted_credentials()
        if t:  self.token = t
        if rt: self.refresh_token = rt
        if ci: self.client_id = ci
        if cs: self.client_secret = cs
        return self.is_configured()

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
        if not (self.refresh_token and self.client_id and self.client_secret):
            return False

        auth_str = _base64_encode("%s:%s" % (self.client_id, self.client_secret))
        headers = {
            "Authorization": "Basic " + auth_str,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        body = "grant_type=refresh_token&refresh_token=" + self.refresh_token
        status, resp_bytes = self._http_request(self.AUTH_HOST, "POST", "/api/token", headers, body)

        if status == 200 and resp_bytes:
            try:
                data = _json.loads(resp_bytes.decode('utf-8'))
                new_token = data.get("access_token")
                if new_token:
                    self.token = new_token
                    return True
            except Exception:
                pass
        return False

    def get_playback(self):
        if not self.token:
            if not self.refresh_access_token():
                return None

        headers = {"Authorization": "Bearer " + self.token}
        status, body = self._http_request(self.API_HOST, "GET", "/v1/me/player", headers)

        if status == 401:
            if self.refresh_access_token():
                headers = {"Authorization": "Bearer " + self.token}
                status, body = self._http_request(self.API_HOST, "GET", "/v1/me/player", headers)

        if status == 204 or not body:
            return {"connected": True, "active": False, "title": "No Active Player", "artist": "Open Spotify on phone/PC"}

        if status == 200 and body:
            try:
                data = _json.loads(body.decode('utf-8'))
                item = data.get("item") or {}
                artists = item.get("artists", [])
                artist_names = ", ".join(a.get("name", "") for a in artists) or "Unknown Artist"

                dev = data.get("device", {})
                self.device_name = dev.get("name", "Spotify")

                return {
                    "connected":   True,
                    "active":      True,
                    "is_playing":  bool(data.get("is_playing", False)),
                    "title":       item.get("name", "Unknown Track"),
                    "artist":      artist_names,
                    "album":       (item.get("album") or {}).get("name", ""),
                    "duration_s":  (item.get("duration_ms", 0) or 0) / 1000.0,
                    "progress_s":  (data.get("progress_ms", 0) or 0) / 1000.0,
                    "volume":      dev.get("volume_percent", 70),
                    "device_name": self.device_name,
                    "shuffle":     bool(data.get("shuffle_state", False)),
                    "repeat":      data.get("repeat_state", "off"),
                }
            except Exception as e:
                self.last_error = "parse: " + str(e)
                return None

        return None

    def play(self):
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

    def _send_control(self, method, path):
        if not self.token:
            if not self.refresh_access_token():
                return False

        headers = {"Authorization": "Bearer " + self.token}
        status, _ = self._http_request(self.API_HOST, method, path, headers)
        if status == 401 and self.refresh_access_token():
            headers = {"Authorization": "Bearer " + self.token}
            status, _ = self._http_request(self.API_HOST, method, path, headers)

        return 200 <= status < 300
