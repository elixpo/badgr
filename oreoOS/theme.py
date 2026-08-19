"""Oreo OS — State-of-the-Art System Theming Engine.

Provides cohesive design tokens, curated theme presets, dynamic harmonic palette
derivation from arbitrary custom accents, and automatic text/icon contrast inversion.
"""

from oreoOS import api

# ── Color Utilities ──────────────────────────────────────────────────────────


def _rgb_to_hsv(r, g, b):
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(rf, gf, bf), min(rf, gf, bf)
    df = mx - mn
    if mx == mn:
        h = 0
    elif mx == rf:
        h = (60 * ((gf - bf) / df) + 360) % 360
    elif mx == gf:
        h = (60 * ((bf - rf) / df) + 120) % 360
    elif mx == bf:
        h = (60 * ((rf - gf) / df) + 240) % 360
    s = 0 if mx == 0 else (df / mx)
    v = mx
    return h, s, v


def _hsv_to_rgb(h, s, v):
    h60 = h / 60.0
    h60_f = int(h60)
    hi = h60_f % 6
    f = h60 - h60_f
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    r, g, b = 0, 0, 0
    if hi == 0:
        r, g, b = v, t, p
    elif hi == 1:
        r, g, b = q, v, p
    elif hi == 2:
        r, g, b = p, v, t
    elif hi == 3:
        r, g, b = p, q, v
    elif hi == 4:
        r, g, b = t, p, v
    elif hi == 5:
        r, g, b = v, p, q
    return int(round(r * 255)), int(round(g * 255)), int(round(b * 255))


def get_perceived_luminance(r, g, b):
    """Returns integer perceived luminance (0..255)."""
    return (299 * int(r) + 587 * int(g) + 114 * int(b)) // 1000


CONTRAST_LUM_THRESHOLD = 170


# ── Theme Definition & Design Tokens ─────────────────────────────────────────


class Theme:
    def __init__(
        self,
        id,
        name,
        bg,
        card,
        primary,
        teal,
        gold,
        text_bright,
        text_dim,
        muted,
        muted2,
        status_bg=None,
        status_text=None,
        status_accent=None,
        dock_bg=None,
        dock_sel=None,
        sel_border=None,
        sel_text=None,
        is_dark=False,
    ):
        self.id = id
        self.name = name
        self.bg_rgb = bg
        self.card_rgb = card
        self.primary_rgb = primary
        self.teal_rgb = teal
        self.gold_rgb = gold
        self.dark_rgb = text_bright
        self.text_dim_rgb = text_dim
        self.muted_rgb = muted
        self.muted2_rgb = muted2
        self.status_rgb = status_bg if status_bg is not None else primary

        # Status text contrast inversion
        if status_text is not None:
            self.status_text_rgb = status_text
        else:
            lum = get_perceived_luminance(*self.status_rgb)
            self.status_text_rgb = (
                (24, 24, 32) if lum >= CONTRAST_LUM_THRESHOLD else (255, 255, 255)
            )

        self.status_accent_rgb = status_accent if status_accent is not None else gold
        self.dock_bg_rgb = dock_bg if dock_bg is not None else card
        self.dock_sel_rgb = (
            dock_sel
            if dock_sel is not None
            else (min(255, card[0] + 15), min(255, card[1] + 15), min(255, card[2] + 15))
        )
        self.sel_border_rgb = sel_border if sel_border is not None else primary
        self.sel_text_rgb = (
            sel_text
            if sel_text is not None
            else (
                primary
                if not is_dark and get_perceived_luminance(*primary) < CONTRAST_LUM_THRESHOLD
                else (
                    primary if is_dark and get_perceived_luminance(*primary) > 80 else text_bright
                )
            )
        )
        self.is_dark = is_dark

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "is_dark": self.is_dark,
            "primary": self.primary_rgb,
        }


