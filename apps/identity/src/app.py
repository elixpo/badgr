import oreoOS
from oreoOS import api, theme, widgets
from .qr import QRCode

SW = api.SCREEN_W  # 320
SH = api.SCREEN_H  # 240


def _filled_circle(d, cx, cy, r, color):
    for dy in range(-r, r + 1):
        dx = int((r * r - dy * dy) ** 0.5)
        d.rect(cx - dx, cy + dy, dx * 2 + 1, 1, color, fill=True)


def _wrap(text, max_chars):
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
            while len(w) > max_chars:
                out.append(w[:max_chars])
                w = w[max_chars:]
            cur = w
    if cur:
        out.append(cur)
    return out


def _try_avatar():
    try:
        m = __import__("apps.identity.assets.optimized.avatar", None, None,
                       ["DATA", "W", "H"])
        return (bytearray(m.DATA), m.W, m.H)
    except (ImportError, AttributeError):
        return None


def _format_platform_name(raw):
    k = raw.upper().strip()
    for prefix in ("SOCIAL_", "CUSTOM_", "MY_"):
        if k.startswith(prefix):
            k = k[len(prefix):]
    for suffix in ("_USER", "_URL", "_LINK", "_CHANNEL", "_HANDLE", "_ID", "_NAME"):
        if k.endswith(suffix):
            k = k[:-len(suffix)]

    known = {
        "GITHUB":    ("GitHub", "GitHub", "github"),
        "LINKEDIN":  ("LinkedIn", "LinkedIn", "linkedin"),
        "TWITTER":   ("X / Twitter", "Twitter", "twitter"),
        "X":         ("X / Twitter", "Twitter", "x"),
        "BLUESKY":   ("Bluesky", "Bluesky", "bluesky"),
        "BSKY":      ("Bluesky", "Bluesky", "bsky"),
        "NPM":       ("NPM", "NPM", "npm"),
        "WEBSITE":   ("Website", "Website", "website"),
        "PORTFOLIO": ("Portfolio", "Portfolio", "portfolio"),
        "BLOG":      ("Blog", "Blog", "blog"),
        "EMAIL":     ("Email", "Email", "email"),
        "DEVTO":     ("Dev.to", "Dev.to", "devto"),
        "YOUTUBE":   ("YouTube", "YouTube", "youtube"),
        "DISCORD":   ("Discord", "Discord", "discord"),
        "TELEGRAM":  ("Telegram", "Telegram", "telegram"),
        "INSTAGRAM": ("Instagram", "Instagram", "instagram"),
        "TIKTOK":    ("TikTok", "TikTok", "tiktok"),
        "MASTODON":  ("Mastodon", "Mastodon", "mastodon"),
        "REDDIT":    ("Reddit", "Reddit", "reddit"),
        "SUBSTACK":  ("Substack", "Substack", "substack"),
        "TWITCH":    ("Twitch", "Twitch", "twitch"),
    }
    if k in known:
        return known[k]

    words = [w.capitalize() for w in k.replace("_", " ").replace("-", " ").split()]
    name = " ".join(words) or "Link"
    tab = name if len(name) <= 10 else name[:9] + "…"
    return name, tab, k.lower()


def _format_url(stem, val):
    val = str(val).strip()
    if val.startswith(("http://", "https://", "mailto:")):
        return val
    if "@" in val and "." in val and "/" not in val:
        return "mailto:" + val

    known_urls = {
        "github":    "https://github.com/",
        "linkedin":  "https://linkedin.com/in/",
        "twitter":   "https://x.com/",
        "x":         "https://x.com/",
        "bluesky":   "https://bsky.app/profile/",
        "bsky":      "https://bsky.app/profile/",
        "npm":       "https://npmjs.com/~",
        "instagram": "https://instagram.com/",
        "youtube":   "https://youtube.com/@",
        "telegram":  "https://t.me/",
        "reddit":    "https://reddit.com/u/",
        "twitch":    "https://twitch.tv/",
    }
    if stem in known_urls:
        return known_urls[stem] + val
    return "https://" + val


