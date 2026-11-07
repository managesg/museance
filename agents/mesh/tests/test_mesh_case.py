import asyncio
import json

import pytest

from agents.mesh import base, captions, case
from court.ledger import commit_hash, read, verify

CLOCK = lambda: "2026-11-07T20:30:00+00:00"  # noqa: E731
ORDER = ["open", "sealed", "sworn", "revealed", "ruling", "remark", "remark"]
KEYS = {"open": {"app", "case_id", "requested_by"}, "sealed": {"count", "seal"}, "sworn": {"count", "total_bond"},
        "revealed": {"count", "matched"}, "remark": {"from", "text"},
        "ruling": {"locked", "struck", "fabricated", "unsworn", "fidelity", "credibility"}}
AGENT = {"open": "bailiff", "sealed": "hoot", "sworn": "mcclusky", "revealed": "hoot", "ruling": "bailiff"}
APP1 = {"LOCKED": 3, "STRUCK": 1, "FABRICATED": 1, "UNSWORN": 0}


def mesh(runs):
    return [e for e in read(runs / "app1" / "ledger.jsonl") if e["type"].startswith("mesh.")]


def test_run_case_app1_with_fakes(runs):
    lines = []
    r = case.run_case("app1", runs=runs, clock=CLOCK, case_id="app1-t1", progress=lines.append)
    assert (r["counts"], r["claims"], r["attacks"], r["error"]) == (APP1, 5, 20, "")
    assert r["credibility_end"] == 963 and r["struck"][0]["id"] == "c03"
    assert lines == list(case.PROGRESS.values())  # R6: one per stage, 4 in all
    assert r["seal"]["p4_count"] == 75 and r["seal"]["p4_problems"] == [] and r["seal"]["matched"] == 20
    events = mesh(runs)
    assert [e["type"][5:] for e in events] == ORDER  # R2: exactly these types, in order
    for e in events:
        t, p = e["type"][5:], e["payload"]
        assert set(p) == KEYS[t] | {"agent", "caption"}, t  # no extra payload keys
        assert p["agent"] == AGENT.get(t, p.get("from")) and len(p["caption"].split()) <= 20 and "\n" not in p["caption"]
    assert events[-2]["payload"]["from"] == "hoot" and events[-1]["payload"]["from"] == "mcclusky"
    path = runs / "app1" / "ledger.jsonl"
    assert verify(path) == (True, f"{len(read(path))} events, chain intact") and r["ledger"]["ok"]
    types = [e["type"] for e in read(path)]
    assert types[4:4 + 25] == ["commit"] * 25 and types[-8:-3] == ["lock"] * 5  # judge()'s own events, in the chain
    on_file = json.loads((runs / "app1" / "ruling.json").read_text())
    assert on_file["case_id"] == "app1-t1" and on_file["record"] == [e["payload"]["caption"] for e in events]


def test_final_reply_shape(runs):
    r = case.run_case("app1", runs=runs, clock=CLOCK, case_id="app1-t2")
    text = base.with_machine_line(captions.final_reply(r), "mcclusky", cmd="raise", **case.numbers(r))
    parts = text.split("\n\n")
    assert parts[0] == "⚖️ The case: is the revived app1 the same app as the dead original?"
    assert parts[1].startswith("🐧 ") and len(parts[1].split()) <= 20
    heads = [p.split("\n")[0] for p in parts]
    i, j, k = heads.index("🔍 What the court actually did"), heads.index("💭 Thinking"), heads.index("📜 Record")
    assert i < j < k
    tests = parts[i + 1].splitlines()
    assert 3 <= len(tests) <= 4 and tests[-1].startswith("- Totals: 5 claims, 20 attacks, 2 runs per build")
    assert tests[0].startswith("- ❌ c03 struck: 1 divide 8 equals")  # strikes first, in the app's own words
    assert 2 <= len(parts[j + 1].splitlines()) <= 3 and "Seal checked" in parts[j + 1]
    record = parts[k + 1].splitlines()
    assert len(record) == 7 and record[1].startswith("2. 🦉→🔨 Sealed 20 attacks")
    assert parts[-2] == f"Ledger: {r['ledger']['entries']} entries, chain intact."
    m = json.loads(parts[-1].removeprefix("[seance] "))
    assert (m["agent"], m["locked"], m["struck"], m["fidelity"], m["chain"]) == ("mcclusky", 3, 1, r["fidelity"], True)
    assert all(len(ln.split()) <= 20 for ln in text.splitlines() if not ln.startswith("[seance]"))


