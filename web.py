# Small async HTTP server for the booking web app.
#
#   GET  /                 booking page (www/index.html)
#   GET  /api/status?t=..  spot, gate and schedule  (t = browser's Unix time)
#   POST /api/book         {name, plate, start, end}  -> booking with code
#   POST /api/lookup       {code}                     -> that booking
#   POST /api/cancel       {code}
#   POST /api/open         {code}                     -> opens the gate
#
# `ctl` is the parking controller from main.py. It needs:
#   ctl.spot_occupied, ctl.gate_open, ctl.ip   (attributes)
#   ctl.open_gate()                            (method)
#
# Works with MicroPython asyncio and desktop Python asyncio.

try:
    import asyncio
except ImportError:
    import uasyncio as asyncio
import json

import clock
from booking import BookingError, EARLY_ACCESS, NO_SHOW, MIN_DURATION, MAX_DURATION, MAX_AHEAD

PAGE = "www/index.html"
MAX_BODY = 1024

_STATUS_TEXT = {200: "OK", 400: "Bad Request", 403: "Forbidden",
                404: "Not Found", 405: "Method Not Allowed", 413: "Payload Too Large"}


class HttpError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def _booking_view(b):
    return {"id": b["id"], "code": b["code"], "name": b["name"], "plate": b["plate"],
            "start": b["start"], "end": b["end"], "arrived": b["arrived"]}


def _parse_query(qs):
    out = {}
    for part in qs.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


class WebApp:
    def __init__(self, ctl, bookings, port=80):
        self.ctl = ctl
        self.bookings = bookings
        self.port = port

    async def start(self):
        return await asyncio.start_server(self._handle, "0.0.0.0", self.port)

    # ---------- HTTP plumbing ----------
    async def _handle(self, reader, writer):
        try:
            line = await reader.readline()
            if not line:
                return
            parts = line.decode().split()
            if len(parts) < 2:
                return
            method, target = parts[0], parts[1]
            length = 0
            while True:
                h = await reader.readline()
                if not h or h in (b"\r\n", b"\n"):
                    break
                name, _, value = h.decode().partition(":")
                if name.strip().lower() == "content-length":
                    length = int(value.strip() or 0)
            if length > MAX_BODY:
                raise HttpError(413, "Request too large")
            body = await reader.readexactly(length) if length else b""

            path, _, qs = target.partition("?")
            if method == "GET" and path in ("/", "/index.html"):
                await self._send_file(writer, PAGE, "text/html; charset=utf-8")
                return
            if path.startswith("/api/"):
                data = {}
                if body:
                    try:
                        data = json.loads(body.decode())
                    except ValueError:
                        raise HttpError(400, "Invalid JSON")
                result = self._api(method, path[5:], _parse_query(qs), data)
                await self._send_json(writer, 200, result)
                return
            raise HttpError(404, "Not found")
        except HttpError as e:
            await self._send_json(writer, e.status, {"ok": False, "error": e.message})
        except BookingError as e:
            await self._send_json(writer, 400, {"ok": False, "error": str(e)})
        except Exception as e:
            print("HTTP error:", e)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _send_head(self, writer, status, ctype, length=None):
        head = "HTTP/1.0 %d %s\r\nContent-Type: %s\r\nCache-Control: no-store\r\n" % (
            status, _STATUS_TEXT.get(status, ""), ctype)
        if length is not None:
            head += "Content-Length: %d\r\n" % length
        writer.write((head + "Connection: close\r\n\r\n").encode())
        await writer.drain()

    async def _send_json(self, writer, status, obj):
        body = json.dumps(obj).encode()
        await self._send_head(writer, status, "application/json", len(body))
        writer.write(body)
        await writer.drain()

    async def _send_file(self, writer, path, ctype):
        try:
            f = open(path, "rb")
        except OSError:
            raise HttpError(404, "Page not uploaded: " + path)
        await self._send_head(writer, 200, ctype)
        try:
            while True:
                chunk = f.read(1024)
                if not chunk:
                    break
                writer.write(chunk)
                await writer.drain()
        finally:
            f.close()

    # ---------- API ----------
    def _api(self, method, name, query, data):
        if name == "status":
            if method != "GET":
                raise HttpError(405, "Use GET")
            return self._status(query)
        if method != "POST":
            raise HttpError(405, "Use POST")
        if not clock.synced:
            raise HttpError(400, "The parking clock is not set yet, reload the page")

        now = clock.now()
        if name == "book":
            b = self.bookings.add(data.get("name", ""), data.get("plate", ""),
                                  data.get("start"), data.get("end"), now)
            print("Booked #%d %s %s" % (b["id"], b["plate"], b["name"]))
            return {"ok": True, "booking": _booking_view(b)}

        code = str(data.get("code", "")).strip()
        b = self.bookings.find(code)
        if b is None:
            raise HttpError(404, "No booking with that code")

        if name == "lookup":
            return {"ok": True, "booking": _booking_view(b)}
        if name == "cancel":
            self.bookings.cancel(code)
            print("Cancelled #%d" % b["id"])
            return {"ok": True}
        if name == "open":
            if not self.bookings.can_open(code, now):
                raise HttpError(403, "The gate opens %d minutes before your booking starts"
                                % (EARLY_ACCESS // 60))
            self.bookings.mark_arrived(b)
            self.ctl.open_gate()
            print("Gate opened by booking #%d" % b["id"])
            return {"ok": True}
        raise HttpError(404, "Unknown API")

    def _status(self, query):
        # Without NTP (access-point mode) the first browser sets the clock.
        if not clock.synced and "t" in query:
            try:
                clock.set_time(int(query["t"]))
                print("Clock set from browser")
            except ValueError:
                pass
        now = clock.now()
        active = self.bookings.active(now) if clock.synced else None
        return {
            "ok": True,
            "now": now,
            "clock_synced": clock.synced,
            "spot": {"occupied": self.ctl.spot_occupied,
                     "reserved": active is not None},
            "gate": {"open": self.ctl.gate_open},
            "bookings": self.bookings.public(now),
            "rules": {"min_minutes": MIN_DURATION // 60, "max_minutes": MAX_DURATION // 60,
                      "max_days_ahead": MAX_AHEAD // 86400,
                      "early_minutes": EARLY_ACCESS // 60, "no_show_minutes": NO_SHOW // 60},
        }
