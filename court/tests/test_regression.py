"""Court vs P4's app1 regression set (copy in tests/data, from origin/p4-skeptic). Run: python -m pytest -q court"""
import json
import pathlib
import subprocess
import sys

import pytest

from court import serve
from court.court import Bench
from court.regression import check, load

ROOT = pathlib.Path(__file__).resolve().parents[2]
ORIGINAL = ROOT / "fixtures" / "app1"
REVIVAL = pathlib.Path(__file__).parent / "revival_app1"  # drifts: rounds instead of truncating, no /0 guard
REG = pathlib.Path(__file__).parent / "data" / "app1-regression.json"


def test_load_flattens_good_and_traps():
    entries = load(REG)
    assert [e["group"] for e in entries] == ["good"] * 12 + ["trap"] * 8
    assert all(set(e["test"]) == {"steps", "observe", "expect"} for e in entries)


@pytest.fixture(scope="module")
def bench():
    with Bench() as b:
        yield b


def test_original_vs_itself_has_zero_false_strikes(bench):
    with serve.folder(ORIGINAL) as url:
        rep = check(load(REG), url, url, bench=bench)
    c = rep["counts"]
    assert (c["false_strikes"], c["struck"], c["mismatches"], c["flaky"]) == (0, 0, 0, 0)
    # every expect P4 wrote (good and traps) is what the court sees on the original
    assert all(r["status"] == "LOCKED" and r["original"] == r["expect"] for r in rep["rows"])


def test_drifted_revival_trips_the_division_traps(bench, tmp_path):
    traps = [e for e in load(REG) if e["group"] == "trap"]
    with serve.folder(ORIGINAL) as orig, serve.folder(REVIVAL) as rev:
        rep = check(traps, orig, rev, bench=bench)
    rows = {r["id"]: r for r in rep["rows"]}
    caught = {i for i, r in rows.items() if r["mismatch"]}
    assert caught == {"t01", "t02"}  # 1/8 rounding and /0, the two drifts in revival_app1
    assert (rows["t01"]["original"], rows["t01"]["revival"]) == ("0.12", "0.13")
    assert (rows["t02"]["original"], rows["t02"]["revival"]) == ("Error", "Infinity")
    assert all(rows[i]["shrunk_steps"] for i in caught)
    # a trap whose revival differs is still LOCKED as a claim: the original does show expect
    assert all(r["status"] == "LOCKED" for r in rows.values()) and rep["counts"]["flaky"] == 0


def _cli(*args):
    # subprocess: a second sync Playwright can't start while the module-scoped bench is open
    return subprocess.run([sys.executable, "-m", "court.regression", *map(str, args)],
                          cwd=ROOT, capture_output=True, text=True, timeout=120)


def test_cli_exit_code_and_report(tmp_path):
    reg = tmp_path / "one.json"
    reg.write_text(json.dumps({"good": [{"id": "g", "steps": ["click:#k7"], "observe": "#display", "expect": "7"}],
                               "traps": []}), encoding="utf-8")
    out = tmp_path / "rep.json"
    r = _cli(reg, "--original-dir", ORIGINAL, "--revival-dir", ORIGINAL, "--out", out)
    assert r.returncode == 0, r.stderr
    assert json.loads(out.read_text(encoding="utf-8"))["counts"]["false_strikes"] == 0
    # a wrong expect on a good entry is a strike -> exit 1
    reg.write_text(json.dumps([{"id": "g", "steps": ["click:#k7"], "observe": "#display", "expect": "8"}]),
                   encoding="utf-8")
    r = _cli(reg, "--original-dir", ORIGINAL, "--revival-dir", ORIGINAL)
    assert r.returncode == 1 and "false strikes 1" in r.stdout, r.stdout + r.stderr
