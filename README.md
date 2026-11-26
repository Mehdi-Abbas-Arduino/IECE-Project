# Smart Parking System

An automated single-spot car park built on a **Raspberry Pi Pico W** running **MicroPython**, made for the IECE course project.

When a car comes up to the entrance, an ultrasonic sensor detects it and a servo lifts the barrier. An IR sensor in the parking bay checks whether the spot is taken. Green and red LEDs show whether the spot is free, booked or occupied, and an OLED screen shows live information. If the spot is already taken, the barrier stays closed and the screen shows **LOT FULL**.

Drivers can also **book the spot** from their phone. The Pico W serves a booking web page over Wi-Fi; while a booking is active the gate stays closed for other cars, and the driver who booked opens it with their 6-digit code. If the car doesn't turn up within 2 minutes the booking is released, and when the booked time is over the spot turns free and an alert is shown.

---

## Features

- **Automatic gate:** the HC-SR04 ultrasonic sensor detects a car within 10 cm of the gate and opens the SG90 servo barrier.
- **Spot detection:** the IR obstacle sensor checks whether the bay is free or taken. Its readings are debounced, so noise doesn't flip the status.
- **Full-lot protection:** the gate won't open for a new car while the spot is taken.
- **Status LEDs:** green = car parked, red = spot booked (car not here yet), both off = spot free.
- **Live display:** a 128×64 OLED shows the spot status, the gate status and the measured distance.
- **Non-blocking control loop:** sensors, gate timer and display all update about 10 times a second, with no `sleep` blocking the gate logic.
- **Booking web app:** pick a day, arrival time and duration (15 min to 4 h, up to 7 days ahead) and get a booking code. Overlapping bookings are refused and bookings survive a reboot.
- **Open the gate from your phone:** the booking code opens the gate from 10 minutes before the booking starts until it ends, both for arriving and for leaving.
- **Reserved status:** the red LED lights while a booking is active, and the OLED shows *RESERVED* if a car without the code comes to the gate.
- **No-show release:** if no car arrives within 2 minutes of the booking start, the booking is cancelled and the spot is free again. A car counts as arrived when its code opens the gate or the IR sensor sees a car in the spot.
- **Alerts:** when a booking's time is complete, or it is released as a no-show, the spot turns free and an alert is sent: a banner on the web page (the driver's own phone also vibrates), *TIME UP* / *NO SHOW* on the OLED for 10 s, and an `ALERT:` line in the serial log.
- **Spots dashboard:** the web page lists every spot as Free, Booked or Occupied, and shows *Sorry No spots left* when none are free.
- **Separate test scripts** for every component, plus a tool to calibrate the servo.

---

## Hardware

| Qty | Component | Notes |
|---|---|---|
| 1 | Raspberry Pi Pico W | Controller, 3.3 V logic |
| 1 | HC-SR04 ultrasonic sensor | Gate detection, needs 5 V |
| 1 | IR obstacle sensor (FC-51 / MH-B) | Spot detection, powered at 3.3 V |
| 1 | SG90 micro servo | Barrier arm |
| 1 | SSD1306 OLED 0.96″ 128×64 (I2C) | Status display |
| 1 | 4-channel logic level converter (BSS138) | 5 V ↔ 3.3 V for the HC-SR04 |
| 1 + 1 | 5 mm LEDs, green and red | Spot status |
| 2 | 220 Ω resistors | LED current limit, about 6 mA each |
| 1 | 5 V supply, ≥ 1 A | Powers the servo and the HC-SR04. On a bench supply, set the **current limit to at least 1 A** |
| 1 | 470 µF capacitor (optional) | Smooths the servo's supply |

---

## Wiring

| Component | Pin | Connects to | Pico pin |
|---|---|---|---|
| HC-SR04 | VCC / GND | External 5 V / GND | — / GND |
| HC-SR04 | TRIG | Shifter HV1 → LV1 | **GP20** (pin 26) |
| HC-SR04 | ECHO | Shifter HV2 → LV2 | **GP19** (pin 25) |
| Level shifter | HV / LV / GND | 5 V ext / 3V3(OUT) / GND | — / pin 36 / GND |
| SSD1306 OLED | VCC / GND | 3V3 / GND | pin 36 / GND |
| SSD1306 OLED | SDA / SCL | I2C0 | **GP4** (pin 6) / **GP5** (pin 7) |
| IR sensor | VCC / GND | 3V3 / GND | pin 36 / GND |
| IR sensor | OUT | Direct | **GP15** (pin 20) |
| SG90 servo | SIG (orange) | Direct to Pico (3.3 V signal is fine) | **GP16** (pin 21) |
| SG90 servo | V+ (red) / GND (brown) | External 5 V / GND | — / GND |
| Green LED | Anode via 220 Ω | Direct | **GP28** (pin 34) |
| Red LED | Anode via 220 Ω | Direct | **GP27** (pin 32) |

