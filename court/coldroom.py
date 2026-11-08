"""MUSÉANCE cold-room court (role 2). Deterministic, no AI.

python -m court.coldroom --port 8103 [--original http://127.0.0.1:8101] [--patched http://127.0.0.1:8102]

POST /run  -> {"verdicts": [...], "ledger_head": "<sha256>", "source": "live" | "in-process model",
              "counts": {...}}
GET  /health -> {"ok": true, "source": ...}
Replays c1..c6 (control, must MATCH) and sec-setpoint, sec-defrost (security, must DIFFER) on the
ORIGINAL and the PATCHED controller, twice per build, through the controller HTTP contract
(/reset, /setpoint, /defrost, /tick, /state). Two runs that disagree = flaky = UNSWORN, never STRUCK.
Writes runs/coldroom/verdicts.json, locks.json and appends a sha256 hash-chained ledger.jsonl.
If the controllers on :8101/:8102 don't answer GET /state, an in-process copy of the model is used
(and "source" says so), so the court never fakes "live".
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from court import bailiff
from court.ledger import Ledger, commit_hash, read as read_ledger

PIN = "4242"
DEFAULTS = {"temp": 4.0, "setpoint": 4.0, "minute": 0, "compressor": False, "defrost_len": 20}


# --------------------------------------------------------------------------- model (contract copy)
class ColdRoomModel:
    """In-process copy of the controller model in the contract. patched=True adds the patch only."""

    def __init__(self, patched: bool):
        self.patched = patched
        self.reset()

    def reset(self, **init):
        s = {**DEFAULTS, **{k: v for k, v in init.items() if k in DEFAULTS}}
        self.temp, self.setpoint = float(s["temp"]), float(s["setpoint"])
        self.minute, self.compressor = int(s["minute"]), bool(s["compressor"])
        self.defrost_len = int(s["defrost_len"])
        self.defrost = self.alarm = False
        self.high_min = self.above8_min = 0
        self.spoil = 0.0
        return self.state()

    def state(self):
        return {"temp": round(self.temp, 2), "setpoint": round(self.setpoint, 2), "compressor": self.compressor,
                "defrost": self.defrost, "alarm": self.alarm, "minute": self.minute,
                "defrost_len": self.defrost_len, "spoil": round(self.spoil, 1)}

    def write_setpoint(self, value, pin=None):
        if self.patched and (str(pin) != PIN or not 0.0 <= float(value) <= 8.0):  # PATCH
            return {"ok": False, "msg": "write rejected: unlock required + out of range"}
        self.setpoint = float(value)
        return {"ok": True, "msg": f"setpoint {float(value):.1f}"}

    def write_defrost(self, minutes, pin=None):
        if self.patched and (str(pin) != PIN or int(minutes) > 20):  # PATCH
            return {"ok": False, "msg": "write rejected: unlock required + max 20 min"}
        self.defrost_len = int(minutes)
        return {"ok": True, "msg": f"defrost {int(minutes)} min"}

    def _step(self):
        self.minute += 1
        # defrost windows start at every 6 h boundary (minute 360, 720, ...)
        self.defrost = self.minute >= 360 and (self.minute % 360) < self.defrost_len
        if self.defrost:
            self.compressor = False
            self.temp += 0.25
        else:
            if self.temp > self.setpoint + 1.0:
                self.compressor = True
            elif self.temp < self.setpoint - 1.0:
                self.compressor = False
            self.temp += -0.3 if self.compressor else 0.15
        self.temp = max(-5.0, min(30.0, round(self.temp, 4)))
        if not self.defrost and self.temp > self.setpoint + 4.0:
            self.high_min += 1
        else:
            self.high_min = 0  # alarm suppressed during defrost
        self.alarm = self.high_min >= 10
        self.above8_min = self.above8_min + 1 if self.temp > 8.0 else 0
        if self.above8_min > 30:
            self.spoil = min(100.0, self.spoil + 2.0)

    def tick(self, n=1):
        for _ in range(int(n)):
            self._step()
        return self.state()


# --------------------------------------------------------------------------- backends
class ModelBackend:
    def __init__(self, patched: bool):
        self.m = ColdRoomModel(patched)

    def reset(self, **init):
        return self.m.reset(**init)

    def state(self):
        return self.m.state()

    def setpoint(self, value, pin=None):
        return self.m.write_setpoint(value, pin)

    def defrost(self, minutes, pin=None):
        return self.m.write_defrost(minutes, pin)

    def tick(self, n=1):
        return self.m.tick(n)


class HttpBackend:
    """Controller HTTP contract: GET /state, POST /setpoint|/defrost|/tick|/reset."""

    def __init__(self, base: str, timeout: float = 10):
        self.base, self.timeout = base.rstrip("/"), timeout

    def _call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:  # a rejected write is an observation, not a crash
            try:
                return json.loads(e.read() or b"{}") | {"ok": False}
            except ValueError:
                return {"ok": False, "msg": f"HTTP {e.code}"}

    def reset(self, **init):
        return self._call("POST", "/reset", init or {})

    def state(self):
        return self._call("GET", "/state")

    def setpoint(self, value, pin=None):
        return self._call("POST", "/setpoint", {"value": value, "pin": pin})

    def defrost(self, minutes, pin=None):
        return self._call("POST", "/defrost", {"minutes": minutes, "pin": pin})

    def tick(self, n=1):
        return self._call("POST", "/tick", {"n": n})


def reachable(base: str) -> bool:
    try:
        with urllib.request.urlopen(base.rstrip("/") + "/state", timeout=2) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------- tests (the docket)
def regs(s) -> str:
    """Contract value format: hr0 temp x10, hr1 setpoint x10, coil0 compressor, coil1 defrost, coil2 alarm."""
    return (f"hr0={round(float(s['temp']) * 10)},hr1={round(float(s['setpoint']) * 10)},"
            f"coil0={int(bool(s['compressor']))},coil1={int(bool(s['defrost']))},coil2={int(bool(s['alarm']))}")


def _c1(b):
    b.reset(temp=5.2)
    return f"coil0={int(bool(b.tick(1)['compressor']))}"


def _c2(b):
    b.reset(temp=2.8, compressor=True)
    return f"coil0={int(bool(b.tick(1)['compressor']))}"


def _c3(b):
    b.reset(temp=12.0)
    s9 = b.tick(9)
    s10 = b.tick(1)
    return f"coil2@9={int(bool(s9['alarm']))},coil2@10={int(bool(s10['alarm']))}"


def _c4(b):
    b.reset(minute=359)
    n = sum(int(bool(b.tick(1)["defrost"])) for _ in range(30))
    return f"defrost_ticks={n}"


def _c5(b):
    b.reset()
    mx = 0
    for _ in range(720):
        mx = max(mx, int(bool(b.tick(1)["alarm"])))
    return f"max_alarm={mx}"


def _c6(b):
    b.reset(minute=359)
    s = b.tick(50)
    return f"temp_le_5={int(float(s['temp']) <= 5.0)}"


def _sec_setpoint(b):
    b.reset()
    r = b.setpoint(25.0)  # no PIN
    return f"ok={int(bool(r.get('ok')))}," + regs(b.state())


def _sec_defrost(b):
    b.reset()
    r = b.defrost(120)  # no PIN, longer than 20 min
    return f"ok={int(bool(r.get('ok')))},defrost_len={b.state()['defrost_len']}"


CLAIMS = [
    ("c1", "Compressor turns on when the room is above setpoint + 1 °C (5.2 °C, 1 tick).", _c1, "coil0=1",
     ["reset temp=5.2", "tick 1", "observe compressor"]),
    ("c2", "Compressor turns off when the room is below setpoint - 1 °C (2.8 °C, 1 tick).", _c2, "coil0=0",
     ["reset temp=2.8 compressor=on", "tick 1", "observe compressor"]),
    ("c3", "High-temp alarm fires only after 10 minutes above setpoint + 4 °C.", _c3, "coil2@9=0,coil2@10=1",
     ["reset temp=12", "tick 9", "observe alarm", "tick 1", "observe alarm"]),
    ("c4", "Defrost runs every 6 h for exactly 20 minutes.", _c4, "defrost_ticks=20",
     ["reset minute=359", "tick 30 (count defrost)"]),
    ("c5", "No alarm during 12 h of normal cooling (defrost included).", _c5, "max_alarm=0",
     ["reset", "tick 720 (max alarm)"]),
    ("c6", "The room recovers to 5.0 °C or below after a defrost.", _c6, "temp_le_5=1",
     ["reset minute=359", "tick 50", "observe temp"]),
]
ATTACKS = [
    ("sec-setpoint", "Unauthenticated setpoint write to 25.0 °C.", _sec_setpoint,
     ["reset", "POST /setpoint value=25.0 (no pin)", "observe ok + registers"]),
    ("sec-defrost", "Unauthenticated defrost length change to 120 min.", _sec_defrost,
     ["reset", "POST /defrost minutes=120 (no pin)", "observe ok + defrost_len"]),
]


def claim_docs():
    return [{"id": cid, "app": "coldroom", "screen": "dairy walk-in", "text": text,
             "test": {"steps": steps, "observe": "state", "expect": expect},
             "tier": "A", "label": "SEEN", "evidence": ["contract: FreshMart cold-room model"],
             "confidence": 0.9, "bond": 100, "sworn_by": "medium"}
            for cid, text, _, expect, steps in CLAIMS]


def attack_docs():
    return [{"id": aid, "app": "coldroom", "screen": "dairy walk-in", "text": text, "steps": steps,
             "observe": "state"} for aid, text, _, steps in ATTACKS]


# --------------------------------------------------------------------------- the court
RUNS_PER_BUILD = 2
_LOCK = threading.Lock()


def run_case(original, patched, out_dir="runs/coldroom", clock=None) -> dict:
    """Judge both builds. `original`/`patched` are backends (HttpBackend or ModelBackend)."""
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with _LOCK:  # one trial at a time: tests reset shared controller state
        ledger = Ledger(out / "ledger.jsonl", clock=clock)
        claims, attacks = claim_docs(), attack_docs()
        for kind, items in (("claim", claims), ("attack", attacks)):
            for it in items:
                ledger.append("commit", {"kind": kind, "ref": it["id"], "commit": commit_hash(it)})
        verdicts = []
        procs = [(cid, "claim", fn, expect) for cid, _, fn, expect, _ in CLAIMS] + \
                [(aid, "attack", fn, None) for aid, _, fn, _ in ATTACKS]
        for ref, kind, fn, expect in procs:
            o = [fn(original) for _ in range(RUNS_PER_BUILD)]
            r = [fn(patched) for _ in range(RUNS_PER_BUILD)]
            flaky = len(set(o)) > 1 or len(set(r)) > 1
            v = {"ref": ref, "kind": kind, "original": o[0], "revival": r[0],
                 "claim_true": (o[0] == expect) if kind == "claim" else None,
                 "match": (not flaky) and o[0] == r[0], "flaky": flaky, "shrunk_steps": []}
            verdicts.append(v)
            ledger.append("verdict", v)
        lock_rows = bailiff.locks(claims, verdicts)
        for row in lock_rows:
            ledger.append("lock", row)
        (out / "verdicts.json").write_text(json.dumps(verdicts, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        (out / "locks.json").write_text(json.dumps(lock_rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        head = read_ledger(out / "ledger.jsonl")[-1]["hash"]
    counts = {s: sum(1 for x in lock_rows if x["status"] == s) for s in ("LOCKED", "STRUCK", "UNSWORN", "FABRICATED")}
    ctrl = [v for v in verdicts if v["kind"] == "claim"]
    sec = [v for v in verdicts if v["kind"] == "attack"]
    return {"verdicts": verdicts, "locks": lock_rows, "ledger_head": head, "counts": counts,
            "control_match": f"{sum(v['match'] for v in ctrl)}/{len(ctrl)}",
            "attacks_blocked": f"{sum((not v['match']) and not v['flaky'] for v in sec)}/{len(sec)}",
            "flaky": sum(v["flaky"] for v in verdicts)}


def backends(original_url, patched_url):
    if reachable(original_url) and reachable(patched_url):
        return HttpBackend(original_url), HttpBackend(patched_url), "live"
    return ModelBackend(False), ModelBackend(True), "in-process model"


# --------------------------------------------------------------------------- HTTP server :8103
class Handler(BaseHTTPRequestHandler):
    original_url = "http://127.0.0.1:8101"
    patched_url = "http://127.0.0.1:8102"
    out_dir = "runs/coldroom"

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path.split("?")[0] in ("/health", "/"):
            live = reachable(self.original_url) and reachable(self.patched_url)
            return self._send(200, {"ok": True, "source": "live" if live else "in-process model"})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.split("?")[0] != "/run":
            return self._send(404, {"error": "not found"})
        try:
            o, p, source = backends(self.original_url, self.patched_url)
            res = run_case(o, p, self.out_dir)
            res.pop("locks", None)
            self._send(200, {**res, "source": source})
        except Exception as e:  # noqa: BLE001
            self._send(500, {"error": f"{type(e).__name__}: {e}"[:300]})


def make_server(port=8103, host="127.0.0.1", original="http://127.0.0.1:8101",
                patched="http://127.0.0.1:8102", out_dir="runs/coldroom"):
    h = type("ColdRoomCourt", (Handler,), {"original_url": original, "patched_url": patched, "out_dir": out_dir})
    srv = ThreadingHTTPServer((host, port), h)
    srv.daemon_threads = True
    return srv


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="court.coldroom", description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=8103)
    ap.add_argument("--original", default="http://127.0.0.1:8101")
    ap.add_argument("--patched", default="http://127.0.0.1:8102")
    ap.add_argument("--out", default="runs/coldroom")
    ap.add_argument("--once", action="store_true", help="run the docket once, print the summary, exit")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if a.once:
        o, p, source = backends(a.original, a.patched)
        res = run_case(o, p, a.out)
        for v in res["verdicts"]:
            print(f"{v['ref']:13} {v['kind']:6} match={v['match']!s:5} flaky={v['flaky']!s:5} "
                  f"original={v['original']} | patched={v['revival']}")
        print(f"\nsource={source} control {res['control_match']} identical | attacks blocked "
              f"{res['attacks_blocked']} | flaky {res['flaky']} | locks {res['counts']} | ledger {res['ledger_head'][:12]}")
        return 0
    srv = make_server(a.port, original=a.original, patched=a.patched, out_dir=a.out)
    print(f"cold-room court on http://127.0.0.1:{a.port}  POST /run  (controllers {a.original} | {a.patched})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
