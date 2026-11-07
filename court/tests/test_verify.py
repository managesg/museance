"""run_case + court.verify. Run: python -m pytest -q court/tests/test_verify.py -p no:asyncio"""
import json
import pathlib
import shutil

import pytest

from court import ledger, serve, verify
from court.court import Bench, run_case

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIX = ROOT / "fixtures"
REVIVAL = pathlib.Path(__file__).parent / "revival_app1"
CLOCK = lambda: "2026-11-07T22:45:00+00:00"  # noqa: E731


def make_case(runs: pathlib.Path, app: str, claims, attacks=None):
    d = runs / app
    d.mkdir(parents=True)
    (d / "claims.json").write_text(json.dumps(claims), encoding="utf-8")
    if attacks is not None:
        (d / "attacks.json").write_text(json.dumps(attacks), encoding="utf-8")
    return d


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


@pytest.fixture  # function scope: the verify CLI tests start their own sync Playwright
def bench():
    with Bench() as b:
        yield b


def test_run_case_summary_and_files(tmp_path, bench):
    runs = tmp_path / "runs"
    d = make_case(runs, "app1", load("claims.json"), load("attacks.json"))
    with serve.folder(FIX / "app1") as orig, serve.folder(REVIVAL) as rev:
        s = run_case("app1", orig, rev, runs=runs, bench=bench, clock=CLOCK)
    assert set(s) == {"counts", "struck", "fabricated", "ledger_head"}  # stable shape for the uAgent
    assert s["counts"] == {"LOCKED": 3, "STRUCK": 1, "UNSWORN": 0, "FABRICATED": 1}
    assert s["struck"] == ["c03"] and s["fabricated"] == ["c05"]
    for f in ("verdicts.json", "locks.json", "ledger.jsonl"):
        assert (d / f).is_file()
    assert s["ledger_head"] == ledger.read(d / "ledger.jsonl")[-1]["hash"]
    assert ledger.verify(d / "ledger.jsonl")[0]


def test_run_case_without_attacks_and_missing_claims(tmp_path, bench):
    runs = tmp_path / "runs"
    make_case(runs, "app1", load("claims.json")[:1])  # no attacks.json
    with serve.folder(FIX / "app1") as orig:
        s = run_case("app1", orig, orig, runs=runs, bench=bench, clock=CLOCK)
    assert s["counts"]["LOCKED"] == 1 and s["struck"] == []
    with pytest.raises(FileNotFoundError, match="claims.json"):
        run_case("nope", "http://x", "http://y", runs=runs, bench=bench)


def test_verify_exit_1_when_struck(tmp_path, capsys):
    runs = tmp_path / "runs"
    make_case(runs, "app1", load("claims.json"))
    code = verify.main(["--app", "app1", "--original", str(FIX / "app1"), "--revival", str(REVIVAL),
                        "--runs", str(runs), "--workers", "1"])
    out = capsys.readouterr().out
    assert code == 1
    assert "c03" in out and "STRUCK" in out and "1 / 8 rounds to 0.13" in out
    assert "LOCKED 3 | STRUCK 1 | UNSWORN 0 | FABRICATED 1" in out


def test_verify_exit_0_and_flaky_is_unsworn_not_struck(tmp_path, capsys):
    runs = tmp_path / "runs"
    site = tmp_path / "flaky"
    site.mkdir()
    (site / "index.html").write_text(
        '<div id="display"></div><script>document.getElementById("display").innerText='
        'String(Math.random())</script>', encoding="utf-8")
    claim = {"id": "f1", "app": "flaky", "screen": "s", "text": "shows 0.5", "tier": "A", "label": "SEEN",
             "confidence": 0.9, "bond": 100,
             "test": {"steps": ["wait:1"], "observe": "#display", "expect": "0.5"}}
    make_case(runs, "flaky", [claim])
    code = verify.main(["--app", "flaky", "--original", str(site), "--revival", str(site),
                        "--runs", str(runs), "--workers", "1"])
    out = capsys.readouterr().out
    assert code == 0  # flaky must never strike
    assert "f1" in out and "UNSWORN" in out and "STRUCK 0" in out
