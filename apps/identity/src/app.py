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


def _load_identity(os_obj=None):
    try:
        import secrets as _sec
    except Exception:
        _sec = None

    try:
        from oreoOS import config as _cfg
    except Exception:
        _cfg = None

    def _get_val(key, default=""):
        if _sec and hasattr(_sec, key):
            val = getattr(_sec, key)
            if val: return str(val).strip()
        if _cfg and hasattr(_cfg, key):
            val = getattr(_cfg, key)
            if val: return str(val).strip()
        if os_obj and hasattr(os_obj, "settings_get"):
            try:
                val = os_obj.settings_get(key.lower(), "")
                if val: return str(val).strip()
            except Exception:
                pass
        return default

    gh_user = _get_val("GITHUB_USER")
    name    = _get_val("DISPLAY_NAME") or gh_user
    desig   = _get_val("DESIGNATION")
    li_user = _get_val("LINKEDIN_USER")
    tw_user = _get_val("TWITTER_USER")
    web_url = _get_val("WEBSITE_URL")

    channels = []
    if gh_user:
        channels.append({"name": "GitHub", "tab": "GitHub", "url": "https://github.com/" + gh_user})
    if li_user:
        channels.append({"name": "LinkedIn", "tab": "LinkedIn", "url": "https://linkedin.com/in/" + li_user})
    if tw_user:
        channels.append({"name": "X / Twitter", "tab": "Twitter", "url": "https://x.com/" + tw_user})
    if web_url:
        url_fmt = web_url if web_url.startswith(("http://", "https://")) else ("https://" + web_url)
        channels.append({"name": "Website", "tab": "Website", "url": url_fmt})

    if not channels:
        fallback_name = name or "Oreo"
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

        # Top Channel Switcher Bar
        chans = self._identity.get("channels", [])
        n_chans = max(1, len(chans))
        tab_w = (cw - 8) // n_chans
        for idx, c in enumerate(chans):
            tx = cx + 4 + idx * tab_w
            is_active = (idx == self._channel_idx)
            t_bg = theme.PRIMARY if is_active else theme.CARD
            t_fg = api.WHITE if is_active else theme.TEXT_DIM

            d.rect(tx, cy + 6, tab_w - 2, 16, t_bg, fill=True)
            if is_active:
                d.rect(tx, cy + 6, tab_w - 2, 16, theme.GOLD, fill=False)
            t_lbl = c.get("tab", c["name"])
            d.text(t_lbl, tx + (tab_w - 2 - len(t_lbl) * 8) // 2, cy + 10, t_fg)

        # FIXED, IMMUTABLE QR Container Box dimensions (116x116px)
        box_w = 116
        box_h = 116
        box_x = (SW - box_w) // 2
        box_y = cy + 26

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
