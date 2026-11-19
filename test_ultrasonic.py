# HC-SR04 ultrasonic test - prints distance twice a second.
# Move your hand towards the sensor; below GATE_TRIGGER_CM it reports "CAR AT GATE".
from hcsr04 import HCSR04
import time

TRIG_PIN = 20 #LV1
ECHO_PIN = 19 #LV2
GATE_TRIGGER_CM = 10

sensor = HCSR04(trigger_pin=TRIG_PIN, echo_pin=ECHO_PIN, echo_timeout_us=30000)

print("Ultrasonic test (TRIG GP%d, ECHO GP%d). Ctrl+C to stop." % (TRIG_PIN, ECHO_PIN))
try:
    while True:
        try:
            d = sensor.distance_cm()
            if d > 400:
                print("Distance: out of range")
            else:
                tag = "  <- CAR AT GATE" if d < GATE_TRIGGER_CM else ""
                print("Distance: %.1f cm%s" % (d, tag))
        except OSError as e:
            print("Error:", e)
        time.sleep_ms(500)
except KeyboardInterrupt:
    print("Stopped.")
