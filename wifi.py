# Wi-Fi for the Pico W.
#
# Joins the network in secrets.py. If there is no secrets.py, or joining
# fails, the Pico starts its own access point instead so the booking page is
# still reachable (connect to it and open http://192.168.4.1).

import network
import time
import clock

AP_SSID = "SmartParking"
AP_PASSWORD = "parking123"      # 8+ characters, or None for an open network
AP_CHANNEL = 6
CONNECT_TIMEOUT_S = 20
DHCP_EXTRA_S = 20         # extra wait once joined but still waiting for an IP address


def _sync_time():
    try:
        import ntptime
        ntptime.settime()       # sets the RTC to UTC
        clock.mark_synced()
        print("Clock set from NTP")
    except Exception as e:
        print("NTP failed, the first browser to connect will set the clock:", e)


def _start_ap():
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
    print("Access point '%s' started (%s), open http://%s"
          % (ap.config("essid"), ("password " + AP_PASSWORD) if AP_PASSWORD else "no password", ip))
    return ip


_SECURITY = {0: "open", 1: "WEP", 2: "WPA", 3: "WPA2", 4: "WPA/WPA2", 5: "WPA2", 6: "WPA3", 7: "WPA2/WPA3"}


def _report_scan(sta, ssid):
    """Print whether the network is visible, and its signal and security."""
    try:
        nets = sta.scan()
    except Exception as e:
        print("Wi-Fi scan failed:", e)
        return
    if not nets:
        print("  Scan found no networks at all (the radio may still be busy)")
        return
    for n in nets:
        if n[0].decode("utf-8", "ignore") == ssid:
            print("  Found '%s': channel %d, signal %d dBm, security %s"
                  % (ssid, n[2], n[3], _SECURITY.get(n[4], n[4])))
            if n[3] < -80:
                print("  Signal is weak, move the Pico closer")
            if n[4] >= 6:
                print("  WPA3 may not work, set the hotspot to WPA2")
            return
    print("  '%s' not visible. It must be 2.4 GHz and switched on. Networks seen:" % ssid)
    for n in sorted(nets, key=lambda n: -n[3])[:8]:
        print("   ", n[0].decode("utf-8", "ignore") or "(hidden)", "%d dBm" % n[3])


def _try_join(sta, ssid, password):
    sta.connect(ssid, password)
    print("Connecting to", ssid, end="")
    waited, limit = 0, CONNECT_TIMEOUT_S * 2
    while waited < limit:
        if sta.isconnected() or sta.status() < 0:
            break
        if sta.status() == 2 and limit == CONNECT_TIMEOUT_S * 2:
            limit += DHCP_EXTRA_S * 2      # joined, give the hotspot longer to hand out an IP
        print(".", end="")
        time.sleep_ms(500)
        waited += 1
    print()
    return sta.isconnected()


def connect():
    """Bring up Wi-Fi and return the Pico's IP address."""
    try:
        import secrets
        ssid, password = secrets.WIFI_SSID, secrets.WIFI_PASSWORD
    except (ImportError, AttributeError):
        print("No secrets.py, starting access point")
        return _start_ap()

    # Wi-Fi country (2-letter code) decides the allowed channels, e.g. "PK", "GB", "US".
    country = getattr(secrets, "WIFI_COUNTRY", None)
    if country:
        try:
            network.country(country)
        except Exception:
            try:
                import rp2
                rp2.country(country)
            except Exception as e:
                print("Could not set Wi-Fi country:", e)

    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    try:
        sta.config(pm=0xa11140)   # turn off Wi-Fi power saving, more reliable
    except Exception:
        pass

    # Optional fixed address (skips DHCP): (ip, netmask, gateway, dns)
    static = getattr(secrets, "WIFI_STATIC", None)
    if static:
        sta.ifconfig(tuple(static))
        print("Using fixed IP", static[0])

    ok = False
    for attempt in (1, 2):
        if _try_join(sta, ssid, password):
            ok = True
            break
        sta.disconnect()
        time.sleep_ms(1000)

    if not ok:
        reasons = {
            getattr(network, "STAT_WRONG_PASSWORD", -3): "wrong password",
            getattr(network, "STAT_NO_AP_FOUND", -2): "network not found",
            getattr(network, "STAT_CONNECT_FAIL", -1): "connection failed",
            1: "still joining when it timed out",
            2: "joined but got no IP address",
        }
        code = sta.status()
        print("Could not join Wi-Fi: %s (status %s)" % (reasons.get(code, "timed out"), code))
        if code == 2:
            print("  The password worked but the hotspot gave no IP address. Try: turn the")
            print("  hotspot off and on, disconnect other devices, or set WIFI_STATIC in secrets.py")
        else:
            sta.disconnect()
            time.sleep_ms(500)
            _report_scan(sta, ssid)
        print("Starting access point instead")
        sta.active(False)
        return _start_ap()

    ip = sta.ifconfig()[0]
    print("Connected, open http://%s" % ip)
    _sync_time()
    return ip