> ⚠️ **Common ground is required.** Connect the external 5 V supply's − terminal to a Pico GND pin. Never connect HC-SR04 ECHO straight to the Pico: it outputs 5 V.

[`docs/circuit-design.html`](docs/circuit-design.html) has the full schematic, power budget and design notes. Download it and open it in a browser.

---

## How it works

```
             ┌──────────────── every 100 ms ────────────────┐
IR sensor ──►│ debounce (3 equal reads) ──► spot FREE/TAKEN │──► LEDs
             │                                              │
HC-SR04 ────►│ distance < 10 cm on 2 reads ──► car at gate  │
             │                                              │
Bookings ───►│ booking active ──► RESERVED (red LED)        │
             │ no car 2 min after start ──► free + alert    │
             │ end time reached ──► free + alert            │
             │                                              │
             │ Gate state machine                           │──► Servo
             │   CLOSED ─ car at gate & spot free ─► OPEN   │
             │   CLOSED ─ car at gate & spot taken ─► FULL  │
             │   CLOSED ─ car at gate & booked ─► RESERVED  │
             │   CLOSED ─ code entered on web page ─► OPEN  │
             │   OPEN ── no car for 3 s ──────────► CLOSED  │
             └──────────────────────────────────────────────┘──► OLED + serial log
```

The gate stays open while a car is still under the barrier, and closes 3 seconds after it has passed.

---

## Project structure

| File | Purpose |
|---|---|
| `main.py` | Main application. Runs automatically when the Pico boots |
| `hcsr04.py` | HC-SR04 ultrasonic sensor driver |
| `ssd1306.py` | SSD1306 OLED driver |
| `clock.py` | Wall-clock time (set by NTP or by the first browser) |
| `booking.py` | Booking schedule: rules, codes, saving to `bookings.json` |
| `wifi.py` | Joins Wi-Fi, or starts the `SmartParking` access point |
| `web.py` | Small async web server and booking API |
| `www/index.html` | The booking page |
| `secrets_example.py` | Template for `secrets.py` (your Wi-Fi name and password) |
| `tools/preview_server.py` | Runs the booking page on your PC, no Pico needed |
| `test_leds.py` | Blinks the green and red LEDs |
| `test_ir.py` | Prints IR detections and lights the matching LED |
| `test_ultrasonic.py` | Prints the measured distance and flags "CAR AT GATE" |
| `test_servo.py` | Cycles the gate open (11.5 % duty) and closed (6.5 % duty) |
| `test_servo_calibrate.py` | Steps through pulse widths to find the servo's real range |
| `test_oled.py` | Scans the I2C bus and draws a test screen |
| `test_wifi.py` | Explains why the Pico can't join your Wi-Fi or hotspot |
| `docs/circuit-design.html` | Schematic, pin map, power budget and bill of materials |

---

## Getting started

