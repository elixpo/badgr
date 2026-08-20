"""Time + NTP helpers shared by the home clock, Settings, and notif panel."""

_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = ("", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _get_tz_offset():
    try:
        from oreoOS import config

        return config.location.TIMEZONE_OFFSET
    except Exception:
        return 5.5


try:
    from datetime import datetime as _DT
    from datetime import timedelta as _TD
    from datetime import timezone as _TZ_OBJ

    def now():
        """Return (hour, minute, second, weekday_str, day, month_str, year) adjusted for timezone offset."""
        tz_offset = _get_tz_offset()
        utc_now = _DT.now(_TZ_OBJ.utc)
        local_now = utc_now + _TD(hours=tz_offset)
        return (
            local_now.hour,
            local_now.minute,
            local_now.second,
            _DAYS[local_now.weekday()],
            local_now.day,
            _MONTHS[local_now.month],
            local_now.year,
        )

except ImportError:
    import time as _t

    def now():
        """MicroPython timezone-adjusted local time tuple."""
        tz_offset = _get_tz_offset()
        t = _t.localtime(_t.time() + int(tz_offset * 3600))
        return (t[3], t[4], t[5], _DAYS[t[6]], t[2], _MONTHS[t[1]], t[0])


# ── NTP sync ────────────────────────────────────────────────────────────
_last_sync_status = "never"  # "never" | "ok" | "no-wifi" | "failed"
_last_sync_ts = 0  # epoch seconds of the last successful sync


def last_sync_status():
    return _last_sync_status


def last_sync_ts():
    return _last_sync_ts


# NTP epoch (1900-01-01) → MicroPython epoch (2000-01-01) offset.
_NTP_DELTA = 3155673600


def _ntp_raw(host="pool.ntp.org", port=123, timeout_s=2.5):
    """Single-shot NTP query via raw UDP with a hard socket timeout."""
    try:
        import socket as _socket
    except ImportError:
        return None
    s = None
    try:
        addr = _socket.getaddrinfo(host, port)[0][-1]
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        s.settimeout(timeout_s)
        pkt = bytearray(48)
        pkt[0] = 0x1B
        s.sendto(pkt, addr)
        data, _src = s.recvfrom(48)
        if len(data) < 48:
            return None
        secs = (data[40] << 24) | (data[41] << 16) | (data[42] << 8) | data[43]
        return secs - _NTP_DELTA
    except Exception:
        return None
    finally:
        try:
            if s is not None:
                s.close()
        except Exception:
            pass


def sync_from_ntp(timezone_offset_h=None):
    """Pull NTP time once, shift by the user's timezone offset, and write the RTC."""
    global _last_sync_status, _last_sync_ts

    try:
        from oreoWare import wifi

        if not wifi.is_connected():
            _last_sync_status = "no-wifi"
            return False, "no wifi"
    except Exception:
        pass

    try:
        from oreoOS import config

        host = config.location.NTP_HOST or "pool.ntp.org"
    except Exception:
        host = "pool.ntp.org"

    epoch_2000 = _ntp_raw(host=host)
    if epoch_2000 is None:
        _last_sync_status = "failed"
        return False, "ntp timeout"

    try:
        import time as _t

        import machine

        utc = _t.localtime(epoch_2000)
        machine.RTC().datetime((utc[0], utc[1], utc[2], utc[6] + 1, utc[3], utc[4], utc[5], 0))

        _last_sync_ts = _t.time()
        _last_sync_status = "ok"
        return True, "synced"
    except Exception as e:
        _last_sync_status = "failed"
        return False, (str(e) or "failed")[:20]
