"""ESP32-S3 Hardware & MicroPython Environment Emulator for oreoSim.

Accurately emulates:
  • Target Frame Rate: 30 FPS (~33.3ms budget, matching ST7789 SPI bus bandwidth).
  • Memory Model: ESP32-S3 8MB Octal PSRAM with 4.0 MB MicroPython heap pool.
  • Storage Model: 16MB SPI Flash with 8.0 MB LittleFS partition (4KB block size).
  • MicroPython Runtime: gc.mem_free(), gc.mem_alloc(), gc.collect(), uos.statvfs, uos.uname.
  • Hardware Clock: 240 MHz dual-core Xtensa LX7 (machine.freq() == 240000000).
"""

import os
import sys
import types
import time
import gc
from collections import namedtuple

# ── Hardware Specifications ───────────────────────────────────────────────────
TARGET_FPS = 30                    # Real ST7789 SPI LCD transfer frame rate
FRAME_BUDGET_MS = 1000.0 / TARGET_FPS  # 33.33ms per frame
CPU_FREQ_HZ = 240_000_000          # 240 MHz Xtensa LX7

# Memory: 4.0 MB MicroPython Heap Pool on ESP32-S3 PSRAM
TOTAL_HEAP_BYTES = 4 * 1024 * 1024  # 4,194,304 bytes
BASE_OS_HEAP = 850 * 1024           # Core OS, fonts, theme base footprint

# Flash: 16 MB Flash with 8.0 MB LittleFS User Partition
FLASH_TOTAL_BYTES = 8 * 1024 * 1024 # 8,388,608 bytes
FLASH_BLOCK_SIZE = 4096             # 4 KB LittleFS block size
FLASH_TOTAL_BLOCKS = FLASH_TOTAL_BYTES // FLASH_BLOCK_SIZE  # 2048 blocks

