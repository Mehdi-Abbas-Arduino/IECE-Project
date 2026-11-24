# =====================================================================
#  Wi-Fi settings - HOW TO USE THIS FILE
#
#  1. Copy this file and name the copy  secrets.py  (same folder).
#  2. CHANGE the values marked below in secrets.py (not in this file).
#  3. Upload secrets.py to the Pico (Upload project to Pico does it).
#
#  secrets.py is in .gitignore, so your password is never pushed to GitHub.
#  Without secrets.py the Pico starts its own "SmartParking" Wi-Fi instead
#  (password parking123, page at http://192.168.4.1).
#  If the Pico won't join, run test_wifi.py - it tells you why.
# =====================================================================

# CHANGE: the hotspot / Wi-Fi name, exactly as the phone shows it.
#   - iPhone names use a curly apostrophe (Umar’s iPhone). wifi.py also accepts a
#     straight ', but renaming the hotspot to something plain like "ParkingNet" is safest.
#   - The hotspot must be 2.4 GHz and WPA2:
#       iPhone : Settings > Personal Hotspot > Maximise Compatibility ON, keep that screen open
#       Android: Hotspot > AP band 2.4 GHz, Security WPA2-Personal (not WPA3)
WIFI_SSID = "Redmi-15"

# CHANGE: the hotspot password (case-sensitive, 8-63 characters).
WIFI_PASSWORD = "12345678"

# OPTIONAL: remove the # and set your 2-letter country code if the Pico can't see
# the hotspot at all (it limits which Wi-Fi channels are used). Pakistan = "PK".
# WIFI_COUNTRY = "PK"

# OPTIONAL: only if test_wifi.py says "Password accepted but no IP address".
# Gives the Pico a fixed address instead of asking the hotspot for one.
# Format: (Pico IP, netmask, gateway, DNS).
#   iPhone hotspot : use the line below as it is (iPhone hotspots are always 172.20.10.x).
#   Android hotspot: look at another device's IP on the hotspot (e.g. 192.168.43.25),
#                    keep the first three numbers, pick an unused last number (e.g. .50),
#                    gateway = same first three numbers + .1, netmask 255.255.255.0.
# WIFI_STATIC = ("172.20.10.9", "255.255.255.240", "172.20.10.1", "8.8.8.8")
