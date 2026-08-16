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
    orig_impl = getattr(sys, 'implementation', None)
    impl_dict = {k: getattr(orig_impl, k) for k in dir(orig_impl) if not k.startswith("__")} if orig_impl else {}
    impl_dict.update({
        'name': 'micropython',
        'version': (1, 22, 0),
        '_machine': 'ESP32S3 module (octal SPI) with ESP32S3'
    })
    sys.implementation = types.SimpleNamespace(**impl_dict)

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

    class MockPin:
        IN = 1
        OUT = 2
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
        def value(self, v=None):
            if v is not None:
                self._val = int(v)
            return self._val
        def on(self): self._val = 1
        def off(self): self._val = 0
        def irq(self, handler=None, trigger=0):
            self._handler = handler
            self._trigger = trigger

    class MockADC:
        ATTN_11DB = 3
        ATTN_6DB = 2
        ATTN_2_5DB = 1
        ATTN_0DB = 0
        def __init__(self, pin, atten=3):
            self.pin = pin
            self.atten_val = atten
        def read(self): return 2048
        def read_u16(self): return 32768
        def read_uv(self): return 1800000
        def atten(self, val): self.atten_val = val

    class MockPWM:
        def __init__(self, pin, freq=1000, duty=0, duty_u16=0):
            self.pin = pin
            self._freq = freq
            self._duty = duty
        def freq(self, f=None):
            if f is not None: self._freq = f
            return self._freq
        def duty(self, d=None):
            if d is not None: self._duty = d
            return self._duty
        def duty_u16(self, d=None):
            if d is not None: self._duty = d >> 6
            return self._duty << 6
        def deinit(self): pass

    class MockSPI:
        def __init__(self, id=0, baudrate=10000000, polarity=0, phase=0, sck=None, mosi=None, miso=None): pass
        def write(self, buf): pass
        def read(self, n, write=0): return bytearray(n)
        def readinto(self, buf, write=0): pass
        def write_readinto(self, write_buf, read_buf): pass

    class MockI2C:
        def __init__(self, id=0, scl=None, sda=None, freq=400000): pass
        def scan(self): return []
        def readfrom(self, addr, nbytes, stop=True): return bytearray(nbytes)
        def readfrom_into(self, addr, buf, stop=True): pass
        def writeto(self, addr, buf, stop=True): return len(buf)
        def readfrom_mem(self, addr, memaddr, nbytes, addrsize=8): return bytearray(nbytes)
        def writeto_mem(self, addr, memaddr, buf, addrsize=8): pass

    mock_m.Pin = MockPin
    mock_m.ADC = MockADC
    mock_m.PWM = MockPWM
    mock_m.SPI = MockSPI
    mock_m.I2C = MockI2C
    mock_m.SoftI2C = MockI2C

    # 4b. Patch esp32 module
    mock_esp32 = sys.modules.get('esp32') or types.ModuleType('esp32')
    sys.modules['esp32'] = mock_esp32

    class MockRMT:
        def __init__(self, channel=0, pin=None, clock_div=80, tx_carrier=None):
            self.channel = channel
            self.pin = pin
            self.clock_div = clock_div
            self.tx_carrier = tx_carrier
        def write_pulses(self, pulses, start_level=1): pass
        def wait_done(self, timeout=0): pass

    mock_esp32.RMT = MockRMT

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
