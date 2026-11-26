# Wi-Fi for the Pico W.
#
# Joins the network in secrets.py. If there is no secrets.py, or joining
# fails, the Pico starts its own access point instead so the booking page is
# still reachable (connect to it and open http://192.168.4.1). While the access
# point is up, retry_station() keeps trying the network from secrets.py in the
# background, so a phone hotspot switched on after boot is still picked up.
#
# The network name is matched loosely: an iPhone hotspot is called
# "Umar’s iPhone" with a curly apostrophe, which is easy to type as a straight
# ' in secrets.py. The exact name the Pico sees in its scan is used to join.

import network
import time
import clock

try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

# Your own hotspot name and password go in secrets.py, NOT here.
# The values below only matter when the Pico makes its OWN Wi-Fi network
# (no secrets.py, or it couldn't join yours).
AP_SSID = "SmartParking"        # CHANGE (optional): name of the Pico's own Wi-Fi network
AP_PASSWORD = "parking123"      # CHANGE (optional): its password, 8+ characters, or None for no password
AP_CHANNEL = 6                  # 2.4 GHz channel 1-11 for the Pico's own network; 1, 6 or 11 are best
CONNECT_TIMEOUT_S = 20          # seconds to wait for the hotspot before giving up (x2 attempts)
DHCP_EXTRA_S = 20               # extra wait once joined but still waiting for an IP address
RETRY_EVERY_S = 60              # while on its own network, retry your hotspot this often (seconds)

# The Pico W scan reports security as bit flags: 1 = encrypted, 2 = WPA, 4 = WPA2.
# So 5 = WPA2, 7 = WPA/WPA2 mixed. WPA3 is NOT reported separately (it shows as 5).
SECURITY = {0: "open", 1: "WEP", 3: "WPA", 5: "WPA2", 7: "WPA/WPA2"}

REASONS = {
    getattr(network, "STAT_WRONG_PASSWORD", -3): "wrong password",
    getattr(network, "STAT_NO_AP_FOUND", -2): "network not found",
    getattr(network, "STAT_CONNECT_FAIL", -1): "connection failed",
    0: "idle",
    1: "joining",
    2: "joined, waiting for an IP address",
    3: "connected",
}

mode = None               # "sta" when on the network from secrets.py, "ap" for own access point


# ---------------- helpers ----------------
def _norm(s):
    """Loose form of a network name: lower case, straight quotes, single spaces."""
    s = str(s)
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"')):
        s = s.replace(a, b)
    return " ".join(s.lower().split())


def _ssid(net):
    return net[0].decode("utf-8", "ignore")


def load_secrets():
    """(ssid, password, secrets module) or None if there is no usable secrets.py."""
    try:
        import secrets
        return secrets.WIFI_SSID, secrets.WIFI_PASSWORD, secrets
    except (ImportError, AttributeError):
        return None


def scan(sta, tries=3):
    """Scan for networks. The first scan after switching Wi-Fi on often comes
    back empty because the radio is still starting, so retry a few times."""
    for i in range(tries):
        try:
            nets = sta.scan()
        except Exception as e:
            print("Wi-Fi scan failed:", e)
            nets = []
        if nets:
            return nets
        if i < tries - 1:
            time.sleep_ms(1500)
    return []


def match(nets, ssid):
    """Find `ssid` in a scan. Returns (net, exact) or (None, False)."""
    for n in nets:
        if _ssid(n) == ssid:
            return n, True
    want = _norm(ssid)
    for n in nets:
        if _norm(_ssid(n)) == want:
            return n, False
    return None, False


def _report_scan(nets, ssid):
    """Print whether the network is visible, and its signal and security."""
    if not nets:
        print("  Scan found no networks at all (the radio may still be busy)")
        return
    n, exact = match(nets, ssid)
    if n:
        print("  Found %r: channel %d, signal %d dBm, security %s%s"
              % (_ssid(n), n[2], n[3], SECURITY.get(n[4], n[4]),
                 "" if exact else " (name differs from secrets.py %r)" % ssid))
        if n[3] < -80:
            print("  Signal is weak, move the Pico closer")
        if n[4] in (0, 1):
            print("  Open/WEP network: make sure the hotspot uses WPA2-Personal")
        return
    print("  %r not visible. It must be 2.4 GHz (iPhone: turn on Maximise Compatibility)" % ssid)
    print("  and, on iPhone, keep the Personal Hotspot screen open. Networks seen:")
    for n in sorted(nets, key=lambda n: -n[3])[:8]:
        print("    %r %d dBm %s" % (_ssid(n) or "(hidden)", n[3], SECURITY.get(n[4], n[4])))


def _set_country(sec):
    # Wi-Fi country (2-letter code) decides the allowed channels, e.g. "PK", "GB", "US".
    country = getattr(sec, "WIFI_COUNTRY", None)
    if not country:
        return
    try:
        network.country(country)
    except Exception:
        try:
            import rp2
            rp2.country(country)
        except Exception as e:
            print("Could not set Wi-Fi country:", e)


def _prepare_sta(sec):
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    try:
        sta.config(pm=0xa11140)   # turn off Wi-Fi power saving, more reliable
    except Exception:
        pass
    static = getattr(sec, "WIFI_STATIC", None)
    if static:
        sta.ifconfig(tuple(static))
        print("Using fixed IP", static[0])
    return sta


def resolve_ssid(sta, ssid):
    """Return the exact name to join (from a scan if it matches loosely), and the scan."""
    print("Wi-Fi: scanning for %r..." % ssid)
    nets = scan(sta)
    n, exact = match(nets, ssid)
    print("Wi-Fi: %d networks seen, %r %s" % (len(nets), ssid, "found" if n else "NOT visible"))
    if n and not exact:
        print("Using exact network name %r (secrets.py has %r)" % (_ssid(n), ssid))
        return _ssid(n), nets
    return ssid, nets


