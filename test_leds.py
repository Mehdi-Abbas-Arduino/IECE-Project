# LED test - blinks green, then red, then both together.
from machine import Pin
import time

# CHANGE: keep these the same as in main.py
GREEN_LED_PIN = 28
RED_LED_PIN = 27

green = Pin(GREEN_LED_PIN, Pin.OUT)
red = Pin(RED_LED_PIN, Pin.OUT)

print("LED test: green -> red -> both. Ctrl+C to stop.")
try:
    while True:
        print("GREEN on")
        green.value(1); red.value(0); time.sleep(1)
        print("RED on")
        green.value(0); red.value(1); time.sleep(1)
        print("BOTH on")
        green.value(1); red.value(1); time.sleep(1)
        green.value(0); red.value(0); time.sleep(0.5)
except KeyboardInterrupt:
    green.value(0); red.value(0)
    print("Stopped.")
