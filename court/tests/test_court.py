"""P1 court tests. Run: python -m pytest -q court"""
import json
import pathlib

import pytest

from court import bailiff, ledger, serve
from court.court import Bench, judge
from court.shrink import shrink
from court.steps import StepError, parse

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIX = ROOT / "fixtures"
REVIVAL = pathlib.Path(__file__).parent / "revival_app1"
CLOCK = lambda: "2026-11-07T20:30:00+00:00"  # noqa: E731


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


# --- steps grammar -------------------------------------------------------------
def test_parse_contract_steps():
    assert parse("click:#k7") == ("click", ["#k7"])
    assert parse("type:#name:Ada: Lovelace") == ("type", ["#name", "Ada: Lovelace"])
    assert parse("key:Enter") == ("key", ["Enter"])
    assert parse("wait:250") == ("wait", ["250"])
    for bad in ["click", "click:", "tap:#x", "wait:soon", "type:#x"]:
        with pytest.raises(StepError):
            parse(bad)


# --- shrinker --------------------------------------------------------------------
def test_shrink_is_one_minimal():
    # mismatch whenever both "a" and "c" are present
    differs = lambda s: "a" in s and "c" in s  # noqa: E731
    assert shrink(["a", "b", "c", "d"], differs) == ["a", "c"]
    assert shrink(["x"], lambda s: True) == []


# --- bailiff (must agree with eval/score.py rules) -------------------------------
def test_bailiff_rules():
    claim = {"id": "x", "test": {"expect": "1"}, "label": "SEEN"}
    v = {"ref": "x", "kind": "claim", "original": "1", "claim_true": True, "flaky": False}
    assert bailiff.status(claim, v)[0] == "LOCKED"
    assert bailiff.status(claim, {**v, "claim_true": False, "original": "2"})[0] == "STRUCK"
    assert bailiff.status(claim, {**v, "flaky": True})[0] == "UNSWORN"
    assert bailiff.status(claim, None)[0] == "UNSWORN"
    fab = {**claim, "label": "FABRICATED"}
    assert bailiff.status(fab, v)[0] == "FABRICATED"
    assert bailiff.status(fab, {**v, "claim_true": False})[0] == "STRUCK"


# --- ledger ---------------------------------------------------------------------
def test_ledger_chain_and_tamper(tmp_path):
    p = tmp_path / "ledger.jsonl"
    lg = ledger.Ledger(p, clock=CLOCK)
    lg.append("commit", {"ref": "c01"})
    lg.append("verdict", {"ref": "c01", "match": True})
    assert ledger.verify(p) == (True, "2 events, chain intact")
    # reopening continues the chain
    ledger.Ledger(p, clock=CLOCK).append("lock", {"claim_id": "c01"})
    assert ledger.verify(p)[0]
    lines = p.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1].replace('"match":true', '"match":false')
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok, msg = ledger.verify(p)
    assert not ok and msg.startswith("seq 2")


def test_commit_hash_matches_p4_definition():
    import hashlib
    obj = {"id": "a01", "text": "7 × 8 ÷ 2 → 28", "steps": ["click:#k1"], "commit": "ignored"}
    body = {k: v for k, v in obj.items() if k != "commit"}
    want = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    assert ledger.commit_hash(obj) == want


def test_edited_after_commit_is_refused(tmp_path):
    c = dict(load("claims.json")[0])
    c["commit"] = ledger.commit_hash(c)
    c["test"] = {**c["test"], "expect": "16"}
    with pytest.raises(ValueError, match="edited after commit"):
        judge([c], [], "http://unused", "http://unused", tmp_path, clock=CLOCK, bench=object())


# --- end to end on fixtures/app1 vs the drifted test revival ----------------------
@pytest.fixture(scope="module")
def bench():
    with Bench() as b:
        yield b


