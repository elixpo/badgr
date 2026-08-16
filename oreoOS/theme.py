"""Oreo OS — State-of-the-Art System Theming Engine.

Provides cohesive design tokens, curated theme presets, dynamic harmonic palette
derivation from arbitrary custom accents, and persistent state management.
"""

import json
from oreoOS import api

# ── Theme Definition & Design Tokens ─────────────────────────────────────────

class Theme:
    def __init__(self, id, name, bg, card, primary, teal, gold,
                 text_bright, text_dim, muted, muted2,
                 status_bg=None, is_dark=False):
        self.id          = id
        self.name        = name
        self.bg_rgb      = bg
        self.card_rgb    = card
        self.primary_rgb = primary
        self.teal_rgb    = teal
        self.gold_rgb    = gold
        self.dark_rgb    = text_bright
        self.text_dim_rgb= text_dim
        self.muted_rgb   = muted
        self.muted2_rgb  = muted2
        self.status_rgb  = status_bg if status_bg is not None else primary
        self.is_dark     = is_dark

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "is_dark": self.is_dark,
            "primary": self.primary_rgb
        }


# ── Curated Theme Presets ───────────────────────────────────────────────────

PRESETS = {
    "celebration": Theme(
        id="celebration",
        name="Panda Celebration",
        bg=(255, 248, 235),       # warm ivory cream
        card=(255, 240, 210),     # slightly deeper cream card
        primary=(255, 93, 104),   # cheek pink accent
        teal=(0, 180, 165),       # festive teal
        gold=(255, 190, 30),      # celebration gold
        text_bright=(38, 38, 48), # deep dark outline text
        text_dim=(100, 80, 70),   # readable secondary text
        muted=(160, 120, 100),    # warm muted labels
        muted2=(200, 160, 140),   # subtle borders
        status_bg=(255, 93, 104), # pink status bar
        is_dark=False
    ),
    "midnight": Theme(
        id="midnight",
        name="Midnight OLED",
        bg=(18, 18, 26),          # deep obsidian slate
        card=(28, 28, 40),        # elevated surface
        primary=(0, 240, 255),    # neon cyan
        teal=(0, 200, 180),       # aqua
        gold=(255, 200, 50),      # electric gold
        text_bright=(245, 245, 250), # pure bright white
        text_dim=(180, 180, 200),
        muted=(120, 120, 145),
        muted2=(70, 70, 90),
        status_bg=(0, 200, 215),
        is_dark=True
    ),
    "emerald": Theme(
        id="emerald",
        name="Matcha Forest",
        bg=(238, 245, 232),       # soft matcha cream
        card=(220, 235, 212),     # sage surface
        primary=(46, 102, 74),    # deep forest green
        teal=(90, 168, 124),      # bamboo green
        gold=(230, 180, 40),      # harvest gold
        text_bright=(26, 51, 34), # deep dark evergreen text
        text_dim=(60, 95, 72),
        muted=(110, 140, 120),
        muted2=(170, 195, 175),
        status_bg=(46, 102, 74),
        is_dark=False
    ),
    "cyberpunk": Theme(
        id="cyberpunk",
        name="Neon Synthwave",
        bg=(22, 15, 41),          # deep purple void
        card=(36, 23, 68),        # synth card surface
        primary=(255, 42, 133),   # hot neon magenta
        teal=(0, 255, 240),       # electric cyan
        gold=(255, 220, 0),       # laser yellow
        text_bright=(255, 255, 255),
        text_dim=(200, 180, 230),
        muted=(140, 110, 180),
        muted2=(80, 60, 110),
        status_bg=(255, 42, 133),
        is_dark=True
    ),
    "sunset": Theme(
        id="sunset",
        name="Sunset Amber",
        bg=(253, 244, 236),       # terracotta cream
        card=(250, 230, 215),     # warm sand card
        primary=(255, 140, 30),   # rich sunset amber
        teal=(232, 77, 98),       # dusk rose
        gold=(255, 200, 40),      # golden sun
        text_bright=(45, 30, 25), # espresso dark text
        text_dim=(110, 75, 60),
        muted=(175, 125, 105),
        muted2=(215, 175, 155),
        status_bg=(255, 140, 30),
        is_dark=False
    ),
    "nordic": Theme(
        id="nordic",
        name="Nordic Frost",
        bg=(236, 239, 244),       # polar ice white
        card=(216, 222, 233),     # glacier frost card
        primary=(94, 129, 172),   # arctic blue
        teal=(136, 192, 208),     # ice teal
        gold=(235, 203, 139),     # auroral gold
        text_bright=(46, 52, 64), # slate ink text
        text_dim=(76, 86, 106),
        muted=(120, 130, 150),
        muted2=(170, 180, 195),
        status_bg=(94, 129, 172),
        is_dark=False
    ),
    "gameboy": Theme(
        id="gameboy",
        name="Retro DMG (1989)",
        bg=(139, 172, 15),        # authentic DMG olive green
        card=(155, 188, 15),      # elevated LCD surface
        primary=(48, 98, 48),     # deep olive accent
        teal=(15, 56, 15),        # darkest shadow
        gold=(190, 210, 20),      # bright LCD highlight
        text_bright=(15, 56, 15), # deep olive shadow text
        text_dim=(48, 98, 48),
        muted=(70, 120, 70),
        muted2=(110, 145, 15),
        status_bg=(48, 98, 48),
        is_dark=False
    )
}

