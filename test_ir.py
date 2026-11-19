# IR obstacle sensor test - prints raw value and lights the matching LED.
# Wave your hand / a toy car in front of the sensor.
# Turn the blue potentiometer on the module to adjust detection range.
from machine import Pin
import time

IR_PIN = 15
IR_ACTIVE_LOW = True
GREEN_LED_PIN = 28
RED_LED_PIN = 27

ir = Pin(IR_PIN, Pin.IN)
green = Pin(GREEN_LED_PIN, Pin.OUT)
red = Pin(RED_LED_PIN, Pin.OUT)

print("IR test on GP%d. Ctrl+C to stop." % IR_PIN)
last = None
try:
    while True:
        raw = ir.value()
        detected = (raw == 0) if IR_ACTIVE_LOW else (raw == 1)
        red.value(1 if detected else 0)
        green.value(0 if detected else 1)
        if detected != last:
            print("raw=%d -> %s" % (raw, "CAR DETECTED" if detected else "clear"))
            last = detected
        time.sleep_ms(50)
except KeyboardInterrupt:
    green.value(0); red.value(0)
    print("Stopped.")
