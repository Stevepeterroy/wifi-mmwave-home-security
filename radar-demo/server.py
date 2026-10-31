"""Local radar demo: genuine recorded previews and an optional ESP serial reader."""
import argparse
import json
import queue
import re
import threading
import time
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from parser import PreviewParser, describe

ROOT = Path(__file__).resolve().parent
LOCK = threading.RLock()
STATE = {"connected": False, "radar_verified": False, "port": None, "version": None,
         "scan_running": False, "scan_pending": False, "message": "Connect an ESP to use live sensing.",
         "last_frame": None, "frames": [], "status": {}, "logs": [], "stop_acknowledged": None}
WORKER = None


def set_state(**values):
    with LOCK:
        STATE.update(values)


def ports():
    try:
        from serial.tools import list_ports
        return [{"port": p.device, "name": p.description} for p in list_ports.comports() if p.vid]
    except ImportError:
        return []


class EspReader(threading.Thread):
    def __init__(self, port, transport=None):
        super().__init__(daemon=True)
        self.port = port
        self.jobs = queue.Queue()
        self.close_requested = threading.Event()
        self.parser = PreviewParser()
        self.partial = b""
        self.serial = None
        self.last_input = time.monotonic()
        self.deadline = None
        self.verified = False
        self.transport = transport

    def handle(self, line):
        now = time.time()
        with LOCK:
            STATE["logs"] = (STATE["logs"] + [line])[-45:]
            if "[STATUS " in line:
                STATE["status"] = {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", line)}
            if "[RADAR]" in line:
                self.add_frames(self.parser.push(line, now))

    def add_frames(self, frames):
        with LOCK:
            for frame in frames:
                STATE["last_frame"] = frame
                STATE["frames"] = (STATE["frames"] + [frame])[-100:]

    def receive(self, seconds):
        end = time.monotonic() + seconds
        reply = []
        while time.monotonic() < end and not self.close_requested.is_set():
            raw = self.serial.read(max(1, min(self.serial.in_waiting, 8192)))
            if raw:
                self.last_input = time.monotonic()
                self.partial += raw
                while b"\n" in self.partial:
                    line, self.partial = self.partial.split(b"\n", 1)
                    text = line.rstrip(b"\r").decode("utf8", "backslashreplace")
                    reply.append(text)
                    self.handle(text)
                if len(self.partial) > 16384:
                    self.partial = b""
                    raise RuntimeError("Serial line exceeded the preview reader limit.")
            if time.monotonic() - self.last_input > .5:
                self.add_frames(self.parser.flush())
        return "\n".join(reply)

    def command(self, command, expected=None, seconds=1.1):
        # HTTPS needs two polls for a command and its diagnostic reply.
        # Keep the existing USB timing while allowing the network round trip.
        if self.transport is not None:
            seconds = max(seconds, 1.5)
        self.serial.write((command + "\n").encode())
        self.serial.flush()
        if expected:
            # Configuration replies can exceed the old 0.8-second USB window.
            # Return promptly on acknowledgement, with a bounded wait and no resend.
            end = time.monotonic() + max(seconds, 4 if self.transport is not None else 3)
            parts = []
            while time.monotonic() < end and not self.close_requested.is_set():
                parts.append(self.receive(min(.1, end - time.monotonic())))
                response = "\n".join(parts)
                if expected in response or "Unsupport" in response or "<Fail" in response:
                    break
            response = "\n".join(parts)
        else:
            response = self.receive(seconds)
        if expected and (expected not in response or "Unsupport" in response or "<Fail" in response):
            raise RuntimeError("Radar did not acknowledge: " + command)
        return response

    def verify(self):
        response = self.command("mmwc version", seconds=1.3)
        match = re.search(r"MMW version:([^\s]+)", response)
        if not match or "<Success 0>" not in response:
            raise RuntimeError("ESP responds, but no readable radar version reply was received.")
        version = match[1]
        self.verified = True
        set_state(radar_verified=True, version=version)
        return version

    def stop_scan(self):
        try:
            self.command("mmwc stop", "<Success 0>")
            set_state(scan_running=False, stop_acknowledged=True, message="Scan stopped; radar acknowledged.")
        except Exception:
            set_state(scan_running=False, stop_acknowledged=False, message="Stop reply missing. The diagnostic firmware also has a 25-second stop watchdog.")
        self.deadline = None
        self.add_frames(self.parser.flush())

    def scan(self):
        if self.verify() != "V4.130.4.2":
            raise RuntimeError("This demo's scan settings are verified only for V4.130.4.2.")
        self.command("CONFIRM_VERSION", "confirmed")
        # UART0/PB0 provides a bounded text preview. Do not configure UART1/PA8's
        # binary baud rate here: this reader neither consumes nor decodes PA8.
        for command in ["mmwc stop", "mmwc mode 1 2", "mmwc chirp_num 1",
                        "mmwc freq 58000 0", "mmwc range 10000 40", "mmwc veloc 3000 375",
                        "mmwc frame 200 100", "mmwc coord cart", "mmwc data 3dpoints",
                        "mmwc uart on", "mmwc report points 100"]:
            self.command(command, "<Success 0>", seconds=.8)
        self.parser = PreviewParser()
        set_state(frames=[], last_frame=None, message="Starting the 20-second live scan…", stop_acknowledged=None)
        self.command("CAPTURE_RESET", "[CAPTURE_RESET]", seconds=.4)
        self.command("mmwc start", "<Success 0>", seconds=1.2)
        self.deadline = time.monotonic() + 22
        set_state(scan_running=True, message="Live scan running. Move in front of the radar.")

    def run(self):
        try:
            if self.transport is not None:
                self.serial = self.transport
            else:
                import serial
                self.serial = serial.Serial(port=None, baudrate=115200, timeout=.05, write_timeout=2)
                self.serial.dtr = False
                self.serial.rts = False
                self.serial.port = self.port
                self.serial.open()
                # Native USB CDC requires DTR; the UART bridge must avoid the reset combination.
                from serial.tools import list_ports
                if any(p.device == self.port and p.vid == 0x303A for p in list_ports.comports()):
                    self.serial.dtr = True
            self.receive(2.5)
            info = self.command("INFO", seconds=1.2)
            if "[INFO] ready=1" not in info or "control=RX16/TX17/115200" not in info:
                raise RuntimeError("Compatible ESP diagnostic firmware was not detected.")
            set_state(connected=True, message="ESP connected; checking the radar…")
            self.command("CONTROL_MATRIX", "[CONTROL_MATRIX]", seconds=.4)
            self.command("PIN_FIX", "result=0", seconds=.4)
            for attempt in range(3):
                try:
                    self.verify()
                    break
                except RuntimeError:
                    if attempt == 2:
                        raise
            set_state(message="Radar connected. Start a scan to receive fresh previews.")
            while not self.close_requested.is_set():
                self.receive(.1)
                if self.deadline and time.monotonic() >= self.deadline:
                    self.stop_scan()
                try:
                    job = self.jobs.get_nowait()
                except queue.Empty:
                    continue
                try:
                    if job == "scan":
                        self.scan()
                    elif job == "stop":
                        self.stop_scan()
                except Exception as exc:
                    if self.verified:
                        self.stop_scan()
                    set_state(message=str(exc))
                finally:
                    set_state(scan_pending=False)
        except Exception as exc:
            set_state(message=str(exc), radar_verified=False)
        finally:
            if self.serial:
                if self.verified:
                    try:
                        # This also runs on a requested disconnect, without receive()'s cancellation guard.
                        self.serial.write(b"mmwc stop\n")
                        self.serial.flush()
                    except Exception:
                        pass
                self.serial.close()
            set_state(connected=False, scan_running=False, scan_pending=False, radar_verified=False)


class Handler(BaseHTTPRequestHandler):
    def reply(self, value, code=200, content_type="application/json"):
        data = json.dumps(value).encode() if content_type == "application/json" else value
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            return self.reply((ROOT / "index.html").read_bytes(), content_type="text/html; charset=utf-8")
        if path == "/api/replay":
            return self.reply(json.loads((ROOT / "recorded-preview.json").read_text()))
        if path == "/api/state":
            with LOCK:
                value = json.loads(json.dumps(STATE))
            value["ports"] = ports()
            value["now"] = time.time()
            value["observation"] = describe(value["last_frame"])
            return self.reply(value)
        if path == "/api/export":
            with LOCK:
                value = {"source": "live ESP UART0 console preview", "exported_at": datetime.now(timezone.utc).isoformat(),
                         "complete_binary_cloud": False, "frames": STATE["frames"], "version": STATE["version"]}
            return self.reply(value)
        return self.reply({"error": "Not found"}, 404)

    def do_POST(self):
        global WORKER
        # The dashboard is local-only; reject cross-origin requests to hardware controls.
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).netloc != self.headers.get("Host"):
            return self.reply({"error": "Cross-origin request rejected"}, 403)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 4096:
                raise ValueError("Request too large")
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("Expected a JSON object")
            path = urlparse(self.path).path
            if path == "/api/connect":
                with LOCK:
                    if WORKER and WORKER.is_alive():
                        raise ValueError("Disconnect the current ESP first")
                    if body.get("port") not in [p["port"] for p in ports()]:
                        raise ValueError("Select an available USB serial port")
                    set_state(port=body["port"], message="Connecting…", frames=[], last_frame=None, status={}, logs=[], version=None)
                    WORKER = EspReader(body["port"])
                    WORKER.start()
            elif path == "/api/disconnect":
                if WORKER:
                    WORKER.close_requested.set()
            elif path in ("/api/scan", "/api/stop"):
                if not WORKER or not WORKER.is_alive() or not STATE["radar_verified"]:
                    raise ValueError("Connect and verify the radar first")
                with LOCK:
                    if path == "/api/scan" and (STATE["scan_running"] or STATE["scan_pending"]):
                        raise ValueError("A scan is already running or preparing")
                    if path == "/api/scan":
                        set_state(scan_pending=True, message="Preparing the live scan…")
                    WORKER.jobs.put("scan" if path == "/api/scan" else "stop")
            else:
                return self.reply({"error": "Not found"}, 404)
            return self.reply({"accepted": True})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return self.reply({"error": str(exc)}, 400)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("--port", type=int, default=8767)
    config = args.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", config.port), Handler)
    print(f"Radar demo: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        if WORKER:
            WORKER.close_requested.set()
            WORKER.join(timeout=3)
    finally:
        server.server_close()
