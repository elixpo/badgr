"""Native WiFi and urequests networking mock for oreoSim.

Provides high-fidelity emulation for:
  • oreoWare.wifi subsystem
  • urequests MicroPython HTTP client (get, post, put, delete, head, patch)
  • network.WLAN MicroPython interface (STA_IF, AP_IF)
"""

import re
import socket
import subprocess
import sys
import time
import types


def _get_config_ssid():
    try:
        from oreoOS import config

        if getattr(config, "wifi", None) and getattr(config.wifi, "NETWORKS", None):
            return config.wifi.NETWORKS[0]["ssid"]
        if getattr(config, "wifi", None) and getattr(config.wifi, "SSIDS", None):
            return config.wifi.SSIDS[0] if config.wifi.SSIDS else ""
    except Exception:
        pass
    return "HostNetwork"


def _get_config_networks():
    try:
        from oreoOS import config

        if getattr(config, "wifi", None) and getattr(config.wifi, "NETWORKS", None):
            return config.wifi.NETWORKS
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
    if not is_connected():
        return "0.0.0.0"
    try:
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
    _saved_networks.append(
        {"ssid": ssid, "password": password, "priority": priority, "metered": metered}
    )


def remove_saved(ssid):
    global _saved_networks
    _saved_networks = [n for n in _saved_networks if n.get("ssid") != ssid]


def info():
    current_s = ssid()
    if not is_connected():
        return {
            "connected": False,
            "radio_on": _radio_on,
            "ssid": None,
            "ip": None,
            "subnet": None,
            "gateway": None,
            "dns": None,
            "rssi": None,
        }
    return {
        "connected": True,
        "radio_on": _radio_on,
        "ssid": current_s,
        "ip": ip(),
        "subnet": "255.255.255.0",
        "gateway": "192.168.1.1",
        "dns": "8.8.8.8",
        "rssi": _rssi,
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
        if platform.startswith("linux"):
            output = subprocess.check_output(
                ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi"],
                stderr=subprocess.DEVNULL,
            ).decode("utf-8", errors="ignore")
            for line in output.split("\n"):
                if not line:
                    continue
                parts = line.split(":")
                if len(parts) >= 3:
                    ssid = parts[0]
                    if not ssid:
                        continue
                    rssi = int(parts[1]) - 100
                    sec = 3 if parts[2] and parts[2] != "--" else 0
                    networks.append((ssid, b"", 0, rssi, sec, 0))
        elif platform == "darwin":
            airport = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
            output = subprocess.check_output([airport, "-s"], stderr=subprocess.DEVNULL).decode(
                "utf-8", errors="ignore"
            )
            lines = output.split("\n")[1:]
            for line in lines:
                if not line:
                    continue
                match = re.search(r"^\s*(.*?)\s+([0-9a-fA-F:]+)\s+(-?\d+)\s", line)
                if match:
                    ssid = match.group(1).strip()
                    rssi = int(match.group(3))
                    sec = 3 if "WPA" in line or "WEP" in line else 0
                    networks.append((ssid, b"", 0, rssi, sec, 0))
        elif platform == "win32":
            output = subprocess.check_output(
                ["netsh", "wlan", "show", "networks", "mode=bssid"], stderr=subprocess.DEVNULL
            ).decode("utf-8", errors="ignore")
            current_ssid = None
            for line in output.split("\n"):
                line = line.strip()
                if line.startswith("SSID"):
                    parts = line.split(":")
                    if len(parts) > 1:
                        current_ssid = parts[1].strip()
                elif line.startswith("Signal"):
                    parts = line.split(":")
                    if len(parts) > 1 and current_ssid:
                        quality = int(parts[1].strip().replace("%", ""))
                        rssi = (quality / 2) - 100
                        networks.append((current_ssid, b"", 0, int(rssi), 3, 0))
                        current_ssid = None
    except Exception:
        pass

    if not networks:
        networks.append(("HostNetwork", b"", 0, -50, 3, 0))
        networks.append(("OreoBadge_Guest", b"", 0, -68, 0, 0))

    return networks


# ── MicroPython urequests Mock ───────────────────────────────────────────────
class _MockResponse:
    def __init__(self, req_res):
        self._res = req_res
        self.status_code = req_res.status_code
        self.reason = req_res.reason
        self.headers = dict(req_res.headers)
        self.encoding = req_res.encoding or "utf-8"
        self._content = None

    @property
    def content(self):
        if self._content is None:
            self._content = self._res.content
        return self._content

    @property
    def text(self):
        return self._res.text

    def json(self):
        return self._res.json()

    def close(self):
        try:
            self._res.close()
        except Exception:
            pass


def _setup_urequests():
    try:
        import requests
    except ImportError:
        requests = None

    ureq = types.ModuleType("urequests")

    def _do_request(method, url, **kwargs):
        if requests is None:
            raise RuntimeError("Python 'requests' package required for oreoSim urequests mock")
        # Map micro-python parameters
        data = kwargs.pop("data", None)
        json_data = kwargs.pop("json", None)
        headers = kwargs.pop("headers", {})
        timeout = kwargs.pop("timeout", 8.0)
        res = requests.request(
            method, url, data=data, json=json_data, headers=headers, timeout=timeout, **kwargs
        )
        return _MockResponse(res)

    ureq.request = _do_request
    ureq.get = lambda url, **k: _do_request("GET", url, **k)
    ureq.post = lambda url, **k: _do_request("POST", url, **k)
    ureq.put = lambda url, **k: _do_request("PUT", url, **k)
    ureq.delete = lambda url, **k: _do_request("DELETE", url, **k)
    ureq.head = lambda url, **k: _do_request("HEAD", url, **k)
    ureq.patch = lambda url, **k: _do_request("PATCH", url, **k)

    sys.modules["urequests"] = ureq


# ── MicroPython network Module Mock ─────────────────────────────────────────
def _setup_network():
    net = types.ModuleType("network")
    net.STA_IF = 0
    net.AP_IF = 1
    net.STAT_IDLE = 1000
    net.STAT_CONNECTING = 1001
    net.STAT_WRONG_PASSWORD = 202
    net.STAT_NO_AP_FOUND = 201
    net.STAT_CONNECT_FAIL = 203
    net.STAT_GOT_IP = 1010

    class MockWLAN:
        def __init__(self, interface_id=0):
            self.if_id = interface_id
            self._active = True
            self._connected = True

        def active(self, is_act=None):
            if is_act is not None:
                self._active = bool(is_act)
            return self._active

        def isconnected(self):
            return self._active and self._connected

        def connect(self, ssid=None, key=None):
            self._active = True
            self._connected = True

        def disconnect(self):
            self._connected = False

        def status(self, param=None):
            return net.STAT_GOT_IP if self.isconnected() else net.STAT_IDLE

        def ifconfig(self, config=None):
            return (ip(), "255.255.255.0", "192.168.1.1", "8.8.8.8")

        def scan(self):
            return scan()

        def config(self, *args, **kwargs):
            if "mac" in args:
                return b"\x24\x6f\x28\xab\xcd\xef"
            if "essid" in kwargs:
                return kwargs["essid"]
            return "HostNetwork"

    net.WLAN = MockWLAN
    sys.modules["network"] = net


_setup_urequests()
_setup_network()
