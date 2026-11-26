# Wi-Fi diagnostic - shows why the Pico W can't join your phone hotspot.
#
# 1. Prints the network name from secrets.py exactly (repr + bytes), so a
#    curly apostrophe or a trailing space is visible. Never prints the password.
# 2. Scans and lists every network the Pico can see.
# 3. Tries to join and prints every status change.
# 4. Ends with a verdict and what to change on the phone.
#
# Needs secrets.py and wifi.py on the Pico. Run with MicroPico.
import network
import time
import wifi

sec = wifi.load_secrets()
if sec is None:
    raise SystemExit("No secrets.py on the Pico. Copy secrets_example.py to secrets.py, fill it in, upload it.")
ssid, password, secrets = sec

print("=== secrets.py ===")
print("WIFI_SSID     = %r" % ssid)
print("  as bytes    =", ssid.encode())
print("WIFI_PASSWORD = %d characters%s" % (len(password),
      "  <- WPA2 needs 8-63 characters" if not 8 <= len(password) <= 63 else ""))
if ssid != ssid.strip():
    print("  ! The name has spaces at the start or end")

import os
print("\n=== Board ===")
u = os.uname()
print("Firmware:", u.version)
print("Board   :", u.machine)
if "W" not in u.machine:
    print("  ! This firmware is not a Pico W build. Flash the Pico W (or Pico 2 W) .uf2 from micropython.org")

# main.py runs at boot and may have started the Pico's own "SmartParking"
# network. Switch that off and reset the station side so the scan is clean.
ap = network.WLAN(network.AP_IF)
if ap.active():
    print("  The Pico's own access point was on (main.py ran at boot) - switching it off")
    ap.active(False)
sta = network.WLAN(network.STA_IF)
sta.active(False)
time.sleep_ms(500)

wifi._set_country(secrets)
sta = wifi._prepare_sta(secrets)
print("Station active:", sta.active(), "| status:", sta.status())
time.sleep_ms(2000)               # give the radio time to start before scanning

print("\n=== Scan ===")
nets = wifi.scan(sta, tries=5)
found, exact = wifi.match(nets, ssid)
for n in sorted(nets, key=lambda n: -n[3]):
    name = n[0].decode("utf-8", "ignore")
    mark = ""
    if n is found:
        mark = "  <== your network" + ("" if exact else " (name differs from secrets.py!)")
    if n[4] in (0, 1):
        mark += "  [open/WEP]"
    print("  %-32s ch %2d  %4d dBm  %-9s%s" % (repr(name) if name else "(hidden)", n[2], n[3],
          wifi.SECURITY.get(n[4], n[4]), mark))
print("  %d networks seen" % len(nets))

verdict = None
if not nets:
    verdict = ("The Pico sees no networks at all, even after 5 scans. Unplug the USB cable for 10 s, "
               "plug it back in, and run this test again BEFORE running main.py. If it is still 0: check "
               "the Board line above is a Pico W build, set WIFI_COUNTRY = \"PK\" in secrets.py, and "
               "make sure nothing metal or the breadboard's power wires cover the antenna (the end "
               "of the Pico opposite the USB socket).")
elif found is None:
    verdict = ("Your hotspot is not visible. Make it 2.4 GHz (iPhone: Settings > Personal Hotspot > "
               "Maximise Compatibility ON, and keep that screen open; Android: AP band 2.4 GHz).")
else:
    join_ssid = found[0].decode("utf-8", "ignore")
    if not exact:
        print("\nsecrets.py has %r but the phone broadcasts %r - joining with the exact name." % (ssid, join_ssid))
    print("\n=== Joining %r ===" % join_ssid)
    sta.connect(join_ssid, password)
    t0 = time.ticks_ms()
    last = None
    while time.ticks_diff(time.ticks_ms(), t0) < 40000:
        s = sta.status()
        if s != last:
            print("  %5.1f s  status %d  %s" % (time.ticks_diff(time.ticks_ms(), t0) / 1000, s,
                  wifi.REASONS.get(s, "?")))
            last = s
        if sta.isconnected() or s < 0:
            break
        time.sleep_ms(200)

    if sta.isconnected():
        ip, mask, gw, dns = sta.ifconfig()
        print("  IP %s  netmask %s  gateway %s  dns %s" % (ip, mask, gw, dns))
        verdict = "WORKING. Open http://%s from a device on the same hotspot." % ip
        if not exact:
            verdict += " (wifi.py now fixes the name automatically.)"
    elif last == getattr(network, "STAT_WRONG_PASSWORD", -3):
        verdict = "Wrong password. Check WIFI_PASSWORD (case-sensitive)."
    elif last == 2:
        verdict = ("Password accepted but no IP address. Turn the hotspot off/on, disconnect other "
                   "devices, or set WIFI_STATIC in secrets.py.")
    else:
        verdict = ("Join failed (%s). Set the hotspot security to WPA2-Personal (NOT WPA3 or "
                   "WPA2/WPA3 - the Pico can't tell these apart in a scan), 2.4 GHz, and move "
                   "the Pico closer." % wifi.REASONS.get(last, "timed out"))
    sta.disconnect()

print("\n=== Verdict ===")
print(verdict)
