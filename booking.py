# Booking schedule for the single parking spot.
#
# A booking reserves the spot for a time window [start, end). While a booking
# is active, the gate will not open for walk-up cars; the driver who booked
# opens it from the web page with their 6-digit booking code.
#
# Times are Unix seconds (UTC). Bookings are saved to a JSON file so they
# survive a reboot. Works on MicroPython and on desktop Python.

import json
import os

MIN_DURATION = 15 * 60          # shortest booking
MAX_DURATION = 4 * 60 * 60      # longest booking
MAX_AHEAD = 7 * 24 * 60 * 60    # how far ahead a booking can start
EARLY_ACCESS = 10 * 60          # code opens the gate this long before the start
NO_SHOW = 15 * 60               # release the spot if nobody arrives by start + this
MAX_BOOKINGS = 30
NAME_MAX = 24
PLATE_MAX = 10

_replace = getattr(os, "replace", os.rename)


class BookingError(Exception):
    pass


def _new_code():
    return "%06d" % (int.from_bytes(os.urandom(4), "big") % 1000000)


def clean_plate(plate):
    plate = " ".join(str(plate).upper().split())
    if not 2 <= len(plate) <= PLATE_MAX:
        raise BookingError("Plate must be 2-%d characters" % PLATE_MAX)
    for ch in plate:
        if not (ch.isdigit() or ("A" <= ch <= "Z") or ch in " -"):
            raise BookingError("Plate may only use letters, digits, spaces and -")
    return plate


def clean_name(name):
    name = " ".join(str(name).split())
    if not 1 <= len(name) <= NAME_MAX:
        raise BookingError("Name must be 1-%d characters" % NAME_MAX)
    for ch in name:
        if ord(ch) < 32 or ch in "<>":
            raise BookingError("Name contains invalid characters")
    return name


class Bookings:
    def __init__(self, path="bookings.json"):
        self.path = path
        self.items = []
        self.next_id = 1
        self._load()

    # ---------- persistence ----------
    def _load(self):
        try:
            with open(self.path) as f:
                data = json.load(f)
            self.items = data.get("items", [])
            self.next_id = data.get("next_id", 1)
        except (OSError, ValueError):
            self.items, self.next_id = [], 1

    def _save(self):
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump({"items": self.items, "next_id": self.next_id}, f)
            _replace(tmp, self.path)
        except OSError as e:
            print("Could not save bookings:", e)

    # ---------- queries ----------
    def active(self, now):
        """The booking whose window contains `now`, or None."""
        for b in self.items:
            if b["start"] <= now < b["end"]:
                return b
        return None

    def find(self, code):
        code = str(code).strip()
        for b in self.items:
            if b["code"] == code:
                return b
        return None

    def public(self, now):
        """Schedule without names or codes, safe to show to everyone."""
        return [
            {"id": b["id"], "start": b["start"], "end": b["end"],
             "active": b["start"] <= now < b["end"], "arrived": b["arrived"]}
            for b in self.items
        ]

    # ---------- changes ----------
    def add(self, name, plate, start, end, now):
        name = clean_name(name)
        plate = clean_plate(plate)
        try:
            start, end = int(start), int(end)
        except (TypeError, ValueError):
            raise BookingError("Invalid start or end time")
        if start < now - 5 * 60:
            raise BookingError("Start time is in the past")
        start = max(start, now)
        if end - start < MIN_DURATION - 60:
            raise BookingError("Bookings must be at least %d minutes" % (MIN_DURATION // 60))
        if end - start > MAX_DURATION:
            raise BookingError("Bookings can be at most %d hours" % (MAX_DURATION // 3600))
        if start > now + MAX_AHEAD:
            raise BookingError("You can book up to %d days ahead" % (MAX_AHEAD // 86400))
        if len(self.items) >= MAX_BOOKINGS:
            raise BookingError("The schedule is full, try again later")
        for b in self.items:
            if start < b["end"] and b["start"] < end:
                raise BookingError("That time overlaps another booking")

        code = _new_code()
        while self.find(code):
            code = _new_code()
        booking = {"id": self.next_id, "code": code, "name": name, "plate": plate,
                   "start": start, "end": end, "arrived": False, "created": now}
        self.next_id += 1
        self.items.append(booking)
        self.items.sort(key=lambda b: b["start"])
        self._save()
        return booking

    def cancel(self, code):
        b = self.find(code)
        if b is None:
            return False
        self.items.remove(b)
        self._save()
        return True

    def can_open(self, code, now):
        """Booking for this code if it may open the gate right now, else None."""
        b = self.find(code)
        if b and b["start"] - EARLY_ACCESS <= now < b["end"]:
            return b
        return None

    def mark_arrived(self, b):
        if not b["arrived"]:
            b["arrived"] = True
            self._save()

    def tick(self, now):
        """Drop finished bookings and no-shows. Returns the removed bookings."""
        removed = [b for b in self.items
                   if b["end"] <= now
                   or (not b["arrived"] and now >= b["start"] + NO_SHOW)]
        if removed:
            for b in removed:
                self.items.remove(b)
            self._save()
        return removed