# ── Storage Emulation (LittleFS 8MB Partition) ──────────────────────────────────
def _calculate_project_used_bytes():
    """Calculate realistic disk usage by summing project files."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    total_used = 0
    target_dirs = ['oreoOS', 'apps', 'apps_market', 'assets']
    for d in target_dirs:
        dp = os.path.join(repo_root, d)
        if os.path.exists(dp):
            for root, _, files in os.walk(dp):
                if '__pycache__' in root or '.venv' in root or '.git' in root or 'node_modules' in root:
                    continue
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        sz = os.path.getsize(fp)
                        # Add LittleFS 4KB block alignment
                        blocks = max(1, (sz + FLASH_BLOCK_SIZE - 1) // FLASH_BLOCK_SIZE)
                        total_used += blocks * FLASH_BLOCK_SIZE
                    except OSError:
                        pass
    # Add reserved state files / NVS buffer (approx 128 KB)
    total_used += 128 * 1024
    return min(FLASH_TOTAL_BYTES - (1024 * 1024), total_used)

def mock_statvfs(path="/"):
    """Simulate MicroPython os.statvfs('/') on ESP32-S3 8MB LittleFS partition."""
    used_bytes = _calculate_project_used_bytes()
    free_bytes = max(0, FLASH_TOTAL_BYTES - used_bytes)
    free_blocks = free_bytes // FLASH_BLOCK_SIZE
    used_blocks = FLASH_TOTAL_BLOCKS - free_blocks
    
    # MicroPython statvfs tuple format:
    # (f_bsize, f_frsize, f_blocks, f_bfree, f_bavail, f_files, f_ffree, f_favail, f_flag, f_namemax)
    return (
        FLASH_BLOCK_SIZE,      # f_bsize
        FLASH_BLOCK_SIZE,      # f_frsize
        FLASH_TOTAL_BLOCKS,    # f_blocks (2048)
        free_blocks,           # f_bfree
        free_blocks,           # f_bavail
        1024,                  # f_files
        free_blocks,           # f_ffree
        free_blocks,           # f_favail
        0,                     # f_flag
        255                    # f_namemax
    )

# ── Memory & Heap Emulation (4MB PSRAM MicroPython Heap) ──────────────────────
_allocated_heap = BASE_OS_HEAP

def mem_alloc():
    """Return currently allocated bytes in simulated MicroPython heap."""
    global _allocated_heap
    # Approximate based on loaded modules, display surfaces, and app data
    extra = len(sys.modules) * 2048
    return min(TOTAL_HEAP_BYTES - (128 * 1024), _allocated_heap + extra)

def mem_free():
    """Return free bytes in simulated MicroPython heap."""
    used = mem_alloc()
    return max(64 * 1024, TOTAL_HEAP_BYTES - used)

_real_gc_collect = gc.collect

def collect():
    """Simulate MicroPython gc.collect() garbage collection cycle."""
    global _allocated_heap
    _real_gc_collect()
    reclaimed = 32 * 1024
    _allocated_heap = max(BASE_OS_HEAP, _allocated_heap - reclaimed)
    return reclaimed

# ── Hardware & System Identity (ESP32-S3) ─────────────────────────────────────
UnameResult = namedtuple('UnameResult', ['sysname', 'nodename', 'release', 'version', 'machine'])

def uname():
    """Return MicroPython ESP32-S3 hardware uname tuple."""
    return UnameResult(
        sysname='esp32',
        nodename='esp32',
        release='1.22.0',
        version='v1.22.0 on 2024-01-05',
        machine='ESP32S3 module (octal SPI) with ESP32S3'
    )

def setup_hardware_emulation():
    """Patch standard modules with realistic ESP32-S3 hardware mocks."""
    # 1. Patch sys attributes
    sys.platform = 'esp32'
    class _MicroPythonImpl:
        def __init__(self, orig):
            self.__dict__['_orig'] = orig
            self.name = 'micropython'
            self.version = (1, 22, 0)
            self._machine = 'ESP32S3 module (octal SPI) with ESP32S3'
        def __getattr__(self, name):
            return getattr(self._orig, name)
        def __repr__(self):
            return "namespace(name='micropython', version=(1, 22, 0))"
    sys.implementation = _MicroPythonImpl(sys.implementation)

    # 2. Patch gc module
    import gc
    gc.mem_free = mem_free
    gc.mem_alloc = mem_alloc
    gc.collect = collect

    # 3. Patch os / uos statvfs, listdir, stat, and uname
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    _orig_listdir = os.listdir
    _orig_stat = os.stat

    HOST_IGNORED = {'.git', '.venv', 'node_modules', '__pycache__', '.gemini', '.pytest_cache', 'build', 'dist', 'oreoSim', 'tools', 'oreo.elixpo'}

    def mock_listdir(path="."):
        raw_list = []
        if path == "/" or path == "" or path == "./":
            raw_list = _orig_listdir(repo_root)
        elif isinstance(path, str) and path.startswith("/") and not path.startswith(repo_root):
            target = os.path.join(repo_root, path.lstrip("/"))
            if os.path.exists(target):
                raw_list = _orig_listdir(target)
            else:
                raw_list = _orig_listdir(path)
        else:
            raw_list = _orig_listdir(path)
        return [entry for entry in raw_list if entry not in HOST_IGNORED and not entry.endswith('.pyc')]

    def mock_stat(path):
        if path == "/" or path == "":
            return _orig_stat(repo_root)
        if isinstance(path, str) and path.startswith("/") and not path.startswith(repo_root):
            target = os.path.join(repo_root, path.lstrip("/"))
            if os.path.exists(target):
                return _orig_stat(target)
        return _orig_stat(path)

    os.statvfs = mock_statvfs
    os.listdir = mock_listdir
    os.stat = mock_stat

    uos = types.ModuleType('uos')
    uos.statvfs = mock_statvfs
    uos.listdir = mock_listdir
    uos.stat = mock_stat
    uos.uname = uname
    sys.modules['uos'] = uos

    # 4. Patch machine module
    mock_m = sys.modules.get('machine') or types.ModuleType('machine')
    sys.modules['machine'] = mock_m
    mock_m.freq = lambda: CPU_FREQ_HZ
    mock_m.reset = lambda: sys.exit(0)
    mock_m.reset_cause = lambda: 0
    mock_m.BROWNOUT_RESET = 1
    mock_m.DEEPSLEEP_RESET = 2
    mock_m.PWRON_RESET = 0

    # 5. Patch time module for MicroPython ticks functions
    import time
    time.ticks_ms = lambda: int(time.time() * 1000)
    time.ticks_diff = lambda a, b: a - b
    time.ticks_add = lambda a, b: a + b
    time.sleep_ms = lambda ms: time.sleep(ms / 1000.0)
    time.sleep_us = lambda us: time.sleep(us / 1000000.0)

    print(f"[oreoSim] ESP32-S3 Hardware Profile Loaded:")
    print(f"  • Display: ST7789 (320x240 @ {TARGET_FPS} FPS, {FRAME_BUDGET_MS:.1f}ms budget)")
    print(f"  • Heap: {TOTAL_HEAP_BYTES / (1024*1024):.1f} MB PSRAM ({mem_free() / 1024:.0f} KB free on boot)")
    print(f"  • Flash: {FLASH_TOTAL_BYTES / (1024*1024):.1f} MB LittleFS ({mock_statvfs()[4] * 4 / 1024:.2f} MB free)")
    print(f"  • CPU: {CPU_FREQ_HZ / 1_000_000:.0f} MHz Dual-Core Xtensa LX7\n")
