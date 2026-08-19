"""OreoOS Centralized Configuration & Environment Provider.

Provides typed schema-backed access to environment variables (.env, .env.local),
embedded hardware secrets (secrets.py), and unified system constants across
desktop simulation and MicroPython hardware.
"""

import sys

# ── 1. Low-Level Environment & Hardware Secrets Hydration ────────────────────


def _load_env_file():
    env = {}
    for fname in (".env", ".env.local"):
        try:
            with open(fname, "r") as f:
                text = f.read()
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


_env = _load_env_file()

# On MicroPython embedded hardware where .env is absent, hydrate from hardware secrets.py
if not _env and sys.platform not in ("linux", "darwin", "win32"):
    try:
        import secrets as _sec

        for _k in dir(_sec):
            if not _k.startswith("_") and hasattr(_sec, _k):
                _v = getattr(_sec, _k)
                if _v is not None and _k not in _env:
                    _env[_k] = str(_v)
    except Exception:
        pass


# ── 2. Type-Safe Getter Provider ─────────────────────────────────────────────


def get(key, default=""):
    """Retrieve raw config value with fallback to default."""
    return _env.get(key, default)


def get_str(key, default=""):
    """Retrieve stripped string value."""
    val = _env.get(key)
    return str(val).strip() if val is not None and str(val).strip() != "" else default


def get_int(key, default=0):
    """Retrieve integer value with safe fallback."""
    val = _env.get(key)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def get_float(key, default=0.0):
    """Retrieve float value with safe fallback."""
    val = _env.get(key)
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def get_bool(key, default=False):
    """Retrieve boolean value."""
    val = _env.get(key)
    if val is None or val == "":
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def get_list(key, default=None):
    """Retrieve comma-separated string as a clean list of trimmed strings."""
    val = _env.get(key)
    if not val:
        return default if default is not None else []
    return [p.strip() for p in str(val).split(",") if p.strip()]


def get_custom_links():
    """Extract all agnostic LINK_<NAME> and SOCIAL_<NAME> custom channels."""
    links = []
    for k, v in _env.items():
        v_str = str(v).strip()
        if not v_str:
            continue
        if k.startswith("LINK_"):
            name = k[5:].replace("_", " ").title()
            links.append({"name": name, "url": v_str, "type": "link"})
        elif k.startswith("SOCIAL_"):
            name = k[7:].replace("_", " ").title()
            links.append({"name": name, "url": v_str, "type": "social"})
    return links


# ── 3. Namespaced Domain Schemas ──────────────────────────────────────────────


class _SystemConfig:
    VERSION = "v1.4.103"
    CODENAME = get_str("CODENAME", "Sweet Sandwich")
    RELEASE_DATE = "2026-08-18"
    DEV_BUILD = get_bool("DEV_BUILD", True)
    DEBUG = get_bool("DEBUG", True)
    OS_NAME = get_str("OS_NAME", "Oreo OS")

    @classmethod
    def get_version_string(cls):
        if cls.DEV_BUILD and not cls.VERSION.endswith("-dev"):
            return cls.VERSION + "-dev"
        return cls.VERSION


system = _SystemConfig()


class _WiFiConfig:
    SSIDS = get_list("WIFI_SSID", [])
    PASSWORDS = get_list("WIFI_PASSWORD", [])
    AUTO_CONNECT = get_bool("WIFI_AUTO_CONNECT", True)
    TX_DBM = get_int("WIFI_TX_DBM", 11)
    POWERSAVE = get_bool("WIFI_POWERSAVE", True)
    BT_ADV_INTERVAL_MS = get_int("BT_ADV_INTERVAL_MS", 500)
    BT_AUTO_ENABLE = get_bool("BT_AUTO_ENABLE", False)

    def __init__(self):
        nets = []
        for i, ssid in enumerate(self.SSIDS):
            pw = self.PASSWORDS[i] if i < len(self.PASSWORDS) else ""
            nets.append({"ssid": ssid, "password": pw, "priority": i + 1, "metered": False})
        self.NETWORKS = nets


wifi = _WiFiConfig()


class _LocationConfig:
    LAT = get_float("WEATHER_LAT", 22.57)
    LON = get_float("WEATHER_LON", 88.36)
    CITY = get_str("WEATHER_NAME", "")
    TIMEZONE_OFFSET = get_float("TIMEZONE_OFFSET", 5.5)
    NTP_HOST = get_str("NTP_HOST", "pool.ntp.org")


location = _LocationConfig()


class _WeatherConfig:
    API_KEY = get_str("OWM_API_KEY", "")
    API_URL = get_str("OWM_API_URL", "https://api.openweathermap.org")
    LAT = location.LAT
    LON = location.LON
    CITY = location.CITY


weather = _WeatherConfig()


class _GitHubConfig:
    USER = get_str("GITHUB_USER", "")
    TOKEN = get_str("GH_TOKEN", "")
    REPO = get_str("GITHUB_REPO", "elixpo/oreo")
    API_URL = get_str("GITHUB_API_URL", "https://api.github.com")
    OTA_REPO = get_str("OTA_REPO", get_str("GITHUB_REPO", "elixpo/oreo"))
    STORE_REPO = get_str("STORE_REPO", get_str("GITHUB_REPO", "elixpo/oreo"))
    STORE_REF = get_str("STORE_REF", "main")


github = _GitHubConfig()


class _SpotifyConfig:
    CLIENT_ID = get_str("SPOTIFY_CLIENT_ID", "")
    RELAY_URL = get_str("SPOTIFY_RELAY_URL", "https://oreo-delta.vercel.app")
    AUTH_URL = get_str("SPOTIFY_AUTH_URL", "https://oreo-delta.vercel.app/spotify")


spotify = _SpotifyConfig()


class _IdentityConfig:
    DISPLAY_NAME = get_str("DISPLAY_NAME", "")
    DESIGNATION = get_str("DESIGNATION", "")
    GITHUB = github.USER
    TWITTER = get_str("TWITTER_USER", get_str("X_USER", ""))
    LINKEDIN = get_str("LINKEDIN_USER", "")
    BLUESKY = get_str("BLUESKY_USER", "")
    NPM = get_str("NPM_USER", "")
    WEBSITE = get_str("WEBSITE_URL", "")
    EMAIL = get_str("EMAIL", "")

    @staticmethod
    def get_custom_links():
        return get_custom_links()


identity = _IdentityConfig()


class _StorageConfig:
    ROOT_DIR = "badge_data"
    APPS_DIR = "badge_data/apps"
    SAVES_DIR = "badge_data/saves"
    CACHE_DIR = "badge_data/cache"
    DOCUMENTS_DIR = "badge_data/documents"

    @classmethod
    def get_path(cls, sub="", rel=""):
        base = cls.ROOT_DIR + ("/" + sub.strip("/") if sub else "")
        return base + ("/" + rel.lstrip("/") if rel else "")

    @classmethod
    def ensure_dirs(cls):
        import os

        for p in (cls.ROOT_DIR, cls.APPS_DIR, cls.SAVES_DIR, cls.CACHE_DIR, cls.DOCUMENTS_DIR):
            try:
                os.stat(p)
            except OSError:
                try:
                    os.mkdir(p)
                except Exception:
                    pass


storage = _StorageConfig()

# Bootstrap badge data state directories on boot
storage.ensure_dirs()
