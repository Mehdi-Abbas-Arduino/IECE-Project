# Smart Parking System - Raspberry Pi Pico W (MicroPython)
#
#   HC-SR04 ultrasonic  -> detects a car at the GATE, opens the servo barrier
#   IR obstacle sensor  -> detects a car in the PARKING SPOT
#   LEDs: green = car parked, red = spot booked, both off = spot free
#   SSD1306 OLED (128x64, I2C) shows the live status
#   Wi-Fi web app       -> book the spot, open the gate with a booking code
#
# Needs on the Pico alongside this file:
#   hcsr04.py ssd1306.py clock.py booking.py wifi.py web.py www/index.html
#   and optionally secrets.py (Wi-Fi name and password, see secrets_example.py)

from machine import Pin, PWM, I2C
import time
try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

from hcsr04 import HCSR04
import clock
from booking import Bookings

# =====================================================================
#  SETTINGS YOU MAY NEED TO CHANGE BY HAND
#  Everything marked  # CHANGE  below is a value you set to match your
#  own wiring or hardware. Nothing else in this file needs editing.
#  After changing anything, re-upload main.py to the Pico.
# =====================================================================

# ---------------- Pin map ----------------
# CHANGE: these are GPIO numbers (the "GPxx" label), NOT the physical pin
# numbers 1-40 printed around the board. Each one must match the wire you
# actually used. Use the matching test_*.py script to check a part works
# before changing it here, and keep the test file's pin the same.
TRIG_PIN = 20             # CHANGE: HC-SR04 TRIG (through level shifter LV1)
ECHO_PIN = 19             # CHANGE: HC-SR04 ECHO (through level shifter LV2, never direct: it is 5 V)
I2C_SDA = 4               # CHANGE: OLED SDA. Must be an I2C0 SDA pin (GP0/4/8/12/16/20)
I2C_SCL = 5               # CHANGE: OLED SCL. Must be the I2C0 SCL pin next to it (GP1/5/9/13/17/21)
IR_PIN = 15               # CHANGE: IR sensor OUT
SERVO_PIN = 16            # CHANGE: servo signal (orange wire, through level shifter LV3)
GREEN_LED_PIN = 28        # CHANGE: green LED (via 220 ohm resistor)
RED_LED_PIN = 27          # CHANGE: red LED (via 220 ohm resistor)

# ---------------- Gate (ultrasonic + servo) ----------------
GATE_TRIGGER_CM = 10      # CHANGE: how close (cm) a car must be to the ultrasonic to open the gate.
                          #   Run test_ultrasonic.py, hold a toy car where it should trigger, use that + 2 cm.
GATE_OPEN_MS = 3000       # how long (ms) the gate stays open after the car has left the sensor
REMOTE_OPEN_MS = 15000    # gate opened from the web page stays open at least this long (ms)
SERVO_CLOSED_DEG = 0      # CHANGE: arm angle when the barrier is down. Adjust if the arm isn't level.
SERVO_OPEN_DEG = 180      # CHANGE: arm angle when the barrier is up (180 = PULSE_MAX_US).
PULSE_MIN_US = 1300       # CHANGE: pulse (us) for 0 deg = gate CLOSED (6.5 % duty at 50 Hz, measured)
PULSE_MAX_US = 2300       # CHANGE: pulse (us) for 180 deg = gate OPEN (11.5 % duty at 50 Hz, measured)
                          #   test_servo.py uses the same positions as duty % (CLOSED_DUTY / OPEN_DUTY).

# ---------------- Parking spot (IR sensor) ----------------
IR_ACTIVE_LOW = True      # CHANGE: True if test_ir.py prints raw=0 when a car is there (most modules).
                          #   Set False if it prints raw=1 when a car is there.
                          #   Detection distance itself is set with the screw on the IR module.
IR_SAMPLES = 3            # IR reads in a row (100 ms apart) that must agree before the spot changes state
BLOCK_WHEN_FULL = True    # True = gate stays shut for new cars while the spot is taken

# ---------------- Other ----------------
ALERT_SHOW_MS = 10000     # how long (ms) a "TIME UP" / "NO SHOW" alert stays on the OLED
GATE_SAMPLES = 2          # ultrasonic reads in a row that must see a car before the gate opens
LOOP_MS = 100             # main loop period (ms). Leave at 100 (matches the tracker's debounce rule)
WEB_ENABLED = True        # CHANGE: False to test the hardware without Wi-Fi / the web page
                          #   (Wi-Fi name and password go in secrets.py, not here)

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


def oled_message(*lines):
    if oled is None:
        return
    oled.fill(0)
    for i, line in enumerate(lines):
        oled.text(line, 0, i * 12)
    oled.show()


