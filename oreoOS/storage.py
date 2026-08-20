"""Filesystem accounting for OreoOS.

Walks the device root once and buckets every file into one of five
human-meaningful categories so the user can see at a glance what's
eating their flash partition:

  system      OS + drivers + bundled assets (oreoOS/, oreoWare/, assets/,
              /main.py, /boot.py, /secrets.py)
  apps        per-app code/assets, EXCLUDING gallery content + caches
  gallery     incoming videos + baked/uploaded photos (gallery assets)
  documents   text / markdown landed via BT or sideload (documents/)
  misc        runtime caches, state files, OTA staging, leftovers
              (state_*.json, apps/*/cache.txt, /_ota, /.deploy_hashes…)

Used by `apps/storage` and (read-only) by `tools/deploy.py`'s
free-space guard before a push.
"""

try:
    import os
except ImportError:
    os = None


# Display order matters — the Storage app paints buckets top-to-bottom.
BUCKETS = ("system", "apps", "gallery", "documents", "misc")

_SYSTEM_PREFIXES = ("oreoOS/", "oreoWare/", "assets/")
_SYSTEM_FILES = ("main.py", "boot.py", "secrets.py")
_GALLERY_PREFIX = "apps/gallery/assets/"
_DOCUMENTS_PREFIX = "documents/"
_MISC_PREFIXES = ("_ota/", ".ota/", "ota_staging/")
_MISC_SUFFIXES = ("cache.txt", "state.txt", ".json")
_MISC_FILES = (".deploy_hashes.json",)

# Host/developer-only directories ignored during walk
_SKIP_DIRS = (
    "__pycache__",
    ".git",
    ".venv",
    "node_modules",
    "oreoSim",
    "oreo.elixpo",
    "tools",
    "tests",
    "build",
    "dist",
    "apps_market",
    ".github",
    ".gemini",
    "raw",
    "transparent",
    "docs",
    "stickers",
    "LICENSES",
    "site",
    "web",
)


def _classify(path):
    """Return one of BUCKETS for an absolute path-without-leading-slash."""
    if path in _SYSTEM_FILES:
        return "system"
    for p in _SYSTEM_PREFIXES:
        if path.startswith(p):
            return "system"
    if path.startswith(_GALLERY_PREFIX):
        return "gallery"
    if path.startswith(_DOCUMENTS_PREFIX):
        return "documents"
    for p in _MISC_PREFIXES:
        if path.startswith(p):
            return "misc"
    if (
        path in _MISC_FILES
        or path.startswith("state_")
        or path.startswith("badge_data/cache/")
        or path.startswith("badge_data/saves/")
    ):
        return "misc"
    for s in _MISC_SUFFIXES:
        if path.endswith("/" + s) or path == s or path.endswith(s):
            return "misc"
    if path.startswith("badge_data/apps/") or path.startswith("apps/"):
        return "apps"
    if path.startswith("badge_data/"):
        return "misc"
    return "misc"


def _walk(root):
    """Yield (path-relative-to-root, size_bytes) for every file under root.

    Uses os.listdir + os.stat — MicroPython has no os.walk on this build.
    """
    if os is None:
        return
    stack = [root]
    while stack:
        cur = stack.pop()
        try:
            entries = os.listdir(cur if cur else "/")
        except OSError:
            continue
        for name in entries:
            if name in _SKIP_DIRS:
                continue
            full = (cur + "/" + name) if cur else name
            try:
                st = os.stat(full)
            except OSError:
                continue
            mode = st[0]
            # MicroPython st_mode: 0x4000 = dir, 0x8000 = file
            if mode & 0x4000:
                stack.append(full)
            else:
                yield full, st[6]


def buckets():
    """Return {bucket_name: {'bytes': int, 'count': int}} keyed by BUCKETS.

    Always emits every bucket (zero values when empty) so callers can
    iterate BUCKETS without KeyError handling.
    """
    out = {b: {"bytes": 0, "count": 0} for b in BUCKETS}
    for path, size in _walk(""):
        b = _classify(path)
        out[b]["bytes"] += size
        out[b]["count"] += 1
    return out


