"""ESP32-S3 Hardware & MicroPython Environment Emulator for oreoSim.

Accurately emulates:
  • Target Frame Rate: 30 FPS (~33.3ms budget, matching ST7789 SPI bus bandwidth).
  • Memory Model: ESP32-S3 8MB Octal PSRAM with 8.0 MB MicroPython heap pool.
  • Storage Model: 16MB SPI Flash with 12.0 MB LittleFS partition (4KB block size).
  • MicroPython Runtime: gc.mem_free(), gc.mem_alloc(), gc.collect(), uos.statvfs, uos.uname, uos.ilistdir.
  • Hardware Clock: 240 MHz dual-core Xtensa LX7 (machine.freq() == 240000000).
  • Universal Path Normalization: Transparently maps LittleFS root paths (/apps, /oreoOS, etc.) to local repo.
  • Complete Hardware Mocks: Pin, ADC, PWM, SPI, I2C, RMT, WDT, RTC, Timer, NVS.
"""

import builtins
import gc
import os
import sys
import time
import types
from collections import namedtuple

# ── Hardware Specifications ───────────────────────────────────────────────────
TARGET_FPS = 30  # Real ST7789 SPI LCD transfer frame rate
FRAME_BUDGET_MS = 1000.0 / TARGET_FPS  # 33.33ms per frame
CPU_FREQ_HZ = 240_000_000  # 240 MHz Xtensa LX7

# Memory: 8.0 MB MicroPython Heap Pool on ESP32-S3 PSRAM
TOTAL_HEAP_BYTES = 8 * 1024 * 1024  # 8,388,608 bytes
BASE_OS_HEAP = 850 * 1024  # Core OS, fonts, theme base footprint

# Flash: 16 MB Flash with 12.0 MB LittleFS User Partition
FLASH_TOTAL_BYTES = 12 * 1024 * 1024  # 12,582,912 bytes
FLASH_BLOCK_SIZE = 4096  # 4 KB LittleFS block size
FLASH_TOTAL_BLOCKS = FLASH_TOTAL_BYTES // FLASH_BLOCK_SIZE  # 2048 blocks

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# ── Universal Path Normalization ──────────────────────────────────────────────
_DEVICE_ROOT_PREFIXES = (
    "badge_data",
    "apps",
    "apps_market",
    "assets",
    "oreoOS",
    "oreoWare",
    "oreoSim",
    "documents",
    "store_icons",
    "store_details",
)


def normalize_sim_path(path):
    """Map LittleFS absolute device paths (/apps/..., /state_*.json) to repo root."""
    if not isinstance(path, (str, bytes)):
        return path
    if isinstance(path, bytes):
        try:
            path_str = path.decode("utf-8")
            is_bytes = True
        except Exception:
            return path
    else:
        path_str = path
        is_bytes = False

    if path_str == "/" or path_str == "":
        res = REPO_ROOT
        return res.encode("utf-8") if is_bytes else res

    if path_str.startswith("/") and not path_str.startswith(REPO_ROOT):
        rel = path_str.lstrip("/")
        first_segment = rel.split("/")[0] if "/" in rel else rel
        if (
            first_segment in _DEVICE_ROOT_PREFIXES
            or first_segment.startswith("state_")
            or first_segment.startswith("store_")
            or first_segment.startswith(".tmp_")
            or first_segment.endswith(".json")
            or first_segment.endswith(".txt")
            or first_segment.endswith(".py")
            or os.path.exists(os.path.join(REPO_ROOT, rel))
        ):
            res = os.path.join(REPO_ROOT, rel)
            return res.encode("utf-8") if is_bytes else res

    return path