def _sync_time():
    try:
        import ntptime
        ntptime.settime()       # sets the RTC to UTC
        clock.mark_synced()
        print("Clock set from NTP")
    except Exception as e:
        print("NTP failed, the first browser to connect will set the clock:", e)


def _start_ap():
    global mode
    # Make sure the station side is fully off; a half-finished join attempt
    # can stop phones from joining the access point.
    sta = network.WLAN(network.STA_IF)
    try:
        sta.disconnect()
    except Exception:
        pass
    sta.active(False)
    time.sleep_ms(500)

    ap = network.WLAN(network.AP_IF)
    ap.active(False)
    if AP_PASSWORD:
        ap.config(essid=AP_SSID, password=AP_PASSWORD, channel=AP_CHANNEL)
    else:
        ap.config(essid=AP_SSID, security=0, channel=AP_CHANNEL)   # open network
    ap.active(True)
    while not ap.active():
        time.sleep_ms(100)
    try:
        ap.config(pm=0xa11140)   # power saving off, so phones can join reliably
    except Exception:
        pass
    ip = ap.ifconfig()[0]
    mode = "ap"
    print("Access point '%s' started (%s), open http://%s"
          % (ap.config("essid"), ("password " + AP_PASSWORD) if AP_PASSWORD else "no password", ip))
    return ip


# ---------------- joining ----------------
def _try_join(sta, ssid, password, attempt=1):
    sta.connect(ssid, password)
    print("Wi-Fi: connecting to %r (attempt %d of 2)" % (ssid, attempt))
    waited, limit, last = 0, CONNECT_TIMEOUT_S * 2, None
    while waited < limit:
        s = sta.status()
        if s != last:                       # one full line per status change
            print("  %3d s  %s" % (waited // 2, REASONS.get(s, "status %s" % s)))
            last = s
        if sta.isconnected() or s < 0:
            break
        if s == 2 and limit == CONNECT_TIMEOUT_S * 2:
            limit += DHCP_EXTRA_S * 2      # joined, give the hotspot longer to hand out an IP
        time.sleep_ms(500)
        waited += 1
        if waited % 10 == 0:
            print("  %3d s  still waiting..." % (waited // 2))
    return sta.isconnected()


def _explain_failure(sta, ssid, nets):
    code = sta.status()
    print("Could not join Wi-Fi: %s (status %s)" % (REASONS.get(code, "timed out"), code))
    if code == 2:
        print("  The password worked but the hotspot gave no IP address. Try: turn the")
        print("  hotspot off and on, disconnect other devices, or set WIFI_STATIC in secrets.py")
    else:
        _report_scan(nets, ssid)


def connect():
    """Bring up Wi-Fi and return the Pico's IP address."""
    global mode
    sec = load_secrets()
    if sec is None:
        print("No secrets.py, starting access point")
        return _start_ap()
    ssid, password, secrets = sec

    _set_country(secrets)
    sta = _prepare_sta(secrets)
    join_ssid, nets = resolve_ssid(sta, ssid)

    ok = False
    for attempt in (1, 2):
        if _try_join(sta, join_ssid, password, attempt):
            ok = True
            break
        sta.disconnect()
        time.sleep_ms(1000)

    if not ok:
        sta.disconnect()
        time.sleep_ms(500)
        _explain_failure(sta, ssid, scan(sta) or nets)
        print("Starting access point instead (retrying %r every %d s)" % (ssid, RETRY_EVERY_S))
        sta.active(False)
        return _start_ap()

    mode = "sta"
    ip = sta.ifconfig()[0]
    print("Connected, open http://%s" % ip)
    _sync_time()
    return ip


def _ap_has_clients():
    """True if a phone/laptop is joined to the Pico's own network."""
    try:
        return len(network.WLAN(network.AP_IF).status("stations")) > 0
    except Exception:
        return False


async def retry_station(ctl, every_s=RETRY_EVERY_S):
    """While in access-point mode, keep trying the network from secrets.py.

    The Pico W has one radio. Scanning or joining another network makes it
    leave the access point's channel, which kicks phones off the Pico's own
    Wi-Fi (or stops them joining). So this only runs while NOBODY is joined
    to the access point, does a single quick scan, and switches the station
    side back off after a failed try.
    """
    global mode
    sec = load_secrets()
    if sec is None:
        return
    ssid, password, secrets = sec
    while mode == "ap":
        await asyncio.sleep(every_s)
        if _ap_has_clients():
            continue                      # someone is using the booking page, leave the radio alone
        sta = _prepare_sta(secrets)
        nets = scan(sta, tries=1)
        n, _ = match(nets, ssid)
        if n is None or _ap_has_clients():
            sta.active(False)             # hotspot still not visible
            continue
        join_ssid = _ssid(n)
        print("Retrying Wi-Fi %r" % join_ssid)
        sta.connect(join_ssid, password)
        for _ in range((CONNECT_TIMEOUT_S + DHCP_EXTRA_S) * 2):
            if sta.isconnected() or sta.status() < 0:
                break
            await asyncio.sleep_ms(500)
        if sta.isconnected():
            mode = "sta"
            ctl.ip = sta.ifconfig()[0]
            print("Connected, open http://%s" % ctl.ip)
            _sync_time()
            return
        print("Retry failed: %s" % REASONS.get(sta.status(), "timed out"))
        sta.disconnect()
        sta.active(False)