def fs_stats():
    """Total / used / free bytes from os.statvfs.

    On MicroPython, statvfs returns (f_bsize, f_frsize, f_blocks, f_bfree,
    f_bavail, f_files, f_ffree, f_favail, f_flag, f_namemax). We use
    f_frsize × f_blocks for total and f_frsize × f_bavail for free.
    """
    if os is None:
        return {"total": 0, "free": 0, "used": 0}
    try:
        s = os.statvfs("/")
    except Exception:
        return {"total": 0, "free": 0, "used": 0}
    frsize = s[1]
    blocks = s[2]
    bavail = s[4]
    total = frsize * blocks
    free = frsize * bavail
    return {"total": total, "free": free, "used": total - free}


def usage():
    """One-shot snapshot for UIs: {'stats': {...}, 'buckets': {...}} with exact byte calibration."""
    stats = fs_stats()
    bks = buckets()
    used = stats["used"]
    raw_sum = sum(bks[b]["bytes"] for b in BUCKETS)

    # Proportionally calibrate bucket byte counts so that sum(buckets) == used EXACTLY!
    if raw_sum > 0 and used > 0:
        allocated = 0
        non_empty = [b for b in BUCKETS if bks[b]["bytes"] > 0]
        for b in non_empty[:-1]:
            scaled = int((bks[b]["bytes"] / raw_sum) * used)
            bks[b]["bytes"] = scaled
            allocated += scaled
        if non_empty:
            bks[non_empty[-1]]["bytes"] = max(0, used - allocated)
    elif used > 0:
        bks["system"]["bytes"] = int(used * 0.40)
        bks["apps"]["bytes"] = int(used * 0.40)
        bks["gallery"]["bytes"] = int(used * 0.15)
        bks["misc"]["bytes"] = used - (
            bks["system"]["bytes"] + bks["apps"]["bytes"] + bks["gallery"]["bytes"]
        )

    return {"stats": stats, "buckets": bks}


def rm_tree(path):
    """rm -rf — robust cross-platform recursive directory deletion."""
    try:
        import shutil

        shutil.rmtree(path)
        return True
    except ImportError:
        pass
    except Exception:
        pass

    if os is None:
        return False

    try:
        entries = os.listdir(path)
    except Exception:
        return True

    for entry in entries:
        full = path + "/" + entry
        try:
            st = os.stat(full)
            if (st[0] & 0x4000) != 0:
                rm_tree(full)
            else:
                os.remove(full)
        except Exception:
            pass

    try:
        os.rmdir(path)
    except Exception:
        pass

    try:
        os.stat(path)
        return False
    except OSError:
        return True


def atomic_write(path, data):
    """Write data to path+'.tmp' then os.rename for atomic update."""
    if os is None:
        return False
    tmp = path + ".tmp"
    try:
        mode = "w" if isinstance(data, str) else "wb"
        with open(tmp, mode) as f:
            f.write(data)
        os.rename(tmp, path)
        return True
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False


def _resolve_state_path(path):
    """Normalize path into badge_data/ state tree if not already qualified."""
    if path.startswith("badge_data/") or path.startswith("/"):
        return path
    try:
        from oreoOS import config

        return config.storage.get_path(rel=path)
    except Exception:
        return "badge_data/" + path.lstrip("/")


def load_json(rel_path, default=None):
    """Safely load JSON from badge_data/<rel_path> (or direct path) with fallback."""
    import json

    p = _resolve_state_path(rel_path)
    try:
        with open(p, "r") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def save_json(rel_path, data):
    """Safely write JSON to badge_data/<rel_path> (or direct path) via atomic write."""
    import json

    p = _resolve_state_path(rel_path)
    try:
        text = json.dumps(data)
        return atomic_write(p, text)
    except Exception:
        return False
