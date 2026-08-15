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
            if btn in (api.BTN_A, api.BTN_RIGHT, api.BTN_DOWN):
                self._mode = "qr"
                self._dirty = True
        elif self._mode == "qr":
            chans = self._identity.get("channels", [])
            if not chans:
                return
            if btn in (api.BTN_LEFT, api.BTN_UP):
                self._channel_idx = (self._channel_idx - 1) % len(chans)
                self._dirty = True
            elif btn in (api.BTN_RIGHT, api.BTN_DOWN, api.BTN_A):
                self._channel_idx = (self._channel_idx + 1) % len(chans)
                self._dirty = True
            elif btn == api.BTN_B:
                self._mode = "card"
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
        widgets.draw_hint(d, "A=show QR  HOME=back")

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

        PAD  = 12
        RING = 3

        desig_row_h = 0
        if p["designation"]:
            desig = p["designation"][:32]
            avail = cw - 16
            dw    = len(desig) * 16
            if dw > avail:
                desig_row_h = 18 + 2 * 22 + 4
            else:
                desig_row_h = 18 + 22 + 4

        block_h = (av_sz + RING * 2) + desig_row_h
        block_y = cy + max(PAD, (ch - block_h) // 2)

        av_x  = cx + PAD
        av_y  = block_y
        av_cx = av_x + av_sz // 2
        av_cy = av_y + av_sz // 2

        _filled_circle(d, av_cx, av_cy, av_sz // 2 + RING, theme.PRIMARY)
        if data:
            d.blit(data, av_cx - aw // 2, av_cy - ah // 2, aw, ah)
        else:
            _filled_circle(d, av_cx, av_cy, av_sz // 2, theme.CARD)
            letter = (p["login"] or p["name"] or "?")[:1].upper()
            d.text(letter, av_cx - 16, av_cy - 16, theme.PRIMARY, scale=4)

        name_x     = av_x + av_sz + RING + PAD
        name_avail = cx + cw - name_x - PAD
        max_chars  = max(4, name_avail // 16)
        name_lines = _wrap(p["name"], max_chars)[:3]

        block_h = len(name_lines) * 22 - 4
        name_y  = av_cy - block_h // 2
        for i, line in enumerate(name_lines):
            d.text(line, name_x, name_y + i * 22, theme.PRIMARY, scale=2)

        block_bot = max(av_y + av_sz + RING, name_y + block_h)
        desig     = p["designation"][:32]
        if desig:
            dy    = block_bot + 14
            dw    = len(desig) * 16
            avail = cw - 16
            if dw > avail:
                wrapped = _wrap(desig, max(6, avail // 16))[:2]
                for i, ln in enumerate(wrapped):
                    lw = len(ln) * 16
                    d.text(ln, (SW - lw) // 2, dy + i * 22, theme.GOLD, scale=2)
                dy += len(wrapped) * 22
            else:
                d.text(desig, (SW - dw) // 2, dy, theme.GOLD, scale=2)
                dy += 22

            uw = min(120, cw - 60)
            d.rect((SW - uw) // 2, dy + 2, uw, 2, theme.GOLD, fill=True)

    def _draw_qr(self, d):
        widgets.draw_header(d, "SOCIAL QR CARD")
        widgets.draw_hint(d, "D-PAD=switch  B=card  HOME=back")

        chan = self._get_active_channel()
        url  = chan["url"]

        cx, cy = 12, widgets.HEADER_H + 4
        cw     = SW - 24
        ch     = SH - widgets.HEADER_H - widgets.HINT_H - 8

        d.rect(cx + 2, cy + 2, cw, ch, theme.MUTED2, fill=True)
        d.rect(cx,     cy,     cw, ch, theme.CARD,   fill=True)
        d.rect(cx,     cy,     cw, 3,  theme.PRIMARY, fill=True)

        # Top Channel Carousel Switcher Bar
        chans = self._identity.get("channels", [])
        n = len(chans)
        bar_y = cy + 6
        bar_h = 18

        if n <= 3:
            tab_w = (cw - 8) // max(1, n)
            for idx, c in enumerate(chans):
                tx = cx + 4 + idx * tab_w
                is_active = (idx == self._channel_idx)
                t_bg = theme.PRIMARY if is_active else theme.CARD
                t_fg = api.WHITE if is_active else theme.TEXT_DIM

                d.rect(tx, bar_y, tab_w - 4, bar_h, t_bg, fill=True)
                if is_active:
                    d.rect(tx, bar_y, tab_w - 4, bar_h, theme.GOLD, fill=False)
                t_lbl = c.get("tab", c["name"])[:10]
                d.text(t_lbl, tx + (tab_w - 4 - len(t_lbl) * 8) // 2, bar_y + 5, t_fg)
        else:
            prev_idx = (self._channel_idx - 1) % n
            next_idx = (self._channel_idx + 1) % n

            tag = "%d/%d" % (self._channel_idx + 1, n)
            tag_w = len(tag) * 8
            d.text(tag, cx + cw - tag_w - 6, bar_y + 5, theme.TEXT_DIM)

            d.text("<", cx + 6, bar_y + 5, theme.GOLD)

            start_x = cx + 18
            avail_w = (cx + cw - tag_w - 14) - start_x

            w_prev = max(44, min(62, len(chans[prev_idx]["tab"]) * 8 + 10))
            w_next = max(44, min(62, len(chans[next_idx]["tab"]) * 8 + 10))
            w_act  = min(116, avail_w - w_prev - w_next - 10)

            x_prev = start_x
            x_act  = x_prev + w_prev + 5
            x_next = x_act + w_act + 5

            # Prev Tab Pill
            d.rect(x_prev, bar_y, w_prev, bar_h, theme.CARD, fill=True)
            d.rect(x_prev, bar_y, w_prev, bar_h, theme.MUTED2, fill=False)
            p_lbl = chans[prev_idx]["tab"][:6]
            d.text(p_lbl, x_prev + (w_prev - len(p_lbl) * 8) // 2, bar_y + 5, theme.TEXT_DIM)

            # Active Tab Pill (Highlighted + Gold Border)
            d.rect(x_act, bar_y, w_act, bar_h, theme.PRIMARY, fill=True)
            d.rect(x_act, bar_y, w_act, bar_h, theme.GOLD, fill=False)
            a_lbl = chans[self._channel_idx]["tab"][:12]
            d.text(a_lbl, x_act + (w_act - len(a_lbl) * 8) // 2, bar_y + 5, api.WHITE)

            # Next Tab Pill
            d.rect(x_next, bar_y, w_next, bar_h, theme.CARD, fill=True)
            d.rect(x_next, bar_y, w_next, bar_h, theme.MUTED2, fill=False)
            n_lbl = chans[next_idx]["tab"][:6]
            d.text(n_lbl, x_next + (w_next - len(n_lbl) * 8) // 2, bar_y + 5, theme.TEXT_DIM)

            # Right arrow
            d.text(">", x_next + w_next + 4, bar_y + 5, theme.GOLD)

        # FIXED, IMMUTABLE QR Container Box dimensions (116x116px)
        box_w = 116
        box_h = 116
        box_x = (SW - box_w) // 2
        box_y = cy + 28

        d.rect(box_x - 1, box_y - 1, box_w + 2, box_h + 2, theme.MUTED2, fill=True)
        d.rect(box_x, box_y, box_w, box_h, api.WHITE, fill=True)

        # Render QR Code centered inside the fixed box
        qr_matrix = self._get_qr_matrix(url)
        q_size    = len(qr_matrix)
        mod_sz    = max(2, min(4, (box_w - 12) // q_size))
        qr_pixel_w = q_size * mod_sz

        start_x = box_x + (box_w - qr_pixel_w) // 2
        start_y = box_y + (box_h - qr_pixel_w) // 2

        for r in range(q_size):
            for col in range(q_size):
                if qr_matrix[r][col]:
                    mx = start_x + col * mod_sz
                    my = start_y + r * mod_sz
                    d.rect(mx, my, mod_sz, mod_sz, api.BLACK, fill=True)

        # Configurable Encoded URL Text Field below QR Code
        field_y = box_y + box_h + 6
        field_w = cw - 16
        field_x = cx + 8
        d.rect(field_x, field_y, field_w, 20, theme.BG, fill=True)
        d.rect(field_x, field_y, field_w, 20, theme.GOLD, fill=False)

        # Strip protocol for clean display inside text box
        display_url = url.replace("https://", "").replace("http://", "")
        if len(display_url) > 33:
            display_url = display_url[:30] + "..."

        d.text(display_url, field_x + (field_w - len(display_url) * 8) // 2, field_y + 6, theme.TEXT_BRIGHT)