# ── Curated Theme Presets (Unixporn & Iconic Rice Aesthetics) ────────────────
PRESETS = {
    "celebration": Theme(
        id="celebration",
        name="Panda Celebration",
        bg=(255, 248, 235),  # warm ivory cream
        card=(255, 240, 210),  # slightly deeper cream card
        primary=(255, 93, 104),  # cheek pink accent
        teal=(0, 180, 165),  # festive teal
        gold=(255, 190, 30),  # celebration gold
        text_bright=(38, 38, 48),  # deep dark outline text
        text_dim=(100, 80, 70),  # readable secondary text
        muted=(160, 120, 100),  # warm muted labels
        muted2=(200, 160, 140),  # subtle borders
        status_bg=(255, 93, 104),  # pink status bar
        status_text=(255, 255, 255),  # white status text
        status_accent=(255, 190, 30),
        dock_bg=(255, 240, 210),
        dock_sel=(255, 220, 180),
        sel_border=(255, 93, 104),
        sel_text=(255, 93, 104),
        is_dark=False,
    ),
    "catppuccin": Theme(
        id="catppuccin",
        name="Catppuccin Mocha",
        bg=(30, 30, 46),  # #1e1e2e Base
        card=(24, 24, 37),  # #181825 Mantle
        primary=(203, 166, 247),  # #cba6f7 Mauve
        teal=(137, 220, 235),  # #89dceb Sky
        gold=(249, 226, 175),  # #f9e2af Yellow
        text_bright=(205, 214, 244),  # #cdd6f4 Text
        text_dim=(166, 173, 200),  # #a6adc8 Subtext0
        muted=(108, 112, 134),  # #6c7086 Overlay0
        muted2=(69, 71, 90),  # #45475a Surface1
        status_bg=(24, 24, 37),
        status_text=(203, 166, 247),
        status_accent=(137, 220, 235),
        dock_bg=(24, 24, 37),
        dock_sel=(49, 50, 68),
        sel_border=(203, 166, 247),
        sel_text=(203, 166, 247),
        is_dark=True,
    ),
    "tokyo_night": Theme(
        id="tokyo_night",
        name="Tokyo Night",
        bg=(26, 27, 38),  # #1a1b26
        card=(36, 40, 59),  # #24283b
        primary=(122, 162, 247),  # #7aa2f7 Blue
        teal=(125, 207, 255),  # #7dcfff Cyan
        gold=(224, 175, 104),  # #e0af68 Warm Yellow
        text_bright=(192, 202, 245),  # #c0caf5
        text_dim=(169, 177, 214),  # #a9b1d6
        muted=(86, 95, 137),  # #565f89
        muted2=(41, 46, 66),  # #292e42
        status_bg=(26, 27, 38),
        status_text=(122, 162, 247),
        status_accent=(125, 207, 255),
        dock_bg=(31, 35, 53),
        dock_sel=(47, 54, 82),
        sel_border=(122, 162, 247),
        sel_text=(122, 162, 247),
        is_dark=True,
    ),
    "gruvbox": Theme(
        id="gruvbox",
        name="Gruvbox Dark",
        bg=(40, 40, 40),  # #282828 Dark0
        card=(50, 48, 47),  # #32302f Dark0_soft
        primary=(254, 128, 25),  # #fe8019 Bright Orange
        teal=(142, 192, 124),  # #8ec07c Bright Aqua
        gold=(250, 189, 47),  # #fabd2f Bright Yellow
        text_bright=(235, 219, 178),  # #ebdbb2 Light1
        text_dim=(189, 174, 147),  # #bdae93 Light4
        muted=(146, 131, 116),  # #928374 Gray
        muted2=(80, 73, 69),  # #504945 Dark2
        status_bg=(40, 40, 40),
        status_text=(254, 128, 25),
        status_accent=(250, 189, 47),
        dock_bg=(50, 48, 47),
        dock_sel=(60, 56, 54),
        sel_border=(254, 128, 25),
        sel_text=(254, 128, 25),
        is_dark=True,
    ),
    "nord": Theme(
        id="nord",
        name="Nord Arctic",
        bg=(46, 52, 64),  # #2e3440 Polar Night
        card=(59, 66, 82),  # #3b4252 Polar Night 1
        primary=(136, 192, 208),  # #88c0d0 Frost Ice
        teal=(143, 188, 187),  # #8fbcbb Frost Teal
        gold=(235, 203, 139),  # #ebcb8b Aurora Gold
        text_bright=(236, 239, 244),  # #eceff4 Snow Storm
        text_dim=(216, 222, 233),  # #d8dee9
        muted=(129, 161, 193),  # #81a1c1 Frost Slate
        muted2=(76, 86, 106),  # #4c566a
        status_bg=(46, 52, 64),
        status_text=(136, 192, 208),
        status_accent=(143, 188, 187),
        dock_bg=(59, 66, 82),
        dock_sel=(67, 76, 94),
        sel_border=(136, 192, 208),
        sel_text=(136, 192, 208),
        is_dark=True,
    ),
    "rose_pine": Theme(
        id="rose_pine",
        name="Rose Pine",
        bg=(25, 23, 36),  # #191724 Base
        card=(31, 29, 46),  # #1f1d2e Surface
        primary=(235, 188, 186),  # #ebbcba Rose
        teal=(156, 207, 216),  # #9ccfd8 Foam
        gold=(246, 193, 119),  # #f6c177 Gold
        text_bright=(224, 222, 244),  # #e0def4 Text
        text_dim=(144, 140, 170),  # #908caa Subtle
        muted=(110, 106, 134),  # #6e6a86 Muted
        muted2=(38, 35, 58),  # #26233a Overlay
        status_bg=(25, 23, 36),
        status_text=(235, 188, 186),
        status_accent=(156, 207, 216),
        dock_bg=(31, 29, 46),
        dock_sel=(42, 39, 63),
        sel_border=(235, 188, 186),
        sel_text=(235, 188, 186),
        is_dark=True,
    ),
    "dracula": Theme(
        id="dracula",
        name="Dracula Pro",
        bg=(40, 42, 54),  # #282a36
        card=(68, 71, 90),  # #44475a Selection
        primary=(255, 121, 198),  # #ff79c6 Pink
        teal=(139, 233, 253),  # #8be9fd Cyan
        gold=(241, 250, 140),  # #f1fa8c Yellow
        text_bright=(248, 248, 242),  # #f8f8f2 Foreground
        text_dim=(189, 147, 249),  # #bd93f9 Purple
        muted=(98, 114, 164),  # #6272a4 Comment
        muted2=(50, 52, 68),
        status_bg=(40, 42, 54),
        status_text=(255, 121, 198),
        status_accent=(139, 233, 253),
        dock_bg=(52, 55, 70),
        dock_sel=(68, 71, 90),
        sel_border=(255, 121, 198),
        sel_text=(255, 121, 198),
        is_dark=True,
    ),
    "kanagawa": Theme(
        id="kanagawa",
        name="Kanagawa Wave",
        bg=(31, 31, 40),  # #1f1f28 SumiInk3
        card=(42, 42, 55),  # #2a2a37 SumiInk4
        primary=(126, 156, 216),  # #7e9cd8 Spring Blue
        teal=(122, 168, 159),  # #7aa89f Wave Aqua
        gold=(230, 195, 132),  # #e6c384 Carp Yellow
        text_bright=(220, 215, 186),  # #dcd7ba Fuji White
        text_dim=(192, 163, 110),  # #c0a36e Boat Yellow
        muted=(114, 113, 105),  # #727169 Fuji Gray
        muted2=(54, 54, 70),  # #363646 SumiInk5
        status_bg=(31, 31, 40),
        status_text=(126, 156, 216),
        status_accent=(122, 168, 159),
        dock_bg=(42, 42, 55),
        dock_sel=(54, 54, 70),
        sel_border=(126, 156, 216),
        sel_text=(126, 156, 216),
        is_dark=True,
    ),
    "latte": Theme(
        id="latte",
        name="Catppuccin Latte",
        bg=(239, 241, 245),  # #eff1f5 Base
        card=(230, 233, 239),  # #e6e9ef Mantle
        primary=(136, 57, 239),  # #8839ef Mauve
        teal=(32, 159, 181),  # #209fb5 Sapphire
        gold=(223, 142, 29),  # #df8e1d Yellow
        text_bright=(76, 79, 105),  # #4c4f69 Text
        text_dim=(108, 111, 133),  # #6c6f85 Subtext0
        muted=(156, 160, 176),  # #9ca0b0 Overlay0
        muted2=(204, 208, 218),  # #ccd0da Surface0
        status_bg=(136, 57, 239),
        status_text=(255, 255, 255),
        status_accent=(32, 159, 181),
        dock_bg=(230, 233, 239),
        dock_sel=(218, 222, 230),
        sel_border=(136, 57, 239),
        sel_text=(136, 57, 239),
        is_dark=False,
    ),
    "matrix": Theme(
        id="matrix",
        name="Matrix Phosphor",
        bg=(13, 17, 23),  # pitch darkness
        card=(22, 27, 34),  # terminal card
        primary=(0, 255, 102),  # phosphor green
        teal=(57, 211, 83),  # mid green
        gold=(126, 231, 135),  # light matrix glow
        text_bright=(0, 255, 102),  # green CRT text
        text_dim=(46, 160, 67),
        muted=(35, 134, 54),
        muted2=(27, 60, 36),
        status_bg=(13, 17, 23),
        status_text=(0, 255, 102),
        status_accent=(57, 211, 83),
        dock_bg=(22, 27, 34),
        dock_sel=(33, 44, 38),
        sel_border=(0, 255, 102),
        sel_text=(0, 255, 102),
        is_dark=True,
    ),
    "gameboy": Theme(
        id="gameboy",
        name="Retro DMG (1989)",
        bg=(139, 172, 15),  # authentic DMG olive green
        card=(155, 188, 15),  # elevated LCD surface
        primary=(48, 98, 48),  # deep olive accent
        teal=(15, 56, 15),  # darkest shadow
        gold=(190, 210, 20),  # bright LCD highlight
        text_bright=(15, 56, 15),  # deep olive shadow text
        text_dim=(48, 98, 48),
        muted=(70, 120, 70),
        muted2=(110, 145, 15),
        status_bg=(48, 98, 48),
        status_text=(155, 188, 15),
        status_accent=(190, 210, 20),
        dock_bg=(148, 180, 15),
        dock_sel=(120, 155, 10),
        sel_border=(15, 56, 15),
        sel_text=(15, 56, 15),
        is_dark=False,
    ),
}

