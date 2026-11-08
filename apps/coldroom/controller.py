"""FreshMart Store #214 dairy walk-in cold-room controller (MODELED, not vendor code).

python apps/coldroom/controller.py --port 8101              # ORIGINAL: legacy, no auth on writes
python apps/coldroom/controller.py --port 8102 --patched    # PATCHED: setpoint/defrost need PIN + limits

HTTP contract (CORS on, 127.0.0.1 only):
  GET  /state                      -> {temp, setpoint, compressor, defrost, alarm, minute, defrost_len, spoil}
  POST /setpoint {value, pin}      -> {ok, msg}
  POST /defrost  {minutes, pin}    -> {ok, msg}
  POST /tick     {n}               -> state      (1 tick = 60 simulated seconds; no wall clock)
  POST /reset    {optional: temp, setpoint, minute, compressor, defrost_len} -> state
The control model and the 2-line patch live in court/coldroom.py (ColdRoomModel), shared with the
court's in-process copy so both builds are byte-for-byte the same logic apart from the patch.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from court.coldroom import ColdRoomModel  # noqa: E402


def make_server(port: int, patched: bool, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    model = ColdRoomModel(patched)
    lock = threading.Lock()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, obj):
            b = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self):
            if self.path.split("?")[0] != "/state":
                return self._send(404, {"error": "not found"})
            with lock:
                self._send(200, {**model.state(), "build": "patched" if patched else "original"})

        def do_POST(self):
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except ValueError:
                return self._send(400, {"ok": False, "msg": "bad JSON"})
            path = self.path.split("?")[0]
            with lock:
                try:
                    if path == "/state":
                        return self._send(200, model.state())
                    if path == "/reset":
                        return self._send(200, model.reset(**body))
                    if path == "/tick":
                        return self._send(200, model.tick(max(0, min(10000, int(body.get("n", 1))))))
                    if path == "/setpoint":
                        return self._send(200, model.write_setpoint(body["value"], body.get("pin")))
                    if path == "/defrost":
                        return self._send(200, model.write_defrost(body["minutes"], body.get("pin")))
                except (KeyError, TypeError, ValueError) as e:
                    return self._send(400, {"ok": False, "msg": f"bad request: {e}"})
            self._send(404, {"error": "not found"})

    srv = ThreadingHTTPServer((host, port), H)
    srv.daemon_threads = True
    return srv


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="coldroom-controller")
    ap.add_argument("--port", type=int, default=8101)
    ap.add_argument("--patched", action="store_true")
    a = ap.parse_args(argv)
    srv = make_server(a.port, a.patched)
    print(f"{'PATCHED' if a.patched else 'ORIGINAL'} cold-room controller on http://127.0.0.1:{a.port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
