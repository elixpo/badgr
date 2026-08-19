"""OreoOS Persistent User Settings Engine.

Manages mutable user settings (themes, gestures, UI modes, network preferences)
with fast in-memory caching and crash-safe atomic persistence to
`badge_data/saves/settings.json`.
"""

try:
    import json
except ImportError:
    import ujson as json

import os

SETTINGS_FILE = "badge_data/saves/settings.json"
_cache = None
_dirty = False


def _ensure_dir(path):
    parts = path.rstrip("/").split("/")
    cur = ""
    for p in parts:
        if not p:
            continue
        cur = cur + "/" + p if cur else p
        try:
            os.stat(cur)
        except OSError:
            try:
                os.mkdir(cur)
            except Exception:
                pass


def _load():
    global _cache
    if _cache is not None:
        return _cache
    _cache = {}
    try:
        with open(SETTINGS_FILE, "r") as f:
            data = json.loads(f.read())
            if isinstance(data, dict):
                _cache = data
    except Exception:
        _cache = {}
    return _cache


def get(key, default=None):
    """Retrieve a setting by key, returning default if not found."""
    cache = _load()
    return cache.get(key, default)


def set(key, value, persist=True):
    """Update a setting. If persist is True, writes immediately to flash."""
    global _dirty
    cache = _load()
    if cache.get(key) != value:
        cache[key] = value
        _dirty = True
        if persist:
            save()


def delete(key, persist=True):
    """Remove a setting by key."""
    global _dirty
    cache = _load()
    if key in cache:
        del cache[key]
        _dirty = True
        if persist:
            save()


def all():
    """Return a shallow copy of all currently loaded settings."""
    return dict(_load())


def save():
    """Flush pending setting changes atomically to disk."""
    global _dirty
    cache = _load()
    _ensure_dir("badge_data/saves")
    try:
        from oreoOS import storage

        storage.atomic_write(SETTINGS_FILE, json.dumps(cache))
        _dirty = False
        return True
    except Exception:
        try:
            tmp = SETTINGS_FILE + ".tmp"
            with open(tmp, "w") as f:
                f.write(json.dumps(cache))
            try:
                os.remove(SETTINGS_FILE)
            except OSError:
                pass
            os.rename(tmp, SETTINGS_FILE)
            _dirty = False
            return True
        except Exception:
            return False


def reload():
    """Force reload of settings from disk, discarding unsaved memory cache."""
    global _cache, _dirty
    _cache = None
    _dirty = False
    return _load()