def test_fixture_run_reproduces_fixture_verdicts(tmp_path, bench):
    claims, attacks = load("claims.json"), load("attacks.json")
    with serve.folder(FIX / "app1") as orig, serve.folder(REVIVAL) as rev:
        verdicts, locks = judge(claims, attacks, orig, rev, tmp_path, clock=CLOCK, bench=bench)

    want = {v["ref"]: v for v in load("verdicts.json")}
    got = {v["ref"]: v for v in verdicts if v["kind"] == "claim"}
    for ref, w in want.items():
        for k in ("original", "revival", "claim_true", "match", "flaky"):
            assert got[ref][k] == w[k], (ref, k, got[ref][k], w[k])
        if not w["match"]:
            assert got[ref]["shrunk_steps"], ref  # every mismatch gets a repro
        else:
            assert got[ref]["shrunk_steps"] == []

    # shrunk repro is smaller than or equal to the original test and still reproduces
    assert got["c05"]["shrunk_steps"] == ["click:#k7", "click:#kdiv", "click:#keq"]

    assert {r["claim_id"]: r["status"] for r in locks} == {
        "c01": "LOCKED", "c02": "LOCKED", "c03": "STRUCK", "c04": "LOCKED", "c05": "FABRICATED"}

    # attacks get verdicts too, claim_true is null for them
    att = [v for v in verdicts if v["kind"] == "attack"]
    assert len(att) == len(attacks) and all(v["claim_true"] is None for v in att)

    # files + ledger: commits first, then verdicts, then locks; chain intact
    assert json.loads((tmp_path / "verdicts.json").read_text(encoding="utf-8")) == verdicts
    evs = ledger.read(tmp_path / "ledger.jsonl")
    kinds = [e["type"] for e in evs]
    n = len(claims) + len(attacks)
    assert kinds == ["commit"] * n + ["verdict"] * n + ["lock"] * len(claims)
    assert ledger.verify(tmp_path / "ledger.jsonl")[0]


def test_flaky_build_is_unsworn_not_struck(tmp_path, bench):
    d = tmp_path / "flaky"
    d.mkdir()
    (d / "index.html").write_text(
        '<div id="display"></div><script>document.getElementById("display").innerText='
        'String(Math.random())</script>', encoding="utf-8")
    claim = {"id": "f1", "app": "x", "screen": "s", "text": "t", "tier": "A", "label": "SEEN",
             "confidence": 0.9, "bond": 100,
             "test": {"steps": ["wait:1"], "observe": "#display", "expect": "0.5"}}
    with serve.folder(d) as url:
        verdicts, locks = judge([claim], [], url, url, tmp_path / "out", clock=CLOCK, bench=bench)
    assert verdicts[0]["flaky"] is True and verdicts[0]["match"] is False
    assert locks[0]["status"] == "UNSWORN"


def test_missing_element_is_an_observation_not_a_crash(tmp_path, bench):
    attack = {"id": "a9", "app": "app1", "screen": "s", "steps": ["click:#nope"], "observe": "#display"}
    with serve.folder(FIX / "app1") as url:
        verdicts, _ = judge([], [attack], url, url, tmp_path, clock=CLOCK, bench=bench)
    assert verdicts[0]["original"].startswith("ERROR:step 0 click:#nope")
    assert verdicts[0]["match"] is True and verdicts[0]["flaky"] is False


# --- review fixes ----------------------------------------------------------------
def test_parse_type_selectors_with_colons():
    assert parse("type:input:nth-child(2):hi") == ("type", ["input:nth-child(2)", "hi"])
    assert parse('type:[name="a:b"]:x') == ("type", ['[name="a:b"]', "x"])
    assert parse("type:#name:Ada: Lovelace") == ("type", ["#name", "Ada: Lovelace"])
    assert parse("type:li:not(.a):first-child:z") == ("type", ["li:not(.a):first-child", "z"])


def test_shrinker_stays_on_the_same_bug(tmp_path, bench):
    c03 = next(c for c in load("claims.json") if c["id"] == "c03")
    with serve.folder(FIX / "app1") as orig, serve.folder(REVIVAL) as rev:
        v, _ = judge([c03], [], orig, rev, tmp_path, clock=CLOCK, bench=bench)
        assert v[0]["shrunk_steps"] == ["click:#k1", "click:#kdiv", "click:#k8", "click:#keq"]
        obs = c03["test"]["observe"]
        assert bench.run(orig, v[0]["shrunk_steps"], obs) == "0.12"
        assert bench.run(rev, v[0]["shrunk_steps"], obs) == "0.13"


