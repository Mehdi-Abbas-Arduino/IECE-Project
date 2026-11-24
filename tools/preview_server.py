# Run the booking web app on your PC, without the Pico.
#
#   python tools/preview_server.py        then open http://localhost:8080
#
# Uses the real web.py and booking.py with a pretend controller: the spot
# shows "occupied" for a while after the gate is opened with a booking code.
# Run this with desktop Python, not on the Pico.

import asyncio
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import clock          # noqa: E402
from booking import Bookings   # noqa: E402
from web import WebApp         # noqa: E402

PORT = int(os.environ.get("PORT", "8080"))


class FakeController:
    def __init__(self):
        self.ip = "localhost"
        self._gate_until = 0
        self._parked_from = None

    @property
    def gate_open(self):
        return time.time() < self._gate_until

    @property
    def spot_occupied(self):
        # Pretend the car parks 5 s after the gate opens and stays 2 minutes.
        return self._parked_from is not None and self._parked_from <= time.time() < self._parked_from + 120

    def open_gate(self):
        self._gate_until = time.time() + 15
        self._parked_from = time.time() + 5


async def main():
    clock.mark_synced()   # the PC clock is already correct
    store = os.path.join(tempfile.gettempdir(), "smart_parking_preview.json")
    bookings = Bookings(store)
    server = await WebApp(FakeController(), bookings, port=PORT).start()
    print("Booking page preview: http://localhost:%d  (Ctrl+C to stop)" % PORT)
    print("Bookings stored in", store)
    while True:
        bookings.tick(clock.now())
        await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