PRESET_KEYS = ["celebration", "midnight", "emerald", "cyberpunk", "sunset", "nordic", "gameboy", "custom"]

# ── Dynamic Harmonic Palette Derivation ──────────────────────────────────────

def derive_custom_theme(r, g, b):
    """Dynamically derive a cohesive OS theme from any user-selected RGB accent."""
    r, g, b = max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b)))
    
    # Calculate perceived luminance: Y = 0.299R + 0.587G + 0.114B
    lum = (299 * r + 587 * g + 114 * b) // 1000
    
    # Base background and card tones based on luminance preference
    if lum < 100:
        # Dark theme
        bg = (18, 18, 26)
        card = (28, 28, 40)
        text_bright = (245, 245, 250)
        text_dim = (180, 180, 200)
        muted = (130, 130, 150)
        muted2 = (70, 70, 90)
        is_dark = True
    else:
        # Light warm ivory theme
        bg = (255, 248, 235)
        card = (255, 240, 210)
        text_bright = (38, 38, 48)
        text_dim = (100, 80, 70)
        muted = (160, 120, 100)
        muted2 = (200, 160, 140)
        is_dark = False

    # Harmonically derived teal and gold
    teal = (max(0, min(255, int(g * 0.8))), max(0, min(255, int(b * 0.9 + 20))), max(0, min(255, int(r * 0.7))))
    gold = (255, 190, 30)

    return Theme(
        id="custom",
        name="Custom Palette",
        bg=bg,
        card=card,
        primary=(r, g, b),
        teal=teal,
        gold=gold,
        text_bright=text_bright,
        text_dim=text_dim,
        muted=muted,
        muted2=muted2,
        status_bg=(r, g, b),
        is_dark=is_dark
    )


# ── Active State & Live Module Variables ─────────────────────────────────────

CURRENT_THEME = PRESETS["celebration"]

# Module-level raw RGB triplets
BG_R,      BG_G,      BG_B      = CURRENT_THEME.bg_rgb
CARD_R,    CARD_G,    CARD_B    = CURRENT_THEME.card_rgb
PRIMARY_R, PRIMARY_G, PRIMARY_B = CURRENT_THEME.primary_rgb
TEAL_R,    TEAL_G,    TEAL_B    = CURRENT_THEME.teal_rgb
GOLD_R,    GOLD_G,    GOLD_B    = CURRENT_THEME.gold_rgb
FUR_R,     FUR_G,     FUR_B     = CURRENT_THEME.dark_rgb
MUTED_R,   MUTED_G,   MUTED_B   = CURRENT_THEME.muted_rgb
DARK_R,    DARK_G,    DARK_B    = CURRENT_THEME.dark_rgb

# Module-level RGB565 values
BG          = api.rgb(*CURRENT_THEME.bg_rgb)
CARD        = api.rgb(*CURRENT_THEME.card_rgb)
PRIMARY     = api.rgb(*CURRENT_THEME.primary_rgb)
TEAL        = api.rgb(*CURRENT_THEME.teal_rgb)
GOLD        = api.rgb(*CURRENT_THEME.gold_rgb)
TEXT_BRIGHT = api.rgb(*CURRENT_THEME.dark_rgb)
TEXT_DIM    = api.rgb(*CURRENT_THEME.text_dim_rgb)
MUTED       = api.rgb(*CURRENT_THEME.muted_rgb)
MUTED2      = api.rgb(*CURRENT_THEME.muted2_rgb)
STATUS_BG   = api.rgb(*CURRENT_THEME.status_rgb)
DOCK_BG     = api.rgb(*CURRENT_THEME.card_rgb)
DOCK_SEL    = api.rgb(min(255, CURRENT_THEME.card_rgb[0] + 15),
                      min(255, CURRENT_THEME.card_rgb[1] + 15),
                      min(255, CURRENT_THEME.card_rgb[2] + 15))
