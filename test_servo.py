# SG90 servo test - cycles the gate CLOSED / OPEN using duty-cycle values
# measured on this servo (with the function generator at 50 Hz).
# Servo must be powered from the external 5 V supply (current limit >= 1 A)
# with GND shared with the Pico.
from machine import Pin, PWM
import time

SERVO_PIN = 16            # CHANGE: GPIO of the servo signal wire
FREQ_HZ = 50              # leave at 50 Hz: SG90 servos expect a 20 ms period
CLOSED_DUTY = 6.5         # CHANGE: % duty for gate closed (6.5 % of 20 ms = 1300 us)
OPEN_DUTY = 11.5          # CHANGE: % duty for gate open   (11.5 % of 20 ms = 2300 us)
HOLD_S = 2                # seconds to stay in each position

servo = PWM(Pin(SERVO_PIN))
servo.freq(FREQ_HZ)
PERIOD_US = 1_000_000 // FREQ_HZ


def set_duty(percent):
    servo.duty_u16(int(percent / 100 * 65535))
    return percent / 100 * PERIOD_US      # pulse width in us, for the printout


print("Servo test on GP%d at %d Hz: closed %.1f %%, open %.1f %%. Ctrl+C to stop." %
      (SERVO_PIN, FREQ_HZ, CLOSED_DUTY, OPEN_DUTY))
try:
    while True:
        print("Gate OPEN   (%.1f %%, %d us)" % (OPEN_DUTY, set_duty(OPEN_DUTY)))
        time.sleep(HOLD_S)
        print("Gate CLOSED (%.1f %%, %d us)" % (CLOSED_DUTY, set_duty(CLOSED_DUTY)))
        time.sleep(HOLD_S)
except KeyboardInterrupt:
    set_duty(CLOSED_DUTY)
    time.sleep_ms(500)
    servo.deinit()
    print("Stopped.")
