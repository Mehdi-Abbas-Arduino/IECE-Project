# IECE Project – Smart Parking System

MicroPython firmware for a Raspberry Pi Pico W smart parking system.

- **HC-SR04 ultrasonic** at the entrance detects a car and opens the **SG90 servo** barrier.
- **IR obstacle sensor** detects whether the parking spot is occupied.
- **Green / red LEDs** show spot free / occupied.
- **SSD1306 OLED** (128×64, I2C) shows spot, gate and distance status.

## Pin map

| Part | GPIO |
|---|---|
| HC-SR04 TRIG / ECHO (via level shifter ch 1–2) | GP2 / GP3 |
| OLED SDA / SCL (I2C0) | GP4 / GP5 |
| IR sensor OUT | GP15 |
| Servo signal (via level shifter ch 3) | GP16 |
| Green LED / Red LED (220 Ω each) | GP28 / GP27 |

Full wiring, power budget and parts list: [docs/circuit-design.html](docs/circuit-design.html) (download and open in a browser).

## Files

| File | Purpose |
|---|---|
| `main.py` | Main application (runs on boot) |
| `hcsr04.py`, `ssd1306.py` | Sensor and display drivers |
| `test_leds.py`, `test_ir.py`, `test_ultrasonic.py`, `test_servo.py`, `test_oled.py` | Individual component tests |
| `test_servo_calibrate.py` | Finds the servo's real pulse range |

## Running

Use the **MicroPico** VS Code extension: *Upload project to Pico*, then *Run current file on Pico*.
Running with desktop Python fails with `No module named 'machine'`.