def test_original_error_is_unsworn_not_struck(tmp_path, bench):
    claim = {"id": "e1", "app": "app1", "screen": "s", "text": "t", "tier": "A", "label": "SEEN",
             "confidence": 0.9, "bond": 100,
             "test": {"steps": ["click:#nope"], "observe": "#display", "expect": "0"}}
    with serve.folder(FIX / "app1") as url:
        v, locks = judge([claim], [], url, url, tmp_path, clock=CLOCK, bench=bench)
    assert v[0]["claim_true"] is None
    assert locks[0]["status"] == "UNSWORN" and "could not run" in locks[0]["reason"]
    assert bailiff.status({**claim, "label": "FABRICATED"}, v[0])[0] == "FABRICATED"


def test_unreachable_url_is_unsworn(tmp_path, bench):
    claim = {"id": "u1", "app": "x", "screen": "s", "text": "t", "tier": "A", "label": "SEEN",
             "confidence": 0.9, "bond": 100, "test": {"steps": [], "observe": "#display", "expect": "0"}}
    v, locks = judge([claim], [], "http://127.0.0.1:9", "http://127.0.0.1:9", tmp_path, clock=CLOCK, bench=bench)
    assert v[0]["original"].startswith("ERROR:load ")
    assert locks[0]["status"] == "UNSWORN"


def test_type_sends_key_events_and_settles(tmp_path, bench):
    d = tmp_path / "kbd"
    d.mkdir()
    (d / "index.html").write_text(
        '<input id="i" value="old"><div id="o"></div><script>'
        'i.addEventListener("keyup",()=>{setTimeout(()=>{o.innerText="up:"+i.value},120)})</script>',
        encoding="utf-8")
    with serve.folder(d) as url:
        assert bench.run(url, ["type:#i:hello"], "#o") == "up:hello"


def test_computed_commit_is_flagged_in_ledger(tmp_path):
    c = dict(load("claims.json")[0])
    committed = {**c, "id": "zz", "commit": None}
    committed["commit"] = ledger.commit_hash(committed)
    judge([c, committed], [], "http://unused", "http://unused", tmp_path, clock=CLOCK,
          bench=type("B", (), {"run": lambda self, *a: "x"})())
    evs = [e["payload"] for e in ledger.read(tmp_path / "ledger.jsonl") if e["type"] == "commit"]
    assert evs[0].get("computed_by_court") is True and "computed_by_court" not in evs[1]


def test_ledger_concurrent_writers_and_truncated_tail(tmp_path):
    import threading
    p = tmp_path / "l.jsonl"
    a, b = ledger.Ledger(p, clock=CLOCK), ledger.Ledger(p, clock=CLOCK)

    def go(lg, tag):
        for i in range(20):
            lg.append("x", {"w": tag, "i": i})
    ts = [threading.Thread(target=go, args=(a, "a")), threading.Thread(target=go, args=(b, "b"))]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert ledger.verify(p) == (True, "40 events, chain intact")
    with p.open("a", encoding="utf-8") as f:
        f.write('{"seq":41,"ts"')  # crash mid-write
    assert len(ledger.read(p)) == 40
    assert ledger.verify(p)[0] is False
    ledger.Ledger(p, clock=CLOCK).append("x", {})  # new writer continues from the last good event
    assert len(ledger.read(p)) == 41 and ledger.verify(p)[0]


def test_ledger_two_processes(tmp_path):
    import subprocess
    import sys
    p = tmp_path / "mp.jsonl"
    code = ("import sys; from court.ledger import Ledger; lg = Ledger(sys.argv[1]); "
            "[lg.append('mesh.x', {'w': sys.argv[2], 'i': i}) for i in range(20)]")
    procs = [subprocess.Popen([sys.executable, "-c", code, str(p), w], cwd=ROOT) for w in "ab"]
    assert [q.wait() for q in procs] == [0, 0]
    assert ledger.verify(p) == (True, "40 events, chain intact")