def test_a_new_case_archives_the_old_ledger(runs):
    case.run_case("app1", runs=runs, case_id="app1-a")
    case.run_case("app1", runs=runs, case_id="app1-b")
    assert len(list((runs / "app1").glob("ledger-*.jsonl"))) == 1
    assert read(runs / "app1/ledger.jsonl")[0]["payload"]["case_id"] == "app1-b"


class Cheat(case.LocalParties):
    async def reveal(self, case_id, app):
        attacks = [dict(a) for a in self._attacks]
        attacks[0]["steps"] = attacks[0]["steps"] + ["click:#k7"]  # edited after the seal
        return attacks


def test_an_attack_edited_after_the_seal_is_refused(runs):
    inp = case.load_inputs("app1", runs)
    r = asyncio.run(case.hear("app1", Cheat(inp, runs), runs=runs, inputs=inp, case_id="app1-c"))
    assert (r["attacks"], r["seal"]["refused"]) == (19, [{"id": "a001", "why": "content changed after the seal"}])
    revealed = next(e["payload"] for e in mesh(runs) if e["type"] == "mesh.revealed")
    assert (revealed["count"], revealed["matched"]) == (20, 19) and "1 thrown out" in revealed["caption"]


class Mute(case.LocalParties):
    async def testify(self, case_id, app):
        raise case.CaseError("McClusky, Esq. did not answer in 240 s")


def test_a_failed_case_still_ends_with_a_ruling_event(runs):
    inp = case.load_inputs("app1", runs)
    r = asyncio.run(case.hear("app1", Mute(inp, runs), runs=runs, inputs=inp, case_id="app1-m"))
    assert r["error"] == "McClusky, Esq. did not answer in 240 s"
    last = mesh(runs)[-1]
    assert last["type"] == "mesh.ruling" and last["payload"]["caption"].startswith("🔨 Error:")
    assert all(last["payload"][k] is None for k in case.RULING_KEYS)
    text = captions.final_reply(r)
    assert "adjourned" in text and text.endswith("chain intact.")


def test_verify_reveal_keeps_only_sealed_content():
    def attack(i, step):
        a = {"id": i, "app": "app1", "screen": "s", "steps": [step], "observe": "#display"}
        return {**a, "commit": commit_hash(a)}
    a1, a2, a3 = attack("a1", "click:#k7"), attack("a2", "click:#k8"), attack("a3", "click:#k1")
    sealed = {"attacks": [{"id": "a1", "commit": a1["commit"]}, {"id": "a2", "commit": a2["commit"]},
                          {"id": "a4", "commit": "0" * 64}]}
    ok, bad = case.verify_reveal(sealed, [a1, {**a2, "steps": ["click:#k1"]}, a3, a1])
    assert ok == [a1]
    assert bad == [{"id": "a2", "why": "content changed after the seal"}, {"id": "a3", "why": "never sealed"},
                   {"id": "a1", "why": "revealed twice"}, {"id": "a4", "why": "sealed but never revealed"}]


def test_attacks_are_p4s_sealed_ids_capped_and_spread(runs):
    inp = case.load_inputs("app1", runs)
    pool, picked = case.sealed_pool("app1", inp), case.make_attacks("app1", inp)
    assert len(pool) == 75 and len(picked) == case.MAX_ATTACKS == 20 and picked[0]["id"] == "a001"
    assert [a["id"] for a in picked] == sorted(a["id"] for a in picked) and {a["screen"] for a in picked} > {"add"}
    inp["sealed"] = {**inp["sealed"], "attacks": inp["sealed"]["attacks"][:5]}
    assert [a["id"] for a in case.make_attacks("app1", inp)] == ["a001", "a002", "a003", "a004", "a005"]
    assert case.spread(list(range(105)), 20)[:3] == [0, 5, 10]


def test_inputs_come_from_runs_then_dig_out(runs):
    inp = case.load_inputs("todo", runs)  # nothing in the temp runs/: P2's dig/out/todo and the repo builds
    assert len(inp["claims"]) == 16 and inp["original"]["dir"].endswith("apps/todo/original")
    assert inp["revival"]["dir"].endswith("revive/out/todo") and len(inp["sealed"]["attacks"]) == 105
    with pytest.raises(case.MissingInput):
        case.load_inputs("../etc", runs)
    with pytest.raises(case.MissingInput, match="selectors"):
        case.load_inputs("pong", runs)
    assert case.apps(runs)["app1"] == "" and case.apps(runs)["todo"] == ""


def test_cross_runs_known_keys_only(runs):
    x = case.cross("app1", "1/8=", runs=runs)
    assert x["steps"] == ["click:#k1", "click:#kdiv", "click:#k8", "click:#keq"] and x["observe"] == "#display"
    assert (x["original"], x["revival"], x["match"], x["flaky"]) == ("0.12", "0.12 (drift)", False, False)
