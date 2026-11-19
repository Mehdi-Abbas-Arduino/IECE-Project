# Servo PWM calibration - steps the pulse width from 500 to 2500 us
# and prints each value, so you can see where your servo starts and
# stops moving. Note the two pulse widths at the ends of its travel
# and put them into PULSE_MIN_US / PULSE_MAX_US in main.py.
from machine import Pin, PWM
import time

SERVO_PIN = 16
FREQ_HZ = 50          # standard for SG90; try 50-60 only
STEP_US = 100
HOLD_MS = 800

servo = PWM(Pin(SERVO_PIN))
servo.freq(FREQ_HZ)
period_us = 1_000_000 // FREQ_HZ


def pulse(us):
    servo.duty_u16(int(us / period_us * 65535))


print("Servo calibration on GP%d at %d Hz. Ctrl+C to stop." % (SERVO_PIN, FREQ_HZ))
try:
    while True:
        for us in range(500, 2501, STEP_US):
            print("pulse %4d us" % us)
            pulse(us)
            time.sleep_ms(HOLD_MS)
        print("--- full-speed jump test: 1000 us <-> 2000 us ---")
        for _ in range(3):
            pulse(1000); time.sleep_ms(1000)
            pulse(2000); time.sleep_ms(1000)
except KeyboardInterrupt:
    pulse(1500)
    time.sleep_ms(500)
    servo.deinit()
    print("Stopped.")