# ── Storage Emulation (LittleFS 8MB Partition) ──────────────────────────────────
def _calculate_project_used_bytes():
    """Calculate realistic disk usage by summing project files."""
    total_used = 0
    target_dirs = ["oreoOS", "apps", "apps_market", "assets"]
    for d in target_dirs:
        dp = os.path.join(REPO_ROOT, d)
        if os.path.exists(dp):
            for root, dirs, files in os.walk(dp):
                dirs[:] = [
                    dr for dr in dirs if dr not in ("__pycache__", ".venv", ".git", "node_modules")
                ]
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        sz = os.path.getsize(fp)
                        blocks = max(1, (sz + FLASH_BLOCK_SIZE - 1) // FLASH_BLOCK_SIZE)
                        total_used += blocks * FLASH_BLOCK_SIZE
                    except OSError:
                        pass
    total_used += 128 * 1024  # Reserved state / NVS buffer
    return min(FLASH_TOTAL_BYTES - (1024 * 1024), total_used)


def mock_statvfs(path="/"):
    """Simulate MicroPython os.statvfs('/') on ESP32-S3 8MB LittleFS partition."""
    used_bytes = _calculate_project_used_bytes()
    free_bytes = max(0, FLASH_TOTAL_BYTES - used_bytes)
    free_blocks = free_bytes // FLASH_BLOCK_SIZE
    _used_blocks = FLASH_TOTAL_BLOCKS - free_blocks

    return (
        FLASH_BLOCK_SIZE,  # f_bsize (4096)
        FLASH_BLOCK_SIZE,  # f_frsize (4096)
        FLASH_TOTAL_BLOCKS,  # f_blocks (2048)
        free_blocks,  # f_bfree
        free_blocks,  # f_bavail
        1024,  # f_files
        free_blocks,  # f_ffree
        free_blocks,  # f_favail
        0,  # f_flag
        255,  # f_namemax
    )


# ── Memory & Heap Emulation (4MB PSRAM MicroPython Heap) ──────────────────────
_allocated_heap = BASE_OS_HEAP


def mem_alloc():
    """Return currently allocated bytes in simulated MicroPython heap."""
    global _allocated_heap
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
UnameResult = namedtuple("UnameResult", ["sysname", "nodename", "release", "version", "machine"])


def uname():
    """Return MicroPython ESP32-S3 hardware uname tuple."""
    return UnameResult(
        sysname="esp32",
        nodename="esp32",
        release="1.28.0",
        version="v1.28.0 on 2026-08-15",
        machine="ESP32S3 module (octal SPI) with ESP32S3",
    )


# ── Hardware Emulation Setup ──────────────────────────────────────────────────
_orig_open = builtins.open
_orig_listdir = os.listdir
_orig_stat = os.stat
_orig_mkdir = os.mkdir
_orig_remove = os.remove
_orig_rmdir = os.rmdir
_orig_rename = os.rename


def setup_hardware_emulation():
    """Patch standard modules with realistic ESP32-S3 hardware mocks."""
    # 1. Patch sys attributes
    sys.platform = "esp32"
    orig_impl = getattr(sys, "implementation", None)
    impl_dict = (
        {k: getattr(orig_impl, k) for k in dir(orig_impl) if not k.startswith("__")}
        if orig_impl
        else {}
    )
    impl_dict.update(
        {
            "name": "micropython",
            "version": (1, 28, 0),
            "_machine": "ESP32S3 module (octal SPI) with ESP32S3",
        }
    )
    sys.implementation = types.SimpleNamespace(**impl_dict)

    def _mock_print_exception(exc, file=sys.stderr):
        import traceback

        traceback.print_exception(type(exc), exc, exc.__traceback__, file=file)

    sys.print_exception = _mock_print_exception

    # 2. Patch gc module
    gc.mem_free = mem_free
    gc.mem_alloc = mem_alloc
    gc.collect = collect
    gc.threshold = lambda *a: 0

    # 3. Patch builtins.open to intercept LittleFS root paths
    def mock_open(
        file,
        mode="r",
        buffering=-1,
        encoding=None,
        errors=None,
        newline=None,
        closefd=True,
        opener=None,
    ):
        normalized = normalize_sim_path(file)
        # Ensure parent directories exist on write
        if any(m in mode for m in ("w", "a", "+")) and isinstance(normalized, str):
            parent = os.path.dirname(normalized)
            if parent and not os.path.exists(parent):
                try:
                    os.makedirs(parent, exist_ok=True)
                except Exception:
                    pass
        return _orig_open(normalized, mode, buffering, encoding, errors, newline, closefd, opener)

    builtins.open = mock_open

    # 4. Patch os & uos functions with path normalization
    HOST_IGNORED = {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        ".gemini",
        ".pytest_cache",
        "build",
        "dist",
        "oreoSim",
        "tools",
        "oreo.elixpo",
    }

    def mock_listdir(path="."):
        norm_path = normalize_sim_path(path)
        try:
            raw_list = _orig_listdir(norm_path)
            return [
                entry
                for entry in raw_list
                if entry not in HOST_IGNORED and not entry.endswith(".pyc")
            ]
        except Exception:
            return []

    def mock_ilistdir(path="."):
        norm_path = normalize_sim_path(path)
        try:
            entries = _orig_listdir(norm_path)
            for e in entries:
                if e in HOST_IGNORED or e.endswith(".pyc"):
                    continue
                full = os.path.join(norm_path, e)
                is_dir = os.path.isdir(full)
                stat_res = _orig_stat(full)
                # (name, type, inode, size) - 0x4000 = dir, 0x8000 = file
                type_val = 0x4000 if is_dir else 0x8000
                yield (e, type_val, stat_res.st_ino, stat_res.st_size)
        except Exception:
            return

    def mock_stat(path):
        return _orig_stat(normalize_sim_path(path))

    def mock_mkdir(path, mode=0o777):
        return _orig_mkdir(normalize_sim_path(path), mode)

    def mock_remove(path):
        return _orig_remove(normalize_sim_path(path))

    def mock_rmdir(path):
        return _orig_rmdir(normalize_sim_path(path))

    def mock_rename(src, dst):
        return _orig_rename(normalize_sim_path(src), normalize_sim_path(dst))

    os.statvfs = mock_statvfs
    os.listdir = mock_listdir
    os.stat = mock_stat
    os.mkdir = mock_mkdir
    os.remove = mock_remove
    os.rmdir = mock_rmdir
    os.rename = mock_rename

    uos = types.ModuleType("uos")
    uos.statvfs = mock_statvfs
    uos.listdir = mock_listdir
    uos.ilistdir = mock_ilistdir
    uos.stat = mock_stat
    uos.mkdir = mock_mkdir
    uos.remove = mock_remove
    uos.rmdir = mock_rmdir
    uos.rename = mock_rename
    uos.uname = uname
    uos.urandom = lambda n: os.urandom(n)
    uos.dupterm = lambda *a, **k: None
    sys.modules["uos"] = uos

    # 5. Patch machine module
    mock_m = sys.modules.get("machine") or types.ModuleType("machine")
    sys.modules["machine"] = mock_m

    def _sim_reset():
        """Simulate hardware reset by cleanly restarting the emulator process."""
        print("\n\033[96m[oreoSim] machine.reset() called — rebooting OreoOS...\033[0m\n")
        try:
            import pygame

            pygame.display.quit()
            pygame.quit()
        except Exception:
            pass
        entry_cmd = getattr(sys, "_oreosim_entry_cmd", None) or (
            [sys.executable, os.path.abspath(sys.argv[0])] + sys.argv[1:]
        )
        os.execv(entry_cmd[0], entry_cmd)

    mock_m.freq = lambda: CPU_FREQ_HZ
    mock_m.reset = _sim_reset
    mock_m.reset_cause = lambda: 0
    mock_m.idle = lambda: time.sleep(0.001)
    mock_m.lightsleep = lambda ms=0: time.sleep(ms / 1000.0)
    mock_m.deepsleep = lambda ms=0: _sim_reset()
    mock_m.unique_id = lambda: b"\x24\x6f\x28\xab\xcd\xef"
    mock_m.BROWNOUT_RESET = 1
    mock_m.DEEPSLEEP_RESET = 2
    mock_m.PWRON_RESET = 0

    class MockPin:
        IN = 1
        OUT = 2
        OPEN_DRAIN = 3
        PULL_UP = 4
        PULL_DOWN = 8
        IRQ_RISING = 1
        IRQ_FALLING = 2

        def __init__(self, pin_id=0, mode=1, pull=-1, value=0):
            self.pin_id = pin_id
            self.mode = mode
            self.pull = pull
            self._val = value
            self._handler = None
            self._trigger = 0

        def init(self, mode=1, pull=-1, value=None):
            self.mode = mode
            self.pull = pull
            if value is not None:
                self._val = int(value)

        def value(self, v=None):
            if v is not None:
                self._val = int(v)
            return self._val

        def on(self):
            self._val = 1

        def off(self):
            self._val = 0

        def irq(self, handler=None, trigger=0):
            self._handler = handler
            self._trigger = trigger

    class MockADC:
        ATTN_11DB = 3
        ATTN_6DB = 2
        ATTN_2_5DB = 1
        ATTN_0DB = 0
        WIDTH_12BIT = 12

        def __init__(self, pin, atten=3):
            self.pin = pin
            self.atten_val = atten

        def read(self):
            return 2048

        def read_u16(self):
            return 32768

        def read_uv(self):
            return 1950000

        def atten(self, val):
            self.atten_val = val

        def width(self, val):
            pass

    class MockPWM:
        def __init__(self, pin, freq=1000, duty=0, duty_u16=0, duty_ns=0):
            self.pin = pin
            self._freq = freq
            self._duty = duty

        def freq(self, f=None):
            if f is not None:
                self._freq = f
            return self._freq

        def duty(self, d=None):
            if d is not None:
                self._duty = d
            return self._duty

        def duty_u16(self, d=None):
            if d is not None:
                self._duty = d >> 6
            return self._duty << 6

        def duty_ns(self, ns=None):
            pass

        def deinit(self):
            pass

    class MockSPI:
        def __init__(
            self, id=0, baudrate=10000000, polarity=0, phase=0, sck=None, mosi=None, miso=None
        ):
            pass

        def init(self, *a, **k):
            pass

        def deinit(self):
            pass

        def write(self, buf):
            pass

        def read(self, n, write=0):
            return bytearray(n)

        def readinto(self, buf, write=0):
            pass

        def write_readinto(self, write_buf, read_buf):
            pass

    class MockI2C:
        def __init__(self, id=0, scl=None, sda=None, freq=400000):
            pass

        def init(self, *a, **k):
            pass

        def deinit(self):
            pass

        def scan(self):
            return [0x68]  # Simulated MPU6050 / RTC address

        def readfrom(self, addr, nbytes, stop=True):
            return bytearray(nbytes)

        def readfrom_into(self, addr, buf, stop=True):
            pass

        def writeto(self, addr, buf, stop=True):
            return len(buf)

        def readfrom_mem(self, addr, memaddr, nbytes, addrsize=8):
            return bytearray(nbytes)

        def writeto_mem(self, addr, memaddr, buf, addrsize=8):
            pass

    class MockRTC:
        def __init__(self):
            pass

        def init(self, datetime):
            pass

        def datetime(self, val=None):
            t = time.localtime()
            # (year, month, day, weekday, hours, minutes, seconds, subseconds)
            return (t.tm_year, t.tm_mon, t.tm_mday, t.tm_wday, t.tm_hour, t.tm_min, t.tm_sec, 0)

    class MockWDT:
        def __init__(self, id=0, timeout=5000):
            self.timeout = timeout

        def feed(self):
            pass

    class MockTimer:
        ONE_SHOT = 0
        PERIODIC = 1

        def __init__(self, id=0):
            pass

        def init(self, mode=1, period=1000, callback=None):
            pass

        def deinit(self):
            pass

    mock_m.Pin = MockPin
    mock_m.ADC = MockADC
    mock_m.PWM = MockPWM
    mock_m.SPI = MockSPI
    mock_m.SoftSPI = MockSPI
    mock_m.I2C = MockI2C
    mock_m.SoftI2C = MockI2C
    mock_m.RTC = MockRTC
    mock_m.WDT = MockWDT
    mock_m.Timer = MockTimer

    # 6. Patch esp32 module
    mock_esp32 = sys.modules.get("esp32") or types.ModuleType("esp32")
    sys.modules["esp32"] = mock_esp32

    class MockRMT:
        def __init__(self, channel=0, pin=None, clock_div=80, tx_carrier=None):
            self.channel = channel
            self.pin = pin
            self.clock_div = clock_div
            self.tx_carrier = tx_carrier

        def write_pulses(self, pulses, start_level=1):
            pass

        def wait_done(self, timeout=0):
            pass

    class MockNVS:
        _storage = {}

        def __init__(self, namespace="oreo"):
            self.ns = namespace

        def set_i32(self, key, val):
            self._storage[f"{self.ns}:{key}"] = int(val)

        def get_i32(self, key):
            val = self._storage.get(f"{self.ns}:{key}")
            if val is None:
                raise OSError(2)
            return val

        def set_blob(self, key, val):
            self._storage[f"{self.ns}:{key}"] = bytes(val)

        def get_blob(self, key, buf):
            val = self._storage.get(f"{self.ns}:{key}")
            if val is None:
                raise OSError(2)
            buf[: len(val)] = val
            return len(val)

        def commit(self):
            pass

    mock_esp32.RMT = MockRMT
    mock_esp32.NVS = MockNVS
    mock_esp32.raw_temperature = lambda: 38.5
    mock_esp32.hall_sensor = lambda: 0

    # 7. Patch time module MicroPython ticks functions
    # MicroPython on ESP32 uses 30-bit ticks that wrap around.
    # ticks_diff handles this 30-bit wrapping with signed arithmetic.
    _SIM_START_TIME = time.time()
    time.ticks_ms = lambda: int((time.time() - _SIM_START_TIME) * 1000) & 0x3FFFFFFF
    time.ticks_us = lambda: int((time.time() - _SIM_START_TIME) * 1000000) & 0x3FFFFFFF
    time.ticks_cpu = lambda: int((time.time() - _SIM_START_TIME) * CPU_FREQ_HZ) & 0x3FFFFFFF

    def _ticks_diff(a, b):
        diff = (a - b) & 0x3FFFFFFF
        return diff if diff < 0x20000000 else diff - 0x40000000

    time.ticks_diff = _ticks_diff
    time.ticks_add = lambda a, b: (a + b) & 0x3FFFFFFF
    time.sleep_ms = lambda ms: time.sleep(ms / 1000.0)
    time.sleep_us = lambda us: time.sleep(us / 1000000.0)

    print("[oreoSim] ESP32-S3 Hardware Profile Loaded:")
    print(f"  • Display: ST7789 (320x240 @ {TARGET_FPS} FPS, {FRAME_BUDGET_MS:.1f}ms budget)")
    print(
        f"  • Heap: {TOTAL_HEAP_BYTES / (1024 * 1024):.1f} MB PSRAM ({mem_free() / 1024:.0f} KB free on boot)"
    )
    print(
        f"  • Flash: {FLASH_TOTAL_BYTES / (1024 * 1024):.1f} MB LittleFS ({mock_statvfs()[4] * 4 / 1024:.2f} MB free)"
    )
    print(f"  • CPU: {CPU_FREQ_HZ / 1_000_000:.0f} MHz Dual-Core Xtensa LX7\n")
