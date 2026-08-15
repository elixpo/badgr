import subprocess
import sys
import re

def _get_config_ssid():
    try:
        from oreoOS import config
        if getattr(config, "WIFI_NETWORKS", None):
            return config.WIFI_NETWORKS[0]["ssid"]
        if getattr(config, "WIFI_SSID", None):
            return config.WIFI_SSID
    except Exception:
        pass
    return "HostNetwork"

def _get_config_networks():
    try:
        from oreoOS import config
        if getattr(config, "WIFI_NETWORKS", None):
            return config.WIFI_NETWORKS
    except Exception:
        pass
    return [{"ssid": _get_config_ssid(), "password": "password", "priority": 1, "metered": False}]

_radio_on = True
_connected = True
_ssid = _get_config_ssid()
_ip = "192.168.1.100"
_rssi = -52
_power_mode = "balanced"
_saved_networks = _get_config_networks()

def is_radio_on():
    return _radio_on

def radio_on():
    global _radio_on
    _radio_on = True

def radio_off():
    global _radio_on, _connected
    _radio_on = False
    _connected = False

def is_connected():
    return _radio_on and _connected

def ip():
    if not is_connected(): return "0.0.0.0"
    try:
        import socket
        host_ip = socket.gethostbyname(socket.gethostname())
        if host_ip and not host_ip.startswith("127."):
            return host_ip
    except Exception:
        pass
    return "127.0.0.1"

def ssid():
    return _ssid if is_connected() else _get_config_ssid()

def rssi():
    return _rssi if is_connected() else None

def is_metered():
    return False

def get_power_mode():
    return _power_mode

def set_power_mode(mode):
    global _power_mode
    _power_mode = mode

def list_saved():
    return _get_config_networks()

def add_saved(ssid, password, priority=10, metered=False):
    _saved_networks.append({"ssid": ssid, "password": password, "priority": priority, "metered": metered})

def remove_saved(ssid):
    global _saved_networks
    _saved_networks = [n for n in _saved_networks if n.get("ssid") != ssid]

def info():
    current_s = ssid()
    if not is_connected():
        return {
            "connected": False, "radio_on": _radio_on,
            "ssid": None, "ip": None, "subnet": None,
            "gateway": None, "dns": None, "rssi": None
        }
    return {
        "connected": True, "radio_on": _radio_on,
        "ssid": current_s, "ip": ip(), "subnet": "255.255.255.0",
        "gateway": "192.168.1.1", "dns": "8.8.8.8", "rssi": _rssi
    }

def connect(ssid, pwd, timeout_ms=6000, pump_cb=None):
    global _connected, _ssid, _radio_on
    _radio_on = True
    _connected = True
    _ssid = ssid
    return True

def connect_from_config(pump_cb=None):
    return connect(_get_config_ssid(), "password")

def disconnect():
    global _connected
    _connected = False

def ping(host="8.8.8.8", port=53, timeout_s=2):
    return (True, 12)

def speed_test(bytes_=200000, timeout_s=10, pump_cb=None):
    return (True, 15400, 12)

def scan():
    networks = []
    platform = sys.platform

    try:
        if platform.startswith('linux'):
            output = subprocess.check_output(['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY', 'dev', 'wifi']).decode('utf-8')
            for line in output.split('\n'):
                if not line: continue
                parts = line.split(':')
                if len(parts) >= 3:
                    ssid = parts[0]
                    if not ssid: continue
                    rssi = int(parts[1]) - 100
                    sec = 3 if parts[2] and parts[2] != '--' else 0
                    networks.append((ssid, b'', 0, rssi, sec, 0))
        
        elif platform == 'darwin':
            airport = '/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport'
            output = subprocess.check_output([airport, '-s']).decode('utf-8')
            lines = output.split('\n')[1:]
            for line in lines:
                if not line: continue
                match = re.search(r'^\s*(.*?)\s+([0-9a-fA-F:]+)\s+(-?\d+)\s', line)
                if match:
                    ssid = match.group(1).strip()
                    rssi = int(match.group(3))
                    sec = 3 if 'WPA' in line or 'WEP' in line else 0
                    networks.append((ssid, b'', 0, rssi, sec, 0))
        
        elif platform == 'win32':
            output = subprocess.check_output(['netsh', 'wlan', 'show', 'networks', 'mode=bssid']).decode('utf-8', errors='ignore')
            current_ssid = None
            for line in output.split('\n'):
                line = line.strip()
                if line.startswith('SSID'):
                    parts = line.split(':')
                    if len(parts) > 1:
                        current_ssid = parts[1].strip()
                elif line.startswith('Signal'):
                    parts = line.split(':')
                    if len(parts) > 1 and current_ssid:
                        quality = int(parts[1].strip().replace('%', ''))
                        rssi = (quality / 2) - 100
                        networks.append((current_ssid, b'', 0, int(rssi), 3, 0))
                        current_ssid = None
    except Exception:
        networks.append(("HostNetwork", b'', 0, -50, 3, 0))

    return networks
