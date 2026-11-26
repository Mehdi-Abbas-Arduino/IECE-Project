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

# ---------------- Booking rules (all values in seconds) ----------------
# CHANGE these to suit the demo. The web page reads them from the Pico, so
# only this file needs editing. Re-upload booking.py after changing.
MIN_DURATION = 15 * 60          # CHANGE: shortest booking (15 min)
MAX_DURATION = 4 * 60 * 60      # CHANGE: longest booking (4 h)
MAX_AHEAD = 7 * 24 * 60 * 60    # how far ahead a booking can start (7 days)
EARLY_ACCESS = 10 * 60          # CHANGE: the code opens the gate this long before the start (10 min)
NO_SHOW = 2 * 60                # CHANGE: release a RESERVED spot back to FREE if no car arrives
                                #   by start + this (2 min). A car counts as arrived when the booking
                                #   code opens the gate or the IR sensor sees a car in the spot.
ALERT_KEEP = 10 * 60            # alerts stay on the web page for this long (10 min)
MAX_ALERTS = 10                 # most alerts kept in memory
MAX_BOOKINGS = 30               # most bookings stored at once (limited by the Pico's memory)
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
        self.alerts = []          # recent alerts for the web page, newest last (not saved)
        self._alert_id = 0
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

    def car_in_spot(self, now):
        """Call while the IR sensor sees a car: the active booking counts as arrived."""
        b = self.active(now)
        if b and not b["arrived"]:
            self.mark_arrived(b)
            return b
        return None

    # ---------- alerts ----------
    def alert(self, now, kind, text, booking=None):
        """Store an alert for the web page. kind: "ended" or "no_show"."""
        self._alert_id += 1
        self.alerts.append({"id": self._alert_id, "time": now, "kind": kind, "text": text,
                            "booking_id": booking["id"] if booking else None})
        del self.alerts[:-MAX_ALERTS]
        print("ALERT:", text)

    def recent_alerts(self, now):
        return [a for a in self.alerts if now - a["time"] < ALERT_KEEP]

    def tick(self, now):
        """Drop finished bookings and no-shows, raising an alert for each.
        Returns a list of (booking, reason) with reason "ended" or "no_show"."""
        removed = []
        for b in self.items:
            if b["end"] <= now:
                removed.append((b, "ended"))
            elif not b["arrived"] and now >= b["start"] + NO_SHOW:
                removed.append((b, "no_show"))
        if removed:
            for b, reason in removed:
                self.items.remove(b)
                if reason == "ended":
                    self.alert(now, "ended", "Booking #%d (%s) time is complete. The spot is now free."
                               % (b["id"], b["plate"]), b)
                else:
                    self.alert(now, "no_show", "Booking #%d (%s) cancelled: no car arrived within %d min. "
                               "The spot is now free." % (b["id"], b["plate"], NO_SHOW // 60), b)
            self._save()
        return removed
