"""Unified Badge — Digital Identity & Networking Card.

Combines the high-visibility conference badge UI with WiFi-fetched GitHub stats
and a robust QR-code networking engine.
"""

import oreoOS
from oreoOS import api, theme, widgets
from oreoOS.qr import QRCode

SW = api.SCREEN_W
SH = api.SCREEN_H

# ── Network Fetching ────────────────────────────────────────────────────────


def _fetch_profile(username):
    try:
        try:
            import urequests as _req
        except ImportError:
            import requests as _req
        r = _req.get(
            "https://api.github.com/users/" + username, headers={"User-Agent": "OreoBadge"}
        )
        try:
            if r.status_code != 200:
                return None
            data = r.json()
            return {
                "name": data.get("name") or data.get("login") or username,
                "login": data.get("login", username),
                "bio": (data.get("bio") or "")[:60],
                "location": (data.get("location") or "")[:24],
                "followers": data.get("followers", 0),
                "following": data.get("following", 0),
                "repos": data.get("public_repos", 0),
            }
        finally:
            r.close()
    except Exception:
        return None


# ── Utilities ───────────────────────────────────────────────────────────────


def _filled_circle(d, cx, cy, r, color):
    """Approximate filled circle by horizontal scan-lines."""
    for dy in range(-r, r + 1):
        dx = int((r * r - dy * dy) ** 0.5)
        d.rect(cx - dx, cy + dy, dx * 2 + 1, 1, color, fill=True)


def _wrap(text, max_chars):
    """Word-wrap helper — splits at spaces, hard-breaks oversized words."""
    if not text:
        return [""]
    out, cur = [], ""
    for w in text.split():
        cand = (cur + " " + w).strip()
        if len(cand) <= max_chars:
            cur = cand
        else:
            if cur:
                out.append(cur)
                cur = ""
            if len(w) > max_chars:
                while len(w) > max_chars:
                    out.append(w[:max_chars])
                    w = w[max_chars:]
            cur = w
    if cur:
        out.append(cur)
    return out


def _try_avatar():
    """Load the pre-fetched avatar baked at deploy time, or None."""
    try:
        m = __import__("apps.badge.assets.optimized.avatar", None, None, ["DATA", "W", "H"])
        return (bytearray(m.DATA), m.W, m.H)
    except (ImportError, AttributeError):
        # Fallback to check identity path in case it hasn't been re-deployed
        try:
            m = __import__("apps.identity.assets.optimized.avatar", None, None, ["DATA", "W", "H"])
            return (bytearray(m.DATA), m.W, m.H)
        except (ImportError, AttributeError):
            return None


STANDARD_LINKS = [
    ("GITHUB_USER", "GitHub", "https://github.com/%s"),
    ("TWITTER_USER", "X / Twitter", "https://x.com/%s"),
    ("LINKEDIN_USER", "LinkedIn", "https://linkedin.com/in/%s"),
    ("BLUESKY_USER", "Bluesky", "https://bsky.app/profile/%s"),
    ("NPM_USER", "NPM", "https://npmjs.com/~%s"),
    ("WEBSITE_URL", "Website", "%s"),
    ("EMAIL", "Email", "mailto:%s"),
]


def _format_url(val):
    val = str(val).strip()
    if val.startswith(("http://", "https://", "mailto:")):
        return val
    if "@" in val and "." in val and "/" not in val:
        return "mailto:" + val
    return "https://" + val.lstrip("/")


def _load_identity(os_obj=None):
    from oreoOS import config

    gh_user = config.identity.GITHUB
    name = config.identity.DISPLAY_NAME or gh_user or "Badge Holder"
    desig = config.identity.DESIGNATION

    channels = []
    seen = set()

    for key, label, tmpl in STANDARD_LINKS:
        val = config.get_str(key)
        if not val:
            continue
        val_clean = val.lstrip("@")
        url = val if val.startswith(("http://", "https://", "mailto:")) else (tmpl % val_clean)
        channels.append({"name": label, "url": _format_url(url)})
        seen.add(label.lower())

    for link in config.get_custom_links():
        label = link["name"]
        if label.lower() not in seen:
            channels.append({"name": label, "url": _format_url(link["url"])})
            seen.add(label.lower())

    if not channels:
        channels.append({"name": "Website", "url": "https://oreo.elixpo.com"})

    return {"name": name, "login": gh_user, "designation": desig, "channels": channels}


