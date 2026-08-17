def _load_env():
    env = {}
    for fname in (".env", ".env.local"):
        try:
            with open(fname) as f:
                text = f.read()
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env

_env = _load_env()

# On MicroPython embedded hardware where .env is absent, hydrate from hardware secrets.py
if not _env:
    try:
        import sys
        if sys.platform not in ("linux", "darwin", "win32"):
            import secrets as _sec
            for _k in dir(_sec):
                if not _k.startswith("_") and hasattr(_sec, _k):
                    _v = getattr(_sec, _k)
                    if _v is not None and _k not in _env:
                        _env[_k] = str(_v)
    except Exception:
        pass

# OS version. tools/deploy.py auto-bumps the PATCH number on every push.
# The literal MUST stay on its own line as `VERSION = "vN.N.N"` — the
# deploy regex relies on that exact format to rewrite in place.
VERSION           = "v1.4.103"
# ISO-date stamp of the current VERSION. Updated by tools/release.py
# (or by hand for hot-fix builds). Shown on the Updates page as the
# "Latest stable as of …" line when no newer release is available.
RELEASE_DATE      = "2026-05-16"

GITHUB_USER       = _env.get("GITHUB_USER", "")
DISPLAY_NAME      = _env.get("DISPLAY_NAME", "")
DESIGNATION       = _env.get("DESIGNATION", "")
LINKEDIN_USER     = _env.get("LINKEDIN_USER", "")
TWITTER_USER      = _env.get("TWITTER_USER", "")
WEBSITE_URL       = _env.get("WEBSITE_URL", "")

try:
    WEATHER_LAT = float(_env.get("WEATHER_LAT", 22.57) or 22.57)
except ValueError:
    WEATHER_LAT = 22.57
try:
    WEATHER_LON = float(_env.get("WEATHER_LON", 88.36) or 88.36)
except ValueError:
    WEATHER_LON = 88.36
WEATHER_NAME      = _env.get("WEATHER_NAME", "")
BT_AUTO_ENABLE    = False
try:
    TIMEZONE_OFFSET = float(_env.get("TIMEZONE_OFFSET", 5.5) or 5.5)
except ValueError:
    TIMEZONE_OFFSET = 5.5
SPOTIFY_CLIENT_ID = _env.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_RELAY_URL = _env.get("SPOTIFY_RELAY_URL", "https://oreo-delta.vercel.app")
SPOTIFY_AUTH_URL  = _env.get("SPOTIFY_AUTH_URL", "https://oreo-delta.vercel.app/spotify")
GITHUB_REPO       = _env.get("GITHUB_REPO", "elixpo/oreo")
GITHUB_API_URL    = _env.get("GITHUB_API_URL", "https://api.github.com")
OWM_API_URL       = _env.get("OWM_API_URL", "https://api.openweathermap.org")
NTP_HOST          = _env.get("NTP_HOST", "pool.ntp.org")
OTA_REPO          = _env.get("OTA_REPO", _env.get("GITHUB_REPO", "elixpo/oreo"))
STORE_REPO        = _env.get("STORE_REPO", _env.get("GITHUB_REPO", "elixpo/oreo"))
DEBUG             = _env.get("DEBUG", "1").lower() in ("1", "true", "yes")

def get(key, default=""):
    """Unified config & secrets getter across desktop emulator (.env) & hardware (secrets.py)."""
    if key in _env and _env[key] != "":
        val = _env[key]
        if isinstance(default, bool):
            return str(val).lower() in ("1", "true", "yes")
        return val
    val = globals().get(key, default)
    return default if val is None else val

def _split_csv(s):
    """Comma-separated env value → trimmed list. Empty entries dropped."""
    return [p.strip() for p in (s or "").split(",") if p.strip()]


# WIFI_SSID and WIFI_PASSWORD in .env are now CSV lists — parallel
# arrays. Example .env:
#     WIFI_SSID=home_net,elixpo_srv,office
#     WIFI_PASSWORD=homepass,srvpass,officepass
#
# WIFI_SSIDS / WIFI_PASSWORDS are the full lists. The singular
# WIFI_SSID / WIFI_PASSWORD constants below are the FIRST entry —
# kept for backward compatibility with any older code that read them
# directly. Boot-time wifi.py uses WIFI_NETWORKS (computed from
# both lists) and merges into /wifi.json on every boot.
WIFI_SSIDS        = _split_csv(_env.get("WIFI_SSID",     ""))
WIFI_PASSWORDS    = _split_csv(_env.get("WIFI_PASSWORD", ""))
WIFI_SSID         = WIFI_SSIDS[0]      if WIFI_SSIDS     else ""
WIFI_PASSWORD     = WIFI_PASSWORDS[0]  if WIFI_PASSWORDS else ""

# Zip into a list of network dicts. Priority is the .env order:
# first entry wins (priority=1), next is priority=2, etc. If the two
# lists are different lengths the extra SSIDs get an empty password
# (open network) and extra passwords are dropped.
WIFI_NETWORKS = []
for _i, _ssid in enumerate(WIFI_SSIDS):
    _pw = WIFI_PASSWORDS[_i] if _i < len(WIFI_PASSWORDS) else ""
    WIFI_NETWORKS.append({
        "ssid":     _ssid,
        "password": _pw,
        "priority": _i + 1,
        "metered":  False,
    })

OWM_API_KEY       = _env.get("OWM_API_KEY", "")
GH_TOKEN          = _env.get("GH_TOKEN", "")

WIFI_AUTO_CONNECT = True
WIFI_TX_DBM       = 11
WIFI_POWERSAVE    = True
BT_ADV_INTERVAL_MS = 500
APP_CATEGORIES = (
    ("Games",  "cat_games",  ("flappy", "snake", "racer", "pet", "doom")),
    ("GitHub", "cat_github", ("badge",  "identity", "commits")),
    ("Utils",  "cat_utils",  ("weather", "spotify")),
    ("Tools",  "cat_tools",  ("gallery", "Colors", "gamepad", "quest", "manager", "reader")),
    ("System", "cat_system", ("settings", "about", "store")),
)
