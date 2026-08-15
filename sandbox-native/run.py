import sys
import os
import types
import warnings

warnings.filterwarnings("ignore", category=RuntimeWarning)

# 1. Add repo root to sys.path so oreoOS can be imported
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
os.chdir(repo_root)

# 2. Setup mock modules BEFORE importing oreoOS
import native_hardware
import native_wifi
import native_bt

_oreoware = types.ModuleType('oreoWare')

# Bind submodules
_oreoware.display = native_hardware
_oreoware.buttons = native_hardware
_oreoware.os = native_hardware
_oreoware.wifi = native_wifi
_oreoware.bt = native_bt

# Setup time and socket correctly for CPython
import time
import socket
import urllib.request
import gc
_oreoware.time = time
time.ticks_ms = lambda: int(time.time() * 1000)
time.ticks_diff = lambda a, b: a - b
time.sleep_ms = lambda ms: time.sleep(ms / 1000.0)
gc.mem_free = lambda: 4 * 1024 * 1024
gc.mem_alloc = lambda: 1024 * 1024
sys.modules['usocket'] = socket

mock_machine = types.ModuleType('machine')
mock_machine.reset = lambda: sys.exit(0)
mock_machine.reset_cause = lambda: 0
mock_machine.BROWNOUT_RESET = 1
mock_machine.DEEPSLEEP_RESET = 2
class MockRTC:
    def datetime(self, *a): pass
mock_machine.RTC = MockRTC
sys.modules['machine'] = mock_machine
sys.modules['urequests'] = types.ModuleType('urequests')
def _mock_get(url, *args, **kwargs):
    import requests
    return requests.get(url, *args, **kwargs)
sys.modules['urequests'].get = _mock_get

sys.modules['oreoWare'] = _oreoware
sys.modules['oreoWare.display'] = native_hardware
sys.modules['oreoWare.buttons'] = native_hardware
sys.modules['oreoWare.os'] = native_hardware
sys.modules['oreoWare.wifi'] = native_wifi
sys.modules['oreoWare.bt'] = native_bt

def _start_hot_reloader():
    import threading, time, os, sys
    
    def _watch():
        watch_dirs = [
            os.path.join(repo_root, 'oreoOS'),
            os.path.join(repo_root, 'apps'),
            os.path.join(repo_root, 'assets'),
            os.path.join(repo_root, 'sandbox-native')
        ]
        
        STOCK_APPS = {
            'about', 'badge', 'bt', 'commits', 'flappy', 'gallery',
            'gamepad', 'gestures', 'identity', 'launcher', 'quest',
            'racer', 'reader', 'settings', 'snake', 'storage',
            'store', 'updates', 'weather', 'wifi'
        }
        
        def _get_max_mtime():
            max_m = 0
            for d in watch_dirs:
                if not os.path.exists(d): continue
                for root, dirs, files in os.walk(d):
                    rel = os.path.relpath(root, repo_root)
                    if rel == "apps":
                        dirs[:] = [sub for sub in dirs if sub in STOCK_APPS]
                    for f in files:
                        if f.endswith('.py'):
                            try:
                                m = os.path.getmtime(os.path.join(root, f))
                                if m > max_m: max_m = m
                            except OSError: pass
            return max_m

        initial_mtime = _get_max_mtime()
        while True:
            time.sleep(0.5)
            curr = _get_max_mtime()
            if curr > initial_mtime:
                print("\n[HotReload] File change detected! Hot-reloading native emulator...\n")
                try:
                    import pygame
                    pygame.quit()
                except Exception: pass
                os.execv(sys.executable, [sys.executable] + sys.argv)
                
    t = threading.Thread(target=_watch, daemon=True)
    t.start()

_start_hot_reloader()

# 3. Boot OS
if __name__ == '__main__':
    from oreoOS import boot
    boot()