# ── App Main ────────────────────────────────────────────────────────────────


class App(oreoOS.App):
    name = "Badge"
    SHOW_LOADING = False

    try:
        from oreoOS.config import get_state_path

        CACHE_PATH = get_state_path("cache/badge_cache.txt")
    except Exception:
        CACHE_PATH = "badge_data/cache/badge_cache.txt"
    CACHE_TTL = 3600  # 1 hour

    def __init__(self):
        self._os = None
        self._avatar = None
        self._identity = None
        self._stats = None
        self._mode = "card"  # "card" or "qr"
        self._channel_idx = 0
        self._qr_cache = {}
        self._dirty = True

    def on_enter(self, os_obj):
        self._os = os_obj
        self._avatar = _try_avatar()
        self._identity = _load_identity(os_obj)
        self._mode = "card"
        self._channel_idx = 0

        # Load GitHub Stats from cache
        cached, age = self._load_cache()
        self._stats = cached

        if self._identity["login"]:
            if cached is None or (age is not None and age > self.CACHE_TTL):
                fresh = _fetch_profile(self._identity["login"])
                if fresh:
                    self._stats = fresh
                    self._save_cache(fresh)

        self._dirty = True

    def _get_active_channel(self):
        chans = self._identity.get("channels", [])
        if 0 <= self._channel_idx < len(chans):
            return chans[self._channel_idx]
        return (
            chans[0]
            if chans
            else {"name": "Website", "tab": "Website", "url": "https://oreo.elixpo.com"}
        )

    def _get_qr_matrix(self, url):
        if url not in self._qr_cache:
            try:
                self._qr_cache[url] = QRCode.encode(url)
            except Exception as e:
                print("[Badge] QR Encode error:", e)
                self._qr_cache[url] = [[False] * 21 for _ in range(21)]
        return self._qr_cache[url]

    # ── Cache Helpers ───────────────────────────────────────────────────────
    def _load_cache(self):
        try:
            from oreoOS import cache

            payload, age = cache.load(self.CACHE_PATH)
        except Exception:
            return None, None
        if not payload:
            return None, None
        try:
            return {
                "followers": int(payload.get("followers", 0)),
                "following": int(payload.get("following", 0)),
                "repos": int(payload.get("repos", 0)),
            }, age
        except Exception:
            return None, None

    def _save_cache(self, profile):
        try:
            from oreoOS import cache

            cache.save(self.CACHE_PATH, profile)
        except Exception:
            pass

    # ── Input Handling ──────────────────────────────────────────────────────
    def on_button_press(self, btn):
        if btn == api.BTN_HOME:
            if self._mode == "qr":
                self._mode = "card"
                self._dirty = True
            else:
                if self._os:
                    self._os.quit()
            return

        if self._mode == "card":
            if btn == api.BTN_A:
                self._mode = "qr"
                self._dirty = True
            elif btn == api.BTN_B:
                # Manual GitHub stats refresh
                if self._identity["login"]:
                    new = _fetch_profile(self._identity["login"])
                    if new:
                        self._stats = new
                        self._save_cache(new)
                    self._dirty = True
        elif self._mode == "qr":
            chans = self._identity.get("channels", [])
            # A or B toggles back to card mode
            if btn in (api.BTN_A, api.BTN_B):
                self._mode = "card"
                self._dirty = True
            # Left / Right arrows cycle through QR channels
            elif btn in (api.BTN_LEFT, api.BTN_UP):
                if chans:
                    self._channel_idx = (self._channel_idx - 1) % len(chans)
                    self._dirty = True
            elif btn in (api.BTN_RIGHT, api.BTN_DOWN):
                if chans:
                    self._channel_idx = (self._channel_idx + 1) % len(chans)
                    self._dirty = True

    def update(self, dt):
        pass

    # ── Rendering ───────────────────────────────────────────────────────────
    def draw(self, d):
        if not self._dirty:
            return

        d.clear(theme.BG)
        if self._mode == "card":
            self._draw_card(d)
        elif self._mode == "qr":
            self._draw_qr(d)

        self._dirty = False

    def _draw_card(self, d):
        self.title = "BADGE"
        self.hints = [("A", "QR Code"), ("B", "Refresh"), ("HOME", "Back")]

        p = self._identity
        cx, cy = 8, widgets.HEADER_H + 4
        cw = SW - 16
        ch = SH - widgets.HEADER_H - widgets.HINT_H - 8

        # Base Card
        d.rect(cx + 2, cy + 2, cw, ch, theme.MUTED2, fill=True)
        d.rect(cx, cy, cw, ch, theme.CARD, fill=True)
        d.rect(cx, cy, cw, 4, theme.PRIMARY, fill=True)

        if self._avatar:
            data, aw, ah = self._avatar
        else:
            data, aw, ah = None, 64, 64
        av_sz = max(aw, ah)

        # 1. Prominent Avatar
        av_cx = SW // 2
        av_cy = cy + 6 + av_sz // 2

        _filled_circle(d, av_cx, av_cy, av_sz // 2 + 4, theme.PRIMARY)
        if data:
            d.blit(data, av_cx - aw // 2, av_cy - ah // 2, aw, ah)
        else:
            _filled_circle(d, av_cx, av_cy, av_sz // 2, theme.CARD)
            letter = (p["login"] or p["name"] or "?")[:1].upper()
            d.text(letter, av_cx - 12, av_cy - 12, theme.PRIMARY, scale=3)

        # 2. Maximum Visibility Name (Scale 3)
        curr_y = av_cy + av_sz // 2 + 8
        name_line = p["name"]

        # Determine scale based on length to ensure it fits horizontally
        scale = 3
        max_chars = 12
        if len(name_line) > 12:
            scale = 2
            max_chars = 18

        name_wrapped = _wrap(name_line, max_chars)[:2]
        for line in name_wrapped:
            lw = len(line) * (8 * scale)
            d.text(line, (SW - lw) // 2, curr_y, theme.TEXT_BRIGHT, scale=scale)
            curr_y += (10 * scale) + 4

        curr_y += 2

        # 3. GitHub @login handle
        if p["login"]:
            log_line = "@" + p["login"]
            lw = len(log_line) * 8
            d.text(log_line, (SW - lw) // 2, curr_y, theme.TEAL)
            curr_y += 14

        # 4. Designation / Affiliation (High Contrast Gold)
        if p["designation"]:
            desig_wrapped = _wrap(p["designation"], 18)[:2]
            for ln in desig_wrapped:
                lw = len(ln) * 16
                d.text(ln, (SW - lw) // 2, curr_y, theme.GOLD, scale=2)
                curr_y += 20
            curr_y += 4

        # 4. GitHub Stats / Network Pill
        if self._stats:
            stats_y = cy + ch - 30
            col_w = cw // 3
            for i, (lbl, val) in enumerate(
                [
                    ("repos", self._stats["repos"]),
                    ("followers", self._stats["followers"]),
                    ("following", self._stats.get("following", 0)),
                ]
            ):
                mx = cx + col_w * i + col_w // 2
                num = str(val)
                d.text(num, mx - len(num) * 8, stats_y, theme.PRIMARY, scale=2)
                d.text(lbl, mx - len(lbl) * 4, stats_y + 20, theme.MUTED)
        else:
            # Clean fallback if no stats available
            btn_w = 170
            btn_h = 16
            btn_x = (SW - btn_w) // 2
            btn_y = cy + ch - 22
            d.rect(btn_x, btn_y, btn_w, btn_h, theme.PRIMARY, fill=True)
            d.rect(btn_x, btn_y, btn_w, btn_h, theme.GOLD, fill=False)
            lbl = "A: Toggle QR Mode >"
            d.text(lbl, btn_x + (btn_w - len(lbl) * 8) // 2, btn_y + 4, api.WHITE)

    def _draw_qr(self, d):
        self.title = "NETWORKING QR"
        self.hints = [("A", "Back"), ("LEFT/RIGHT", "Channel")]

        chan = self._get_active_channel()
        url = chan["url"]

        cx, cy = 12, widgets.HEADER_H + 4
        cw = SW - 24
        ch = SH - widgets.HEADER_H - widgets.HINT_H - 8

        d.rect(cx + 2, cy + 2, cw, ch, theme.MUTED2, fill=True)
        d.rect(cx, cy, cw, ch, theme.CARD, fill=True)
        d.rect(cx, cy, cw, 3, theme.PRIMARY, fill=True)

        # 1. Top Channel Switcher Bar
        chans = self._identity.get("channels", [])
        n = len(chans)
        bar_y = cy + 6
        bar_h = 18
        bar_w = cw - 16
        bar_x = cx + 8

        d.rect(bar_x, bar_y, bar_w, bar_h, theme.PRIMARY, fill=True)
        d.rect(bar_x, bar_y, bar_w, bar_h, theme.GOLD, fill=False)

        d.text("<", bar_x + 8, bar_y + 5, api.WHITE)
        act_name = chan.get("name", "Channel")
        d.text(act_name, bar_x + (bar_w - len(act_name) * 8) // 2, bar_y + 5, api.WHITE)
        tag = "%d/%d" % (self._channel_idx + 1, n)
        d.text(tag, bar_x + bar_w - len(tag) * 8 - 20, bar_y + 5, api.WHITE)
        d.text(">", bar_x + bar_w - 14, bar_y + 5, api.WHITE)

        widgets.draw_scrollbar(
            d, bar_x, bar_y + bar_h + 2, bar_w, 3, n, self._channel_idx, visible=1, horizontal=True
        )

        # 2. QR Container Box
        qr_matrix = self._get_qr_matrix(url)
        q_size = len(qr_matrix)
        mod_sz = 4 if q_size <= 29 else max(2, min(4, 116 // q_size))
        qr_pixel_w = q_size * mod_sz
        pad = 4

        box_w = qr_pixel_w + pad * 2
        box_h = box_w
        box_x = (SW - box_w) // 2
        box_y = cy + 32 + (118 - box_h) // 2

        d.rect(box_x + 1, box_y + 1, box_w, box_h, theme.MUTED2, fill=True)
        d.rect(box_x, box_y, box_w, box_h, api.WHITE, fill=True)
        d.rect(box_x, box_y, box_w, box_h, theme.MUTED2, fill=False)

        start_x = box_x + pad
        start_y = box_y + pad

        for r in range(q_size):
            for col in range(q_size):
                if qr_matrix[r][col]:
                    mx = start_x + col * mod_sz
                    my = start_y + r * mod_sz
                    d.rect(mx, my, mod_sz, mod_sz, api.BLACK, fill=True)

        # 3. Configurable Encoded URL Text Field
        field_y = cy + ch - 22
        field_w = cw - 16
        field_x = cx + 8
        field_h = 18
        d.rect(field_x, field_y, field_w, field_h, theme.BG, fill=True)
        d.rect(field_x, field_y, field_w, field_h, theme.GOLD, fill=False)

        display_url = url.replace("https://", "").replace("http://", "")
        if len(display_url) > 33:
            display_url = display_url[:30] + "..."

        d.text(
            display_url,
            field_x + (field_w - len(display_url) * 8) // 2,
            field_y + 5,
            theme.TEXT_BRIGHT,
        )

    def on_exit(self):
        """Free memory on exit."""
        self._qr_cache = {}
        try:
            import gc

            gc.collect()
        except Exception:
            pass