LEGACY_PRESET_MAP = {
    "midnight": "catppuccin",
    "cyberpunk": "tokyo_night",
    "nordic": "nord",
    "emerald": "kanagawa",
    "sunset": "gruvbox",
}

PRESET_KEYS = [
    "celebration",
    "catppuccin",
    "tokyo_night",
    "gruvbox",
    "nord",
    "rose_pine",
    "dracula",
    "kanagawa",
    "latte",
    "matrix",
    "gameboy",
    "custom",
]

# ── Dynamic Harmonic Palette Derivation ──────────────────────────────────────


def derive_custom_theme(r, g, b):
    """Dynamically derive a cohesive OS theme from any user-selected RGB accent with contrast inversion."""
    r, g, b = max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b)))

    # Calculate perceived luminance: Y = 0.299R + 0.587G + 0.114B (0..255)
    lum = get_perceived_luminance(r, g, b)
    h, s, v = _rgb_to_hsv(r, g, b)

    # Compute harmonious complementary and triadic accents
    teal_rgb = _hsv_to_rgb((h + 160) % 360, max(0.5, min(0.9, s)), max(0.6, min(0.95, v)))
    gold_rgb = _hsv_to_rgb((h + 50) % 360, max(0.6, min(0.85, s)), max(0.8, min(1.0, v)))

    # Automatic contrast text for status bar
    status_text = (24, 24, 32) if lum >= CONTRAST_LUM_THRESHOLD else (255, 255, 255)
    status_accent = (
        (int(r * 0.7), int(g * 0.7), int(b * 0.7))
        if lum >= CONTRAST_LUM_THRESHOLD
        else (min(255, int(r * 1.3 + 30)), min(255, int(g * 1.3 + 30)), min(255, int(b * 1.3 + 30)))
    )

    if lum < 55:
        # Deep Dark / OLED theme mode
        bg = (18, 18, 26)
        card = (28, 28, 42)
        dock_bg = (24, 24, 36)
        text_bright = (245, 245, 250)
        text_dim = (180, 180, 200)
        muted = (130, 130, 155)
        muted2 = (60, 60, 85)
        dock_sel = (
            min(255, 35 + int(r * 0.15)),
            min(255, 35 + int(g * 0.15)),
            min(255, 50 + int(b * 0.15)),
        )
        sel_border = (min(255, r + 60), min(255, g + 60), min(255, b + 60))
        sel_text = (0, 240, 255)
        is_dark = True
    elif lum > 215:
        # High-key White / Pure Light theme mode
        bg = (248, 250, 252)
        card = (235, 238, 244)
        dock_bg = (240, 242, 248)
        text_bright = (18, 24, 38)
        text_dim = (70, 85, 105)
        muted = (145, 160, 180)
        muted2 = (200, 212, 224)
        dock_sel = (215, 225, 238)
        sel_border = (30, 42, 60)
        sel_text = (30, 42, 60)
        is_dark = False
    else:
        # Balanced Vibrant Light theme mode
        bg = (255, 248, 235)
        card = (255, 240, 210)
        dock_bg = (255, 242, 220)
        text_bright = (38, 38, 48)
        text_dim = (100, 80, 70)
        muted = (160, 120, 100)
        muted2 = (200, 160, 140)
        dock_sel = (
            min(255, 235 + int(r * 0.08)),
            min(255, 215 + int(g * 0.08)),
            min(255, 185 + int(b * 0.08)),
        )
        sel_border = (r, g, b)
        sel_text = (r, g, b) if lum < CONTRAST_LUM_THRESHOLD else (38, 38, 48)
        is_dark = False

    return Theme(
        id="custom",
        name="Custom Palette",
        bg=bg,
        card=card,
        primary=(r, g, b),
        teal=teal_rgb,
        gold=gold_rgb,
        text_bright=text_bright,
        text_dim=text_dim,
        muted=muted,
        muted2=muted2,
        status_bg=(r, g, b),
        status_text=status_text,
        status_accent=status_accent,
        dock_bg=dock_bg,
        dock_sel=dock_sel,
        sel_border=sel_border,
        sel_text=sel_text,
        is_dark=is_dark,
    )