class Controller:
    def __init__(self, bookings):
        self.bookings = bookings
        self.ip = None
        self.spot_occupied = ir_raw_occupied()
        self.reserved = False
        self.gate_open = False
        self.gate_hold_until = 0      # ticks_ms; gate may close after this
        self.remote_open = False      # set by the web app
        self._ir_candidate = self.spot_occupied
        self._ir_count = 0
        self._near_count = 0
        self._last_status = None
        self._alert_banner = None
        self._alert_until = 0

    # Called from the web app
    def open_gate(self):
        self.remote_open = True

    def _open(self, now, hold_ms):
        if not self.gate_open:
            self.gate_open = True
            set_angle(SERVO_OPEN_DEG)
        until = time.ticks_add(now, hold_ms)
        if time.ticks_diff(until, self.gate_hold_until) > 0:
            self.gate_hold_until = until

    def _update_leds(self):
        if self.spot_occupied:        # car parked -> green
            green.value(1)
            red.value(0)
        elif self.reserved:           # booked, car not here yet -> red
            green.value(0)
            red.value(1)
        else:                         # free -> both off
            green.value(0)
            red.value(0)

    def _show(self, dist, banner):
        if oled is None:
            return
        oled.fill(0)
        oled.text("SMART PARKING", 12, 0)
        oled.hline(0, 10, 128, 1)
        spot = "OCCUPIED" if self.spot_occupied else ("RESERVED" if self.reserved else "FREE")
        oled.text("Spot: " + spot, 0, 16)
        oled.text("Gate: " + ("OPEN" if self.gate_open else "CLOSED"), 0, 28)
        if self.ip:
            oled.text(self.ip, 0, 40)
        elif dist is None or dist > 400:
            oled.text("Dist: --", 0, 40)
        else:
            oled.text("Dist: %d cm" % dist, 0, 40)
        if banner:
            oled.fill_rect(0, 52, 128, 12, 1)
            oled.text(banner, (128 - len(banner) * 8) // 2, 54, 0)
        oled.show()

    def tick(self):
        now = time.ticks_ms()

        # --- Bookings: is the spot reserved right now? ---
        if clock.synced:
            t = clock.now()
            if self.spot_occupied:
                b = self.bookings.car_in_spot(t)
                if b:
                    print("Booking #%d: car arrived" % b["id"])
            for b, reason in self.bookings.tick(t):
                self._alert_banner = "TIME UP" if reason == "ended" else "NO SHOW"
                self._alert_until = time.ticks_add(now, ALERT_SHOW_MS)
            self.reserved = self.bookings.active(t) is not None
        else:
            self.reserved = False

        # --- IR: debounced spot occupancy ---
        raw = ir_raw_occupied()
        if raw == self._ir_candidate:
            self._ir_count += 1
        else:
            self._ir_candidate, self._ir_count = raw, 1
        if self._ir_count >= IR_SAMPLES and self._ir_candidate != self.spot_occupied:
            self.spot_occupied = self._ir_candidate

        # --- Ultrasonic: car at gate? ---
        dist = read_distance()
        if dist is not None and 0 < dist < GATE_TRIGGER_CM:
            self._near_count += 1
        else:
            self._near_count = 0
        car_at_gate = self._near_count >= GATE_SAMPLES

        # --- Gate state machine ---
        banner = None
        if self.remote_open:
            self.remote_open = False
            self._open(now, REMOTE_OPEN_MS)
        if car_at_gate:
            if self.gate_open:
                self._open(now, GATE_OPEN_MS)     # car still under the barrier
            elif self.spot_occupied and BLOCK_WHEN_FULL:
                banner = "LOT FULL"
            elif self.reserved:
                banner = "RESERVED"               # booked: open with code only
            else:
                self._open(now, GATE_OPEN_MS)
        elif self.gate_open and time.ticks_diff(now, self.gate_hold_until) > 0:
            self.gate_open = False
            set_angle(SERVO_CLOSED_DEG)
        if banner is None and self._alert_banner:
            if time.ticks_diff(self._alert_until, now) > 0:
                banner = self._alert_banner        # booking ended / released alert
            else:
                self._alert_banner = None

        # --- Output ---
        self._update_leds()
        self._show(dist, banner)
        status = (self.spot_occupied, self.reserved, self.gate_open, banner)
        if status != self._last_status:
            print("Spot:", "OCCUPIED" if self.spot_occupied else "FREE",
                  "| Reserved" if self.reserved else "",
                  "| Gate:", "OPEN" if self.gate_open else "CLOSED",
                  "|", banner or "", "| Dist:", dist)
            self._last_status = status

    async def run(self):
        set_angle(SERVO_CLOSED_DEG)
        while True:
            self.tick()
            await asyncio.sleep_ms(LOOP_MS)


async def main():
    ctl = Controller(Bookings("bookings.json"))
    print("Smart Parking started.")

    if WEB_ENABLED:
        oled_message("SMART PARKING", "", "Starting Wi-Fi...")
        try:
            import wifi
            from web import WebApp
            ctl.ip = wifi.connect()
            await WebApp(ctl, ctl.bookings).start()
            print("Booking page: http://%s" % ctl.ip)
            asyncio.create_task(wifi.retry_station(ctl))   # rejoins the hotspot if it appears later
        except Exception as e:
            print("Web app disabled:", e)
            ctl.ip = None

    await ctl.run()


def shutdown():
    set_angle(SERVO_CLOSED_DEG)
    time.sleep_ms(500)
    servo.deinit()
    green.value(0)
    red.value(0)
    if oled:
        oled.fill(0)
        oled.show()
    print("Stopped.")


try:
    asyncio.run(main())
except KeyboardInterrupt:
    shutdown()
finally:
    asyncio.new_event_loop()
