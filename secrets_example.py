# Copy this file to secrets.py and fill in your Wi-Fi details.
# secrets.py is ignored by git so your password is never committed.
# Without secrets.py the Pico starts its own "SmartParking" access point.

WIFI_SSID = "your-network-name"
WIFI_PASSWORD = "your-password"
# WIFI_COUNTRY = "GB"   # optional: your 2-letter country code (e.g. GB, US, PK, IN)

# Optional: fixed IP if the hotspot connects but never gives the Pico an address.
# iPhone hotspots use 172.20.10.x; for Android, check another device's IP on the
# hotspot and pick an unused number in the same range.
# WIFI_STATIC = ("172.20.10.9", "255.255.255.240", "172.20.10.1", "8.8.8.8")
