"""OreoOS Native Desktop Simulator (oreoSim) Entry Point & Hot-Reloader.

Provides:
  • Zero-latency local development environment for Oreo OS.
  • ESP32-S3 hardware emulation (30 FPS cap, 4MB PSRAM heap, 8MB LittleFS flash, 240MHz CPU).
  • Intelligent, debounced hot-reloader with AST syntax validation.
  • Active app state preservation across hot reloads.
  • Seamless CPython / MicroPython compatibility bridging.

Usage:
  python oreoSim/run.py                 # Boot into Home Screen with live hot-reload
  python oreoSim/run.py <app_name>      # Boot directly into a specific app (e.g. spotify, Colors, manager)
  python oreoSim/run.py --no-reload     # Run without hot-reloader watcher
  python oreoSim/run.py --scale=3       # Run at 3x window scale (960x720)
"""

import sys
import os
import types
import warnings
import time

warnings.filterwarnings("ignore", category=RuntimeWarning)

# 1. Add repo root to sys.path so oreoOS and apps can be imported
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
if os.path.dirname(__file__) not in sys.path:
    sys.path.insert(0, os.path.dirname(__file__))
os.chdir(repo_root)

# 2. Setup mock modules BEFORE importing oreoOS
import native_hardware
import native_wifi
import native_bt
import native_esp32

# 3. Setup accurate ESP32-S3 hardware & MicroPython mocks
native_esp32.setup_hardware_emulation()

import oreoWare

# Bind desktop simulator submodules
oreoWare.display = native_hardware
oreoWare.buttons = native_hardware
oreoWare.os = native_hardware
oreoWare.wifi = native_wifi
oreoWare.bt = native_bt

# Setup time and socket correctly for CPython
import socket
oreoWare.time = time
sys.modules['usocket'] = socket

sys.modules['oreoWare.display'] = native_hardware
sys.modules['oreoWare.buttons'] = native_hardware
sys.modules['oreoWare.os'] = native_hardware
sys.modules['oreoWare.wifi'] = native_wifi
sys.modules['oreoWare.bt'] = native_bt

# Parse CLI flags for scale
for arg in sys.argv[1:]:
    if arg.startswith("--scale="):
        try:
            scale_val = int(arg.split("=", 1)[1])
            native_hardware.ZOOM = scale_val
        except ValueError:
            pass

# ── Intelligent Hot-Reloader Engine ──────────────────────────────────────────
def _validate_syntax(filepath):
    """Check if modified Python file parses without syntax errors before reloading."""
    if not filepath.endswith('.py'):
        return True
    try:
        with open(filepath, 'rb') as f:
            source = f.read()
        compile(source, filepath, 'exec')
        return True
    except SyntaxError as e:
        print(f"\n\033[91m[HotReload] SyntaxError in {os.path.relpath(filepath, repo_root)} (Line {e.lineno}):\033[0m")
        print(f"\033[93m  --> {e.text.strip() if e.text else ''}\033[0m")
        print(f"\033[91m  {e.msg}\033[0m")
        print("\033[90m  (Simulator stays running. Fix syntax error and save to reload.)\033[0m\n")
        return False
    except Exception:
        return True

def _start_hot_reloader():
    import threading

    watch_dirs = [
        os.path.join(repo_root, 'oreoOS'),
        os.path.join(repo_root, 'oreoWare'),
        os.path.join(repo_root, 'badge_data', 'apps'),
        os.path.join(repo_root, 'apps'),
        os.path.join(repo_root, 'apps_market'),
        os.path.join(repo_root, 'assets'),
        os.path.join(repo_root, 'oreoSim'),
    ]

    IGNORED_DIRS = {
        '__pycache__', '.venv', '.git', 'node_modules', '.gemini',
        '.pytest_cache', 'shipready_results', 'dist', 'build',
        'store_icons', 'store_details', '.savegame', 'cache', 'saves'
    }

    def _get_files_snapshot():
        """Returns dict of {filepath: mtime} for all watched source files."""
        snapshot = {}
        for d in watch_dirs:
            if not os.path.exists(d):
                continue
            for root, dirs, files in os.walk(d):
                dirs[:] = [dr for dr in dirs if dr not in IGNORED_DIRS and not dr.startswith('.')]
                for f in files:
                    if f.startswith('.') or f.startswith('~') or f.endswith('.swp') or f.endswith('.tmp'):
                        continue
                    if (f.endswith('.py') or f == 'manifest.json') and not f.startswith('state_') and f != 'store_cache.json':
                        fp = os.path.join(root, f)
                        try:
                            snapshot[fp] = os.path.getmtime(fp)
                        except OSError:
                            pass
        # Also watch root configuration
        env_path = os.path.join(repo_root, '.env')
        if os.path.exists(env_path):
            try:
                snapshot[env_path] = os.path.getmtime(env_path)
            except OSError:
                pass
        return snapshot

    def _watch():
        prev_snapshot = _get_files_snapshot()

        while True:
            time.sleep(0.3)

            if getattr(sys, '_store_installing', False):
                prev_snapshot = _get_files_snapshot()
                continue

            curr_snapshot = _get_files_snapshot()

            changed_files = []
            for path, mtime in curr_snapshot.items():
                if path not in prev_snapshot or mtime > prev_snapshot[path]:
                    changed_files.append(path)

            if changed_files:
                # Debounce window (200ms) to ensure file writes have completely settled
                time.sleep(0.2)
                curr_snapshot = _get_files_snapshot()

                # Validate all modified Python files for syntax errors
                all_valid = True
                for cf in changed_files:
                    if not _validate_syntax(cf):
                        all_valid = False

                if all_valid:
                    rel_names = [os.path.relpath(p, repo_root) for p in changed_files[:3]]
                    name_str = ", ".join(rel_names) + ("..." if len(changed_files) > 3 else "")
                    print(f"\n\033[92m[HotReload] Change detected in {name_str} — reloading emulator...\033[0m\n")

                    try:
                        import pygame
                        pygame.display.quit()
                        pygame.quit()
                    except Exception:
                        pass

                    # Clean execv restart
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                else:
                    # Update snapshot so we don't spam errors on the same unchanged file
                    prev_snapshot = curr_snapshot

    t = threading.Thread(target=_watch, daemon=True)
    t.start()


if "--no-reload" not in sys.argv:
    _start_hot_reloader()


# ── Boot OreoOS ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    if not os.path.exists('.env'):
        print("\n\033[93m[WARNING] No .env file found! OreoOS will boot with default empty credentials.")
        print("          Apps like Spotify, GitHub, and Weather will not function properly.")
        print("          To fix this, run: cp .env.example .env and fill in your keys.\033[0m\n")
        time.sleep(1)

    from oreoOS import boot
    boot()
