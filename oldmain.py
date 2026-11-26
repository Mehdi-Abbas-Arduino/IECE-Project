# Smart Parking System - Raspberry Pi Pico (MicroPython)
#
#   HC-SR04 ultrasonic  -> detects a car at the GATE, opens the servo barrier
#   IR obstacle sensor  -> detects a car in the PARKING SPOT
#   Green LED = spot free, Red LED = spot occupied
#   SSD1306 OLED (128x64, I2C) shows the live status
#
# Needs hcsr04.py and ssd1306.py on the Pico alongside this file.

from machine import Pin, PWM, I2C
import time
from hcsr04 import HCSR04

# ---------------- Pin map (change to match your wiring) ----------------
TRIG_PIN = 20
ECHO_PIN = 19
I2C_SDA = 4
I2C_SCL = 5
IR_PIN = 15
SERVO_PIN = 16
GREEN_LED_PIN = 28
RED_LED_PIN = 27

# ---------------- Settings ----------------
GATE_TRIGGER_CM = 10      # car closer than this to the ultrasonic = car at gate
GATE_OPEN_MS = 3000       # keep gate open this long after the car leaves the sensor
SERVO_CLOSED_DEG = 0
SERVO_OPEN_DEG = 180
PULSE_MIN_US = 1300       # CHANGE: pulse (us) for 0 deg = gate CLOSED (6.5 % duty at 50 Hz, measured)
PULSE_MAX_US = 2300       # CHANGE: pulse (us) for 180 deg = gate OPEN (11.5 % duty at 50 Hz, measured)
IR_ACTIVE_LOW = True      # most IR modules output 0 when something is detected
BLOCK_WHEN_FULL = True    # don't open the gate if the spot is already taken
IR_SAMPLES = 3            # consecutive equal IR reads needed to change state
GATE_SAMPLES = 2          # consecutive "close" ultrasonic reads to count a car
LOOP_MS = 100

# ---------------- Hardware setup ----------------
sensor = HCSR04(trigger_pin=TRIG_PIN, echo_pin=ECHO_PIN, echo_timeout_us=30000)
ir = Pin(IR_PIN, Pin.IN)
green = Pin(GREEN_LED_PIN, Pin.OUT)
red = Pin(RED_LED_PIN, Pin.OUT)

servo = PWM(Pin(SERVO_PIN))
servo.freq(50)

oled = None
try:
    from ssd1306 import SSD1306_I2C
    i2c = I2C(0, sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=400000)
    oled = SSD1306_I2C(128, 64, i2c)
except Exception as e:
    print("OLED not found, continuing without display:", e)


def set_angle(deg):
    """0-180 deg -> PULSE_MIN_US..PULSE_MAX_US pulse in a 20 ms period."""
    deg = max(0, min(180, deg))
    pulse_us = PULSE_MIN_US + (deg / 180) * (PULSE_MAX_US - PULSE_MIN_US)
    servo.duty_u16(int(pulse_us / 20000 * 65535))


def ir_raw_occupied():
    v = ir.value()
    return v == 0 if IR_ACTIVE_LOW else v == 1


def read_distance():
    try:
        return sensor.distance_cm()
    except OSError:
        return None  # out of range / no echo


def show(spot_occupied, gate_open, dist, full_blocked):
    if oled is None:
        return
    oled.fill(0)
    oled.text("SMART PARKING", 12, 0)
    oled.hline(0, 10, 128, 1)
    oled.text("Spot: " + ("OCCUPIED" if spot_occupied else "FREE"), 0, 16)
    oled.text("Gate: " + ("OPEN" if gate_open else "CLOSED"), 0, 28)
    if dist is None or dist > 400:
        oled.text("Dist: --", 0, 40)
    else:
        oled.text("Dist: %d cm" % dist, 0, 40)
    if full_blocked:
        oled.fill_rect(0, 52, 128, 12, 1)
        oled.text("LOT FULL", 32, 54, 0)
    oled.show()


def update_leds(occupied):
    green.value(0 if occupied else 1)
    red.value(1 if occupied else 0)


# ---------------- Main loop ----------------
def main():
    spot_occupied = ir_raw_occupied()
    ir_candidate, ir_count = spot_occupied, 0
    gate_open = False
    gate_last_seen = 0
    near_count = 0
    last_status = None

    set_angle(SERVO_CLOSED_DEG)
    update_leds(spot_occupied)
    print("Smart Parking started.")

    while True:
        now = time.ticks_ms()

        # --- IR: debounced spot occupancy ---
        raw = ir_raw_occupied()
        if raw == ir_candidate:
            ir_count += 1
        else:
            ir_candidate, ir_count = raw, 1
        if ir_count >= IR_SAMPLES and ir_candidate != spot_occupied:
            spot_occupied = ir_candidate
            update_leds(spot_occupied)

        # --- Ultrasonic: car at gate? ---
        dist = read_distance()
        if dist is not None and 0 < dist < GATE_TRIGGER_CM:
            near_count += 1
        else:
            near_count = 0
        car_at_gate = near_count >= GATE_SAMPLES

        # --- Gate state machine ---
        full_blocked = False
        if car_at_gate:
            if gate_open:
                gate_last_seen = now          # car still under the barrier
            elif spot_occupied and BLOCK_WHEN_FULL:
                full_blocked = True
            else:
                gate_open = True
                gate_last_seen = now
                set_angle(SERVO_OPEN_DEG)
        elif gate_open and time.ticks_diff(now, gate_last_seen) > GATE_OPEN_MS:
            gate_open = False
            set_angle(SERVO_CLOSED_DEG)

        # --- Output ---
        show(spot_occupied, gate_open, dist, full_blocked)
        status = (spot_occupied, gate_open, full_blocked)
        if status != last_status:
            print("Spot:", "OCCUPIED" if spot_occupied else "FREE",
                  "| Gate:", "OPEN" if gate_open else "CLOSED",
                  "| LOT FULL" if full_blocked else "",
                  "| Dist:", dist)
            last_status = status

        time.sleep_ms(LOOP_MS)


try:
    main()
except KeyboardInterrupt:
    set_angle(SERVO_CLOSED_DEG)
    time.sleep_ms(500)
    servo.deinit()
    green.value(0)
    red.value(0)
    if oled:
        oled.fill(0)
        oled.show()
    print("Stopped.")