def _load_identity(os_obj=None):
    from oreoOS import config

    name    = config.get("DISPLAY_NAME") or config.get("GITHUB_USER", "")
    gh_user = config.get("GITHUB_USER", "")
    desig   = config.get("DESIGNATION", "")

    # Priority order for standard curated channels
    standard_order = [
        "GITHUB_USER", "LINKEDIN_USER", "TWITTER_USER", "BLUESKY_USER",
        "NPM_USER", "WEBSITE_URL", "EMAIL"
    ]
    seen_keys = set()
    channels = []

    # 1. Process standard keys first in clean curated order
    for k in standard_order:
        val = config.get(k)
        if val:
            seen_keys.add(k)
            c_name, c_tab, c_stem = _format_platform_name(k)
            c_url = _format_url(c_stem, val)
            channels.append({"name": c_name, "tab": c_tab, "url": c_url})

    # 2. Dynamically process any extra custom keys defined in .env
    env_dict = getattr(config, "_env", {})
    for k, val in env_dict.items():
        if k in seen_keys or not val:
            continue
        # Skip system / non-social keys
        if k in ("DISPLAY_NAME", "DESIGNATION", "OWM_API_KEY", "GH_TOKEN",
                 "WEATHER_LAT", "WEATHER_LON", "WEATHER_NAME", "TIMEZONE_OFFSET",
                 "DEBUG", "WIFI_SSID", "WIFI_PASSWORD", "WIFI_AUTO_CONNECT", "VERSION", "RELEASE_DATE"):
            continue
        c_name, c_tab, c_stem = _format_platform_name(k)
        c_url = _format_url(c_stem, val)
        channels.append({"name": c_name, "tab": c_tab, "url": c_url})

    if not channels:
        channels.append({"name": "Website", "tab": "Website", "url": "https://oreo.elixpo.com"})

    return {
        "name":        name or "Badge Holder",
        "login":       gh_user,
        "designation": desig,
        "channels":    channels
    }


