# SSD1306 OLED test - scans the I2C bus, then draws text, shapes and a counter.
from machine import Pin, I2C
import time
from ssd1306 import SSD1306_I2C

I2C_SDA = 4
I2C_SCL = 5

i2c = I2C(0, sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=400000)
found = i2c.scan()
print("I2C devices found:", [hex(a) for a in found])
if not found:
    raise SystemExit("No I2C device - check SDA/SCL wiring and power.")

addr = 0x3C if 0x3C in found else found[0]
oled = SSD1306_I2C(128, 64, i2c, addr=addr)

oled.fill(0)
oled.text("OLED TEST", 28, 0)
oled.text("addr " + hex(addr), 28, 12)
oled.rect(0, 24, 128, 40, 1)
oled.fill_rect(4, 28, 20, 20, 1)
oled.show()
time.sleep(2)

print("Counting on display. Ctrl+C to stop.")
n = 0
try:
    while True:
        oled.fill_rect(30, 36, 90, 10, 0)
        oled.text("Count: %d" % n, 30, 36)
        oled.show()
        n += 1
        time.sleep_ms(500)
except KeyboardInterrupt:
    oled.fill(0)
    oled.show()
    print("Stopped.")
