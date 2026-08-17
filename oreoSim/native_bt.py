"""Native Bluetooth Low Energy (BLE) mock for oreoSim.

Provides desktop emulation for:
  • BLE scanning (using Bleak when available, otherwise mock beacon generator)
  • BLE advertising and GATT services registration
  • oreoWare.bt compatibility
"""

import threading
import asyncio

_HAS_BLEAK = False
try:
    from bleak import BleakScanner
    _HAS_BLEAK = True
except Exception:
    _HAS_BLEAK = False

_loop = None
_thread = None

if _HAS_BLEAK:
    try:
        _loop = asyncio.new_event_loop()
        def _run_loop():
            asyncio.set_event_loop(_loop)
            _loop.run_forever()

        _thread = threading.Thread(target=_run_loop, daemon=True)
        _thread.start()
    except Exception:
        _HAS_BLEAK = False

_scan_results = []
_scan_lock = threading.Lock()
_is_scanning = False
_scanner = None
_active = False

def is_active():
    global _active
    return _active

def set_active(val):
    global _active
    _active = bool(val)

def active(val=None):
    global _active
    if val is not None:
        _active = bool(val)
    return _active

def init_from_config():
    pass

def _detection_callback(device, advertisement_data):
    with _scan_lock:
        name_bytes = advertisement_data.local_name.encode('utf-8') if advertisement_data.local_name else b''
        addr_bytes = device.address.encode('utf-8') if hasattr(device, 'address') else b'00:11:22:33:44:55'
        _scan_results.append((
            0,
            addr_bytes,
            0,
            advertisement_data.rssi if hasattr(advertisement_data, 'rssi') else -55,
            name_bytes
        ))

def start_scan():
    global _scan_results, _is_scanning, _scanner
    with _scan_lock:
        _scan_results = []
    if _is_scanning:
        return
    _is_scanning = True

    if _HAS_BLEAK and _loop:
        try:
            async def _do_start():
                global _scanner
                _scanner = BleakScanner(detection_callback=_detection_callback)
                await _scanner.start()

            asyncio.run_coroutine_threadsafe(_do_start(), _loop)
            return
        except Exception:
            pass

    # Fallback simulated badge peer discoveries for testing
    with _scan_lock:
        _scan_results.append((0, b'24:6F:28:11:22:33', 0, -48, b'OreoBadge_Alpha'))
        _scan_results.append((0, b'24:6F:28:44:55:66', 0, -62, b'OreoBadge_QuestPeer'))

def get_scan_results():
    with _scan_lock:
        res = list(_scan_results)
        _scan_results.clear()
    return res

def stop_scan():
    global _is_scanning, _scanner
    if not _is_scanning:
        return
    _is_scanning = False

    if _HAS_BLEAK and _loop and _scanner:
        try:
            async def _do_stop():
                global _scanner
                if _scanner:
                    await _scanner.stop()
                    _scanner = None

            asyncio.run_coroutine_threadsafe(_do_stop(), _loop)
        except Exception:
            pass

def start_advertising(name):
    pass

def stop_advertising():
    pass

def gatts_register_services(services):
    return ((10, 11, 12),)

def gatts_write(handle, data):
    pass

def gatts_notify(conn_handle, handle, data):
    pass

def gatts_set_buffer(handle, size, append=False):
    pass