1. **Flash MicroPython:** hold **BOOTSEL**, plug the Pico in, and drag the Pico W `.uf2` file from [micropython.org](https://micropython.org/download/RPI_PICO_W/) onto the drive that appears.
2. **Install the MicroPico extension** in VS Code and open this folder.
3. **Connect:** the status bar should say *Pico Connected*.
4. **Upload:** right-click the folder and choose **Upload project to Pico**.
5. **Test each part:** open a `test_*.py` file and choose **MicroPico: Run current file on Pico**.
6. **Set up Wi-Fi:** copy `secrets_example.py` to `secrets.py`, fill in your network name and password, and upload it. `secrets.py` is ignored by git.
7. **Run the system:** run `main.py`, or reset the Pico and it starts on its own. The serial log and the OLED show the Pico's IP address.
8. **Book:** open `http://<that IP>` on a phone or laptop on the same network.

## Booking web app

| How the Pico connects | Where to open the page |
|---|---|
| `secrets.py` present and the network is in range | `http://<IP shown on the OLED>` |
| No `secrets.py`, or joining fails | Join the Wi-Fi network **SmartParking** (password `parking123`), then open `http://192.168.4.1` |

While it's on its own access point, the Pico keeps retrying the network in `secrets.py` every 60 seconds, but **only while no phone is joined to SmartParking**. The Pico W has one radio, and scanning for another network would kick phones off. If you switch the hotspot on after the Pico has booted, it joins by itself and the OLED shows the new IP address.

When you join **SmartParking**, your phone will warn that there's no internet. Choose **Stay connected** and turn off mobile data, or the phone may leave the network or send the page request over mobile data.

Joining can take up to about 2 minutes before the Pico gives up and starts SmartParking. The serial log prints every step (`Wi-Fi: scanning...`, `Wi-Fi: connecting ... (attempt 1 of 2)`, each status change), so you can see it's still working.

### Phone hotspot checklist

The Pico W only works with **2.4 GHz WPA2** networks.

- **iPhone:** Settings → Personal Hotspot → turn on **Maximise Compatibility** (this switches it to 2.4 GHz), and keep that screen open while the Pico connects. Otherwise the hotspot is hidden.
- **Android:** Hotspot settings → AP band **2.4 GHz**, security **WPA2-Personal**, not WPA3 or WPA2/WPA3.
- **Name:** iPhone names use a curly apostrophe (`Umar’s iPhone`). `wifi.py` matches a straight `'` too, but a plain name like `ParkingNet` is safest.
- **Same network:** the phone or laptop that opens the dashboard must be on the same hotspot. The phone that's sharing its own hotspot can open the page too.
- **Still failing?** Run `test_wifi.py`. It lists every network the Pico sees, shows each status change while joining, and ends with a verdict.

### Dashboard

- **Spots:** every spot is listed as *Free*, *Booked* or *Occupied*, with a count such as "1 of 1 spot free". When none are free the page shows **Sorry No spots left**.
- **Status card:** the spot state, when the current booking ends, and whether the gate is open.
- **Alerts:** banners at the top when a booking ends or is released. The driver who made the booking sees "Your booking time is complete. The spot is now free." Alerts stay for 10 minutes or until dismissed with ×.
- The page refreshes itself every 3 seconds.

### Making and using a booking

Making a booking: enter your name and number plate, pick a day and arrival time (or tap the timeline), choose how long, and press **Book spot**. Keep the 6-digit code: the page remembers it on that device, and **Already booked?** finds it on any other device.

At the gate: from 10 minutes before your start, press **Open gate** on your booking. The gate stays open for at least 15 seconds and closes 3 seconds after the car has passed. Use the same button to leave.

Rules, set at the top of `booking.py`:

| Constant | Default | Meaning |
|---|---|---|
| `MIN_DURATION` / `MAX_DURATION` | 15 min / 4 h | Allowed booking length |
| `MAX_AHEAD` | 7 days | How far ahead you can book |
| `EARLY_ACCESS` | 10 min | The code opens the gate this long before the start |
| `NO_SHOW` | 2 min | A booking is released if no car arrives (gate opened with the code, or a car seen by the IR sensor) within this time of its start |
| `MAX_BOOKINGS` | 30 | Bookings stored at once |

**The clock:** on Wi-Fi the Pico sets its clock from the internet (NTP). In access-point mode it has no internet, so the first browser that opens the page sets the clock. Bookings can't be made until the clock is set.

**API** (JSON): `GET /api/status`, `POST /api/book {name, plate, start, end}`, `POST /api/lookup {code}`, `POST /api/cancel {code}`, `POST /api/open {code}`. Times are Unix seconds. `/api/status` also returns `spots` (each with `state` *free*, *booked* or *occupied*), `free_spots`, and `alerts` from the last 10 minutes.

**Try it on your PC:** `python tools/preview_server.py`, then open http://localhost:8080. It runs the real `web.py` and `booking.py` with a pretend controller.

> Running these files with desktop Python (VS Code's ▶ button) fails with `ModuleNotFoundError: No module named 'machine'`. Always use MicroPico's **Run**.

---

## Configuration

All settings are constants at the top of `main.py`:

| Constant | Default | Meaning |
|---|---|---|
| `GATE_TRIGGER_CM` | `10` | Distance that counts as a car at the gate |
| `GATE_OPEN_MS` | `3000` | How long the gate stays open after the car has passed |
| `SERVO_CLOSED_DEG` / `SERVO_OPEN_DEG` | `0` / `180` | Barrier angles. 0 = `PULSE_MIN_US`, 180 = `PULSE_MAX_US` |
| `PULSE_MIN_US` / `PULSE_MAX_US` | `1300` / `2300` | Gate closed / open pulse, measured on our servo (6.5 % / 11.5 % duty at 50 Hz) |
| `IR_ACTIVE_LOW` | `True` | Set to `False` if your IR module outputs HIGH when it detects something |
| `BLOCK_WHEN_FULL` | `True` | Keep the gate closed when the spot is taken |
| `IR_SAMPLES` / `GATE_SAMPLES` | `3` / `2` | Debounce counts |
| `REMOTE_OPEN_MS` | `15000` | How long the gate stays open after **Open gate** on the web page |
| `ALERT_SHOW_MS` | `10000` | How long *TIME UP* / *NO SHOW* stays on the OLED |
| `WEB_ENABLED` | `True` | Set to `False` to run without Wi-Fi and booking |

### Servo calibration

Every SG90 is slightly different, and many can't turn a full 180°. Pushing one past its end stop makes it buzz and stick. To find your servo's positions:

1. **Check the signal** with an oscilloscope on GP16 (probe ground on GND). You should see 50 Hz (20 ms period), 3.3 V high, and a pulse between 0.5 and 2.5 ms. Use **Measure → +Width** to read the pulse exactly.
2. **Find the positions** by driving the servo from a function generator: square wave, 50 Hz, 5 Vpp, **offset +2.5 V** so it swings 0–5 V. Change DUTY until the arm sits where the gate should be closed, then open. At 50 Hz, duty % × 200 = pulse in µs, so 6.5 % = 1300 µs. Or run `test_servo_calibrate.py` and note the pulse values it prints.
3. **Set the values:** `PULSE_MIN_US` (closed) and `PULSE_MAX_US` (open) in `main.py`, and `CLOSED_DUTY` / `OPEN_DUTY` in `test_servo.py`.

---

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `No module named 'machine'` | The file ran on the PC. Use MicroPico's *Run current file on Pico* |
| Pico never joins Wi-Fi or the hotspot | Run `test_wifi.py` and follow its verdict. See the phone hotspot checklist |
| Nothing printed after `Smart Parking started.` | Wi-Fi is still trying, so wait up to 2 minutes. If no `Wi-Fi:` lines appear at all, unplug the Pico for 10 s and run `test_wifi.py` |
| Phone won't stay on *SmartParking* | Choose *Stay connected* when the phone says there's no internet, and turn off mobile data |
| Servo only vibrates, or is slow or jittery | Supply current limit too low: the SG90 draws up to about 0.7 A when it starts to move. Set the bench supply's limit to 1 A (watch for the CC light), join the grounds, and add a 470 µF capacitor |
| Servo doesn't move at all | Check the common ground and that the servo has 5 V on its red wire. Wire SIG straight to GP16, not through the level shifter. Check the signal on the orange wire with an oscilloscope |
| Servo moves once, then sticks at one end | The pulse is past the servo's end stop. See *Servo calibration* |
| Servo moves less than expected | Pulse range doesn't match your servo. See *Servo calibration* |
| Ultrasonic works in the test but not in `main.py` | The servo is pulling down the shared 5 V rail. Fix the servo power as above |
| OLED blank | Check SDA/SCL. `test_oled.py` prints the I2C address it finds (0x3C or 0x3D) |
| Spot status inverted | Change `IR_ACTIVE_LOW` |
| Booking page doesn't load | Check the phone is on the same network as the Pico (or on *SmartParking*), and that `www/index.html` was uploaded. The serial log prints the address |
| "The parking clock is not set yet" | Reload the page. In access-point mode the page sets the clock when it loads |
| Booking released straight away | No car arrived within 2 minutes of the start. Open the gate with the code or park in the spot in time, or raise `NO_SHOW` in `booking.py` |
| IR always or never detects | Turn the sensor's potentiometer to adjust its range |

---

## Known limitations and future work

- **Exit handling:** the gate opens only for cars approaching the ultrasonic sensor, or from the web page with a booking code. Drivers without a booking still need an exit trigger: either open the gate when the IR sensor shows the spot has emptied, or add an exit button.
- **Booking security:** the page uses plain HTTP on the local network and anyone who has a code can use it. Codes are random 6-digit numbers with no rate limit, which is fine for a demo but not for a real car park.
- **Walk-up overstay:** a car without a booking that parks before a booking starts can still be in the spot when the booking begins.
- Single parking spot. More IR sensors and a car counter would scale it to a multi-spot car park.