SEL_BORDER  = PRIMARY
ORANGE      = api.rgb(255, 140,  30)
PURPLE      = api.rgb(180,  80, 220)
GREEN       = api.rgb(60,  200, 100)


def apply_theme(theme_obj, save=True):
    """Apply a Theme object across all global design tokens in real-time."""
    global CURRENT_THEME
    global BG_R, BG_G, BG_B, CARD_R, CARD_G, CARD_B, PRIMARY_R, PRIMARY_G, PRIMARY_B
    global TEAL_R, TEAL_G, TEAL_B, GOLD_R, GOLD_G, GOLD_B, FUR_R, FUR_G, FUR_B, MUTED_R, MUTED_G, MUTED_B, DARK_R, DARK_G, DARK_B
    global BG, CARD, PRIMARY, TEAL, GOLD, TEXT_BRIGHT, TEXT_DIM, MUTED, MUTED2, STATUS_BG, DOCK_BG, DOCK_SEL, SEL_BORDER

    CURRENT_THEME = theme_obj

    BG_R, BG_G, BG_B           = theme_obj.bg_rgb
    CARD_R, CARD_G, CARD_B     = theme_obj.card_rgb
    PRIMARY_R, PRIMARY_G, PRIMARY_B = theme_obj.primary_rgb
    TEAL_R, TEAL_G, TEAL_B     = theme_obj.teal_rgb
    GOLD_R, GOLD_G, GOLD_B     = theme_obj.gold_rgb
    FUR_R, FUR_G, FUR_B        = theme_obj.dark_rgb
    MUTED_R, MUTED_G, MUTED_B  = theme_obj.muted_rgb
    DARK_R, DARK_G, DARK_B     = theme_obj.dark_rgb

    BG          = api.rgb(*theme_obj.bg_rgb)
    CARD        = api.rgb(*theme_obj.card_rgb)
    PRIMARY     = api.rgb(*theme_obj.primary_rgb)
    TEAL        = api.rgb(*theme_obj.teal_rgb)
    GOLD        = api.rgb(*theme_obj.gold_rgb)
    TEXT_BRIGHT = api.rgb(*theme_obj.dark_rgb)
    TEXT_DIM    = api.rgb(*theme_obj.text_dim_rgb)
    MUTED       = api.rgb(*theme_obj.muted_rgb)
    MUTED2      = api.rgb(*theme_obj.muted2_rgb)
    STATUS_BG   = api.rgb(*theme_obj.status_rgb)
    DOCK_BG     = api.rgb(*theme_obj.card_rgb)
    DOCK_SEL    = api.rgb(min(255, theme_obj.card_rgb[0] + 15),
                          min(255, theme_obj.card_rgb[1] + 15),
                          min(255, theme_obj.card_rgb[2] + 15))
    SEL_BORDER  = PRIMARY

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

THEME_STATE_PATH = "state_theme.json"
LEGACY_STATE_PATH = "state_color.txt"


def save_theme_state():
    """Persist current active theme configuration to disk."""
    try:
        data = {
            "preset_id": CURRENT_THEME.id,
            "primary_rgb": CURRENT_THEME.primary_rgb
        }
        with open(THEME_STATE_PATH, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def load_custom_theme():
    """Load persisted theme from state_theme.json with legacy state_color.txt migration."""
    try:
        with open(THEME_STATE_PATH, "r") as f:
            data = json.load(f)
            preset_id = data.get("preset_id")
            if preset_id in PRESETS and preset_id != "custom":
                apply_theme(PRESETS[preset_id], save=False)
                return
            elif preset_id == "custom" or "primary_rgb" in data:
                r, g, b = data["primary_rgb"]
                apply_theme(derive_custom_theme(r, g, b), save=False)
                return
    except Exception:
        pass

    # Legacy state_color.txt fallback & auto-migration
    try:
        with open(LEGACY_STATE_PATH, "r") as f:
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
