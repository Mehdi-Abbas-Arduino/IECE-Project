# SG90 servo test - sweeps 0 -> 90 -> 180 -> 90 -> 0, then cycles gate closed/open.
# Servo must be powered from the external 5 V supply with GND shared with the Pico.
from machine import Pin, PWM
import time

SERVO_PIN = 16
SERVO_CLOSED_DEG = 0
SERVO_OPEN_DEG = 90
PULSE_MIN_US = 500        # pulse for 0 deg   (find yours with test_servo_calibrate.py)
PULSE_MAX_US = 2500       # pulse for 180 deg
FREQ_HZ =       50        # standard for SG90

servo = PWM(Pin(SERVO_PIN))
servo.freq(FREQ_HZ)
PERIOD_US = 1_000_000 // FREQ_HZ


def set_angle(deg):
    deg = max(0, min(180, deg))
    pulse_us = PULSE_MIN_US + (deg / 180) * (PULSE_MAX_US - PULSE_MIN_US)
    servo.duty_u16(70)
    return pulse_us


print("Servo test on GP%d at %d Hz, pulse %d-%d us. Ctrl+C to stop." %
      (SERVO_PIN, FREQ_HZ, PULSE_MIN_US, PULSE_MAX_US))
try:
    for a in (0, 90, 180, 90, 0):
        print("Angle %3d -> pulse %d us" % (a, set_angle(a)))
        time.sleep(1)
    while True:
        print("Gate OPEN   (%d deg, %d us)" % (SERVO_OPEN_DEG, set_angle(SERVO_OPEN_DEG)))
        time.sleep(2)
        print("Gate CLOSED (%d deg, %d us)" % (SERVO_CLOSED_DEG, set_angle(SERVO_CLOSED_DEG)))
        time.sleep(2)
except KeyboardInterrupt:
    set_angle(SERVO_CLOSED_DEG)
    time.sleep_ms(500)
    servo.deinit()
    print("Stopped.")
