"""Regenerate court/ics/sample_run: legacy cold room (no auth) vs --hardened, judged by the Court.
Run from repo root: python court/ics/make_sample.py"""
import json
import pathlib
import socket
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from court.ics import judge_modbus  # noqa: E402

CTRL = str(ROOT / "court" / "tests" / "ics" / "legacy_cold_room.py")
OUT = pathlib.Path(__file__).parent / "sample_run"
OBS = "hr:0,hr:1,coil:0,coil:1,coil:2"


def state(hr0, hr1, c0, c1, c2):
    return f"hr0={hr0},hr1={hr1},coil0={c0},coil1={c1},coil2={c2}"


def claim(cid, text, steps, expect):
    return {"id": cid, "app": "coldroom", "text": text, "test": {"steps": steps, "observe": OBS, "expect": expect},
            "tier": "A", "label": "SEEN", "evidence": ["modbus-map"], "confidence": 0.9, "bond": 100}


CLAIMS = [
    claim("cr01", "Compressor runs when room is above setpoint + 1.0 C", ["hr:0=60"], state(60, 40, 1, 0, 0)),
    claim("cr02", "Compressor stays off when room is near setpoint", ["hr:0=45"], state(45, 40, 0, 0, 0)),
    claim("cr03", "No high-temp alarm before 600 s above setpoint + 4.0 C", ["hr:0=100", "tick:599"], state(100, 40, 1, 0, 0)),
    claim("cr04", "High-temp alarm after 600 s above setpoint + 4.0 C", ["hr:0=100", "tick:600"], state(100, 40, 1, 0, 1)),
    claim("cr05", "Defrost starts at 6 h of simulated time", ["tick:21600"], state(0, 40, 0, 1, 0)),
    claim("cr06", "Defrost ends 20 min later", ["tick:22800"], state(0, 40, 0, 0, 0)),
]
ATTACKS = [
    {"id": "sec-setpoint-unauth", "app": "coldroom", "observe": OBS,
     "steps": ["hr:0=100", "hr:1=250", "tick:600"]},
    {"id": "sec-setpoint-range", "app": "coldroom", "observe": OBS, "steps": ["hr:9=4242", "hr:1=500"]},
    {"id": "sec-wrong-pin", "app": "coldroom", "observe": OBS, "steps": ["hr:9=1111", "hr:1=100"]},
]


def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


if __name__ == "__main__":
    po, pr = port(), port()
    uo, ur = f"modbus://127.0.0.1:{po}", f"modbus://127.0.0.1:{pr}"
    launch = {uo: [sys.executable, CTRL, "--port", str(po)],
              ur: [sys.executable, CTRL, "--port", str(pr), "--hardened"]}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claims.json").write_text(json.dumps(CLAIMS, indent=1) + "\n", encoding="utf-8")
    (OUT / "attacks.json").write_text(json.dumps(ATTACKS, indent=1) + "\n", encoding="utf-8")
    (OUT / "ledger.jsonl").unlink(missing_ok=True)
    v, locks = judge_modbus(CLAIMS, ATTACKS, uo, ur, OUT, launch=launch, clock_reg=2)
    for x in v:
        print(x["ref"], x["match"], x["flaky"], x["original"], "|", x["revival"])
    print([l["status"] for l in locks])
