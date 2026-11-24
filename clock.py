# Wall-clock time as Unix seconds (UTC), shared by the booking code.
#
# The Pico's RTC starts at a made-up date on every boot, so the time is only
# trusted once it has been set: by NTP (see wifi.py) or, when the Pico has no
# internet (access-point mode), by the first browser that opens the web page.
#
# Works on MicroPython and on desktop Python.

import time

# Some MicroPython ports count seconds from 2000 instead of 1970.
_EPOCH_ADJ = 946684800 if time.gmtime(0)[0] == 2000 else 0
_offset = 0
synced = False


def now():
    """Current time in Unix seconds (UTC)."""
    return int(time.time()) + _EPOCH_ADJ + _offset


def set_time(unix_seconds):
    """Trust this time from now on (used when a browser supplies the time)."""
    global _offset, synced
    _offset = int(unix_seconds) - (int(time.time()) + _EPOCH_ADJ)
    synced = True


def mark_synced():
    """Call after the RTC itself has been set correctly (e.g. by NTP)."""
    global _offset, synced
    _offset = 0
    synced = True