# ── Active State & Live Module Variables ─────────────────────────────────────

CURRENT_THEME = PRESETS["celebration"]

# Module-level raw RGB triplets
BG_R, BG_G, BG_B = CURRENT_THEME.bg_rgb
CARD_R, CARD_G, CARD_B = CURRENT_THEME.card_rgb
PRIMARY_R, PRIMARY_G, PRIMARY_B = CURRENT_THEME.primary_rgb
TEAL_R, TEAL_G, TEAL_B = CURRENT_THEME.teal_rgb
GOLD_R, GOLD_G, GOLD_B = CURRENT_THEME.gold_rgb
FUR_R, FUR_G, FUR_B = CURRENT_THEME.dark_rgb
MUTED_R, MUTED_G, MUTED_B = CURRENT_THEME.muted_rgb
DARK_R, DARK_G, DARK_B = CURRENT_THEME.dark_rgb

# Module-level RGB565 values
BG = api.rgb(*CURRENT_THEME.bg_rgb)
CARD = api.rgb(*CURRENT_THEME.card_rgb)
PRIMARY = api.rgb(*CURRENT_THEME.primary_rgb)
TEAL = api.rgb(*CURRENT_THEME.teal_rgb)
GOLD = api.rgb(*CURRENT_THEME.gold_rgb)
TEXT_BRIGHT = api.rgb(*CURRENT_THEME.dark_rgb)
TEXT_DIM = api.rgb(*CURRENT_THEME.text_dim_rgb)
MUTED = api.rgb(*CURRENT_THEME.muted_rgb)
MUTED2 = api.rgb(*CURRENT_THEME.muted2_rgb)
STATUS_BG = api.rgb(*CURRENT_THEME.status_rgb)
STATUS_TEXT = api.rgb(*CURRENT_THEME.status_text_rgb)
STATUS_ACCENT = api.rgb(*CURRENT_THEME.status_accent_rgb)
DOCK_BG = api.rgb(*CURRENT_THEME.dock_bg_rgb)
DOCK_SEL = api.rgb(*CURRENT_THEME.dock_sel_rgb)
SEL_BORDER = api.rgb(*CURRENT_THEME.sel_border_rgb)
SEL_TEXT = api.rgb(*CURRENT_THEME.sel_text_rgb)
SHADOW = api.rgb(20, 20, 28) if CURRENT_THEME.is_dark else api.rgb(180, 160, 140)
ORANGE = api.rgb(255, 140, 30)
PURPLE = api.rgb(180, 80, 220)
GREEN = api.rgb(60, 200, 100)