class App(oreoOS.App):
    name         = "Identity"
    SHOW_LOADING = False

    def __init__(self):
        self._os          = None
        self._avatar      = None
        self._identity    = None
        self._mode        = "card"   # "card" or "qr"
        self._channel_idx = 0
        self._qr_cache    = {}       # url -> matrix cache
        self._dirty       = True

    def on_enter(self, os_obj):
        self._os          = os_obj
        self._avatar      = _try_avatar()
        self._identity    = _load_identity(os_obj)
        self._mode        = "card"
        self._channel_idx = 0
        self._dirty       = True

    def _get_active_channel(self):
        chans = self._identity.get("channels", [])
        if 0 <= self._channel_idx < len(chans):
            return chans[self._channel_idx]
        return chans[0] if chans else {"name": "Website", "tab": "Website", "url": "https://oreo.elixpo.com"}

    def _get_qr_matrix(self, url):
        if url not in self._qr_cache:
            try:
                self._qr_cache[url] = QRCode.encode(url)
            except Exception as e:
                print("[Identity] QR Encode error:", e)
                self._qr_cache[url] = [[False]*21 for _ in range(21)]
        return self._qr_cache[url]

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
                if self._os:
                    self._os.quit()
        elif self._mode == "qr":
            chans = self._identity.get("channels", [])
            # A toggles back to card mode
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
        widgets.draw_header(d, "IDENTITY")
        widgets.draw_hint(d, "A=toggle QR  HOME=back")

        p = self._identity
        cx, cy = 12, widgets.HEADER_H + 4
        cw     = SW - 24
        ch     = SH - widgets.HEADER_H - widgets.HINT_H - 8

        d.rect(cx + 2, cy + 2, cw, ch, theme.MUTED2, fill=True)
        d.rect(cx,     cy,     cw, ch, theme.CARD,   fill=True)
        d.rect(cx,     cy,     cw, 3,  theme.PRIMARY, fill=True)

        if self._avatar:
            data, aw, ah = self._avatar
        else:
            data, aw, ah = None, 72, 72
        av_sz = max(aw, ah)

        # 1. Centered circular avatar with pink outer ring
        av_cx = SW // 2
        av_cy = cy + 12 + av_sz // 2

        _filled_circle(d, av_cx, av_cy, av_sz // 2 + 3, theme.PRIMARY)
        if data:
            d.blit(data, av_cx - aw // 2, av_cy - ah // 2, aw, ah)
        else:
            _filled_circle(d, av_cx, av_cy, av_sz // 2, theme.CARD)
            letter = (p["login"] or p["name"] or "?")[:1].upper()
            d.text(letter, av_cx - 12, av_cy - 12, theme.PRIMARY, scale=3)

        # 2. Display Name (centered below avatar)
        curr_y = av_cy + av_sz // 2 + 10
        name_line = p["name"][:18]
        lw = len(name_line) * 16
        d.text(name_line, (SW - lw) // 2, curr_y, theme.PRIMARY, scale=2)
        curr_y += 22

        # 3. GitHub @login handle
        if p["login"]:
            log_line = "@" + p["login"]
            lw = len(log_line) * 8
            d.text(log_line, (SW - lw) // 2, curr_y, theme.TEAL)
            curr_y += 12

        # 4. Designation / Bio
        if p["designation"]:
            desig = p["designation"][:32]
            lw = len(desig) * 8
            d.text(desig, (SW - lw) // 2, curr_y + 2, theme.GOLD)
            curr_y += 14

        # 5. Bottom "View QR Cards" Action Pill
        btn_w = 170
        btn_h = 16
        btn_x = (SW - btn_w) // 2
        btn_y = cy + ch - 22
        d.rect(btn_x, btn_y, btn_w, btn_h, theme.PRIMARY, fill=True)
        d.rect(btn_x, btn_y, btn_w, btn_h, theme.GOLD, fill=False)
        lbl = "A: Toggle QR Mode >"
        d.text(lbl, btn_x + (btn_w - len(lbl) * 8) // 2, btn_y + 4, api.WHITE)

    def _draw_qr(self, d):
        widgets.draw_header(d, "SOCIAL QR CARD")
        widgets.draw_hint(d, "A=card  LEFT/RIGHT=channel")

        chan = self._get_active_channel()
        url  = chan["url"]

        cx, cy = 12, widgets.HEADER_H + 4
        cw     = SW - 24
        ch     = SH - widgets.HEADER_H - widgets.HINT_H - 8

        d.rect(cx + 2, cy + 2, cw, ch, theme.MUTED2, fill=True)
        d.rect(cx,     cy,     cw, ch, theme.CARD,   fill=True)
        d.rect(cx,     cy,     cw, 3,  theme.PRIMARY, fill=True)

        # 1. Top Channel Switcher Bar with high-contrast PRIMARY fill
        chans = self._identity.get("channels", [])
        n = len(chans)
        bar_y = cy + 6
        bar_h = 18
        bar_w = cw - 16
        bar_x = cx + 8

        d.rect(bar_x, bar_y, bar_w, bar_h, theme.PRIMARY, fill=True)
        d.rect(bar_x, bar_y, bar_w, bar_h, theme.GOLD, fill=False)

        # Left arrow
        d.text("<", bar_x + 8, bar_y + 5, api.WHITE)

        # Centered active channel name in crisp high-contrast white
        act_name = chan.get("name", "Channel")
        d.text(act_name, bar_x + (bar_w - len(act_name) * 8) // 2, bar_y + 5, api.WHITE)

        # Counter on right side
        tag = "%d/%d" % (self._channel_idx + 1, n)
        d.text(tag, bar_x + bar_w - len(tag) * 8 - 20, bar_y + 5, api.WHITE)

        # Right arrow
        d.text(">", bar_x + bar_w - 14, bar_y + 5, api.WHITE)

        # Horizontal scroll bar indicator track & slider thumb
        track_y = bar_y + bar_h + 2
        track_h = 3
        d.rect(bar_x, track_y, bar_w, track_h, theme.BG, fill=True)
        d.rect(bar_x, track_y, bar_w, track_h, theme.MUTED2, fill=False)
        if n > 0:
            thumb_w = max(24, bar_w // n)
            thumb_x = bar_x + (bar_w - thumb_w) * self._channel_idx // max(1, n - 1)
            d.rect(thumb_x, track_y, thumb_w, track_h, theme.PRIMARY, fill=True)

        # 2. QR Container Box — tightly hugs the QR code so it fills the square!
        qr_matrix = self._get_qr_matrix(url)
        q_size    = len(qr_matrix)
        mod_sz    = 4 if q_size <= 29 else max(2, min(4, 116 // q_size))
        qr_pixel_w = q_size * mod_sz
        pad       = 4

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

        # 3. Configurable Encoded URL Text Field below QR Code
        field_y = cy + ch - 22
        field_w = cw - 16
        field_x = cx + 8
        field_h = 18
        d.rect(field_x, field_y, field_w, field_h, theme.BG, fill=True)
        d.rect(field_x, field_y, field_w, field_h, theme.GOLD, fill=False)

        # Strip protocol for clean display inside text box
        display_url = url.replace("https://", "").replace("http://", "")
        if len(display_url) > 33:
            display_url = display_url[:30] + "..."

        d.text(display_url, field_x + (field_w - len(display_url) * 8) // 2, field_y + 5, theme.TEXT_BRIGHT)

    def on_exit(self):
        """Free QR cache and sweep GC on exit."""
        self._qr_cache = {}
        try:
            import gc
            gc.collect()
        except Exception:
            pass
