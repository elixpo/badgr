import threading
import asyncio
from bleak import BleakScanner

_loop = asyncio.new_event_loop()
def _run_loop():
    asyncio.set_event_loop(_loop)
    _loop.run_forever()

_thread = threading.Thread(target=_run_loop, daemon=True)
_thread.start()

_scan_results = []
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
    print("[NativeBT] Mocking init_from_config...")

def _detection_callback(device, advertisement_data):
    _scan_results.append((
        0,
        device.address.encode('utf-8'),
        0,
        advertisement_data.rssi,
        advertisement_data.local_name.encode('utf-8') if advertisement_data.local_name else b''
    ))

def start_scan():
    global _scan_results, _is_scanning, _scanner
    _scan_results = []
    if _is_scanning:
        return
    _is_scanning = True
    
    async def _do_start():
        global _scanner
        _scanner = BleakScanner(detection_callback=_detection_callback)
        await _scanner.start()
        
    asyncio.run_coroutine_threadsafe(_do_start(), _loop)

def get_scan_results():
    res = list(_scan_results)
    _scan_results.clear()
    return res

def stop_scan():
    global _is_scanning, _scanner
    if not _is_scanning:
        return
    _is_scanning = False
    
    async def _do_stop():
        global _scanner
        if _scanner:
            await _scanner.stop()
            _scanner = None
            
    asyncio.run_coroutine_threadsafe(_do_stop(), _loop)

def start_advertising(name):
    print(f"[NativeBT] Advertising as {name} (Stubbed)")

def stop_advertising():
    pass

def gatts_register_services(services):
    print("[NativeBT] Registering GATT Services (Stubbed)")
    return ((10, 11, 12),)

def gatts_write(handle, data):
    pass

def gatts_notify(conn_handle, handle, data):
    pass

def gatts_set_buffer(handle, size, append=False):
    pass