def apply_theme(theme_obj, save=True):
    """Apply a Theme object across all global design tokens in real-time."""
    global CURRENT_THEME
    global BG_R, BG_G, BG_B, CARD_R, CARD_G, CARD_B, PRIMARY_R, PRIMARY_G, PRIMARY_B
    global \
        TEAL_R, \
        TEAL_G, \
        TEAL_B, \
        GOLD_R, \
        GOLD_G, \
        GOLD_B, \
        FUR_R, \
        FUR_G, \
        FUR_B, \
        MUTED_R, \
        MUTED_G, \
        MUTED_B, \
        DARK_R, \
        DARK_G, \
        DARK_B
    global \
        BG, \
        CARD, \
        PRIMARY, \
        TEAL, \
        GOLD, \
        TEXT_BRIGHT, \
        TEXT_DIM, \
        MUTED, \
        MUTED2, \
        STATUS_BG, \
        STATUS_TEXT, \
        STATUS_ACCENT, \
        DOCK_BG, \
        DOCK_SEL, \
        SEL_BORDER, \
        SEL_TEXT, \
        SHADOW

    CURRENT_THEME = theme_obj

    BG_R, BG_G, BG_B = theme_obj.bg_rgb
    CARD_R, CARD_G, CARD_B = theme_obj.card_rgb
    PRIMARY_R, PRIMARY_G, PRIMARY_B = theme_obj.primary_rgb
    TEAL_R, TEAL_G, TEAL_B = theme_obj.teal_rgb
    GOLD_R, GOLD_G, GOLD_B = theme_obj.gold_rgb
    FUR_R, FUR_G, FUR_B = theme_obj.dark_rgb
    MUTED_R, MUTED_G, MUTED_B = theme_obj.muted_rgb
    DARK_R, DARK_G, DARK_B = theme_obj.dark_rgb

    BG = api.rgb(*theme_obj.bg_rgb)
    CARD = api.rgb(*theme_obj.card_rgb)
    PRIMARY = api.rgb(*theme_obj.primary_rgb)
    TEAL = api.rgb(*theme_obj.teal_rgb)
    GOLD = api.rgb(*theme_obj.gold_rgb)
    TEXT_BRIGHT = api.rgb(*theme_obj.dark_rgb)
    TEXT_DIM = api.rgb(*theme_obj.text_dim_rgb)
    MUTED = api.rgb(*theme_obj.muted_rgb)
    MUTED2 = api.rgb(*theme_obj.muted2_rgb)
    STATUS_BG = api.rgb(*theme_obj.status_rgb)
    STATUS_TEXT = api.rgb(*theme_obj.status_text_rgb)
    STATUS_ACCENT = api.rgb(*theme_obj.status_accent_rgb)
    DOCK_BG = api.rgb(*theme_obj.dock_bg_rgb)
    DOCK_SEL = api.rgb(*theme_obj.dock_sel_rgb)
    SEL_BORDER = api.rgb(*theme_obj.sel_border_rgb)
    SEL_TEXT = api.rgb(*theme_obj.sel_text_rgb)
    SHADOW = api.rgb(20, 20, 28) if theme_obj.is_dark else api.rgb(180, 160, 140)

    if save:
        save_theme_state()


