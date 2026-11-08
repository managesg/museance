"""ICS dialect tests. Run: python -m pytest -q court/tests/test_ics.py -p no:asyncio"""
import pathlib
import socket
import sys

import pytest

from court.ics import ModbusBench, judge_modbus, parse_observe, parse_step
from court.steps import StepError

CTRL = str(pathlib.Path(__file__).parent / "ics" / "legacy_cold_room.py")
CLOCK = lambda: "2026-11-07T20:30:00+00:00"  # noqa: E731


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def claim(cid, text, steps, observe, expect):
    return {"id": cid, "app": "cold_room", "text": text, "test": {"steps": steps, "observe": observe, "expect": expect},
            "tier": "A", "label": "SEEN", "confidence": 0.9, "bond": 100}


CLAIMS = [
    claim("k1", "compressor on above setpoint+1.0", ["hr:0=60"], "coil:0", "1"),
    claim("k2", "compressor off below", ["hr:0=45"], "coil:0", "0"),
    claim("k3", "no alarm before 600 s", ["hr:0=100", "tick:599"], "coil:2", "0"),
    claim("k4", "alarm at 600 s", ["hr:0=100", "tick:600"], "coil:2", "1"),
    claim("k5", "defrost starts at 6 h", ["tick:21600"], "coil:1", "1"),
    claim("k6", "defrost ends after 20 min", ["tick:22800"], "coil:1", "0"),
]
ATTACK = {"id": "s1", "app": "cold_room", "steps": ["hr:1=250"], "observe": "hr:1"}


def test_parsing():
    assert parse_step("hr:1=250") == ("hr", 1, 250)
    assert parse_step("coil:3=1") == ("coil", 3, 1)
    assert parse_step("wait:50") == ("wait", 50, 0)
    assert parse_step("tick:60", clock_reg=2) == ("tick", 2, 60)
    assert parse_observe("hr:0,coil:3") == [("hr", 0), ("coil", 3)]
    for bad in ["hr:1", "hr:x=1", "coil:1=2", "wait:soon", "poke:1", "hr:1=70000", "tick:5", "hr"]:
        with pytest.raises(StepError):
            parse_step(bad)
    for bad in ["", "foo:1", "hr:", "hr:1,xx:2"]:
        with pytest.raises(StepError):
            parse_observe(bad)


def test_observe_format_and_rejection_is_observation():
    port = free_port()
    url = f"modbus://127.0.0.1:{port}"
    b = ModbusBench(launch={url: [sys.executable, CTRL, "--port", str(port), "--hardened"]}, clock_reg=2)
    assert b.run(url, ["hr:0=60", "hr:1=250"], "hr:0,hr:1,coil:0") == "hr0=60,hr1=40,coil0=1"
    assert any("rejected" in e for e in b.events)
    assert b.run(url, [], "hr:1") == "40"  # fresh controller every run


def test_original_vs_itself_all_locked(tmp_path):
    port = free_port()
    url = f"modbus://127.0.0.1:{port}"
    launch = {url: [sys.executable, CTRL, "--port", str(port)]}
    verdicts, locks = judge_modbus(CLAIMS, [], url, url, tmp_path, launch=launch, clock_reg=2, clock=CLOCK)
    assert [l["status"] for l in locks] == ["LOCKED"] * 6
    assert all(v["match"] and not v["flaky"] for v in verdicts)


def test_original_vs_hardened(tmp_path):
    po, pr = free_port(), free_port()
    uo, ur = f"modbus://127.0.0.1:{po}", f"modbus://127.0.0.1:{pr}"
    launch = {uo: [sys.executable, CTRL, "--port", str(po)],
              ur: [sys.executable, CTRL, "--port", str(pr), "--hardened"]}
    verdicts, locks = judge_modbus(CLAIMS, [ATTACK], uo, ur, tmp_path, launch=launch, clock_reg=2, clock=CLOCK)
    claims_v = [v for v in verdicts if v["kind"] == "claim"]
    assert len(claims_v) == 6 and all(v["match"] and not v["flaky"] for v in claims_v)
    assert [l["status"] for l in locks] == ["LOCKED"] * 6
    atk = verdicts[-1]
    assert (atk["original"], atk["revival"], atk["match"], atk["flaky"]) == ("250", "40", False, False)