def set_preset(preset_id, save=True):
    """Set active theme to a curated preset by ID."""
    if preset_id in PRESETS:
        apply_theme(PRESETS[preset_id], save=save)
        return True
    return False


def set_primary_color(r, g, b, save=True):
    """Set custom accent color with harmonic dynamic theme derivation."""
    custom_theme = derive_custom_theme(r, g, b)
    apply_theme(custom_theme, save=save)


def get_presets():
    """Return dictionary of all available theme presets."""
    return PRESETS


def get_current_id():
    """Return active theme preset ID."""
    return CURRENT_THEME.id


def get_current_name():
    """Return active theme display name."""
    return CURRENT_THEME.name


# ── Persistence Engine ──────────────────────────────────────────────────────


def save_theme_state():
    """Persist current active theme configuration to disk inside badge_data/."""
    try:
        from oreoOS import storage

        data = {"preset_id": CURRENT_THEME.id, "primary_rgb": CURRENT_THEME.primary_rgb}
        return storage.save_json("state_theme.json", data)
    except Exception as e:
        api.log_debug("THEME", "Failed saving theme", e)
        return False


def load_custom_theme():
    """Load persisted theme from state_theme.json with legacy state_color.txt migration."""
    try:
        from oreoOS import storage

        data = storage.load_json("state_theme.json")
        if data:
            preset_id = data.get("preset_id")
            if preset_id in LEGACY_PRESET_MAP:
                preset_id = LEGACY_PRESET_MAP[preset_id]
            if preset_id in PRESETS and preset_id != "custom":
                apply_theme(PRESETS[preset_id], save=False)
                return
            elif preset_id == "custom" or "primary_rgb" in data:
                r, g, b = data["primary_rgb"]
                apply_theme(derive_custom_theme(r, g, b), save=False)
                return
    except Exception as e:
        api.log_debug("THEME", "Failed loading custom theme", e)

    # Legacy state_color.txt fallback & auto-migration
    try:
        with open("state_color.txt", "r") as f:
            parts = f.read().strip().split(",")
            if len(parts) == 5:
                r, g, b = int(parts[2]), int(parts[3]), int(parts[4])
            elif len(parts) == 3:
                r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
            else:
                return
            apply_theme(derive_custom_theme(r, g, b), save=True)
    except Exception:
        pass


# Initialize theme state on module load
load_custom_theme()
