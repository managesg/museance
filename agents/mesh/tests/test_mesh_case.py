import asyncio
import json
import pathlib

import pytest

from agents.mesh import captions, case, commands
from agents.mesh.models import Ruling
from court.ledger import commit_hash, read, verify

ROOT = pathlib.Path(__file__).resolve().parents[3]
CLOCK = lambda: "2026-11-07T20:30:00+00:00"  # noqa: E731
MESH_ORDER = ["open", "summon", "sealed", "summon", "testimony", "summon", "reveal", "court", "ruling",
              "remark", "remark", "closed"]


def mesh_events(runs):
    return [e for e in read(runs / "app1" / "ledger.jsonl") if e["type"].startswith("mesh.")]


def test_run_case_app1_with_fakes(runs):
    r = case.run_case("app1", runs=runs, clock=CLOCK, case_id="app1-t1")
    assert r["counts"] == {"LOCKED": 3, "STRUCK": 1, "FABRICATED": 1, "UNSWORN": 0}
    assert (r["claims"], r["attacks"], r["refused"]) == (5, 75, 0)
    assert (r["credibility_end"], r["brier"]) == (963, 0.173)
    assert [s["id"] for s in r["struck"]] == ["c03"] and r["struck"][0]["original"] == "0.12"
    assert r["funniest"].startswith("c03:") and "90 credibility" in r["funniest"]
    traps = {(tuple(e["steps"]), e["observe"])
             for e in json.loads((ROOT / "eval/regression/app1-fixture.json").read_text())["traps"]}
    attacks = json.loads((runs / "app1/attacks.json").read_text())
    assert r["catches"] == sum((tuple(a["steps"]), a["observe"]) in traps for a in attacks) > 0
    assert set(r["remarks"]) == {"hoot", "mcclusky"} and "90 points" in r["remarks"]["hoot"]
    assert set(r) - {"remarks"} <= set(Ruling.__fields__)  # the ruling dict is the Ruling model
    Ruling(**{k: v for k, v in r.items() if k != "remarks"})

    path = runs / "app1/ledger.jsonl"
    assert verify(path)[0]
    types = [e["type"] for e in read(path)]
    assert [t[5:] for t in types if t.startswith("mesh.")] == MESH_ORDER
    court_part = types[types.index("mesh.court") + 1: types.index("mesh.ruling")]
    assert court_part == ["commit"] * 80 + ["verdict"] * 80 + ["lock"] * 5  # judge's own events, in place
    for e in mesh_events(runs):
        p = {k: v for k, v in e["payload"].items() if k != "caption"}
        assert e["payload"]["caption"] == captions.caption(e["type"][5:], p) and "\n" not in e["payload"]["caption"]
    sealed = next(e["payload"] for e in mesh_events(runs) if e["type"] == "mesh.sealed")
    assert sealed["p4_match"] and sealed["attacks"] == 75  # Hoot's live seal == P4's seal in git


def test_a_new_case_archives_the_old_ledger(runs):
    case.run_case("app1", runs=runs, case_id="app1-a")
    case.run_case("app1", runs=runs, case_id="app1-b")
    assert len(list((runs / "app1").glob("ledger-*.jsonl"))) == 1
    first = read(runs / "app1/ledger.jsonl")[0]
    assert first["seq"] == 1 and first["payload"]["case_id"] == "app1-b"


class Cheat(case.LocalParties):
    async def reveal(self, case_id, app):
        attacks = [dict(a) for a in self._attacks]
        attacks[0]["steps"] = attacks[0]["steps"] + ["click:#k7"]  # edited after the seal
        return attacks


def test_an_attack_edited_after_the_seal_is_refused(runs):
    inp = case.load_inputs("app1", runs)
    r = asyncio.run(case.hear("app1", Cheat(inp), runs=runs, inputs=inp, case_id="app1-c"))
    assert (r["refused"], r["attacks"]) == (1, 74)
    reveal = next(e["payload"] for e in mesh_events(runs) if e["type"] == "mesh.reveal")
    assert reveal["refused"] == [{"id": "a001", "why": "content changed after the seal"}]
    assert reveal["p4_problems"]  # P4's seal in git catches it too


class Mute(case.LocalParties):
    async def testify(self, case_id, app):
        raise case.CaseError("McClusky, Esq. did not answer in 240 s")


def test_a_silent_party_adjourns_the_case(runs):
    inp = case.load_inputs("app1", runs)
    r = asyncio.run(case.hear("app1", Mute(inp), runs=runs, inputs=inp, case_id="app1-m"))
    assert r == {"case_id": "app1-m", "app": "app1", "error": "McClusky, Esq. did not answer in 240 s"}
    types = [e["type"] for e in read(runs / "app1/ledger.jsonl")]
    assert types[-1] == "mesh.adjourned" and "mesh.court" not in types and "commit" not in types


def test_async_on_event_sees_every_hop_in_order(runs):
    seen = []

    async def on_event(type_, payload, caption):
        await asyncio.sleep(0)
        seen.append(type_)

    asyncio.run(case.hear("app1", on_event=on_event, runs=runs, case_id="app1-e"))
    assert seen == MESH_ORDER


def test_last_case_feeds_the_chat_templates(runs):
    assert captions.status(case.last_case("app1", runs)) == captions.no_case("app1")
    case.run_case("app1", runs=runs, case_id="app1-l")
    last = case.last_case("app1", runs)
    assert last["ruling"]["case_id"] == "app1-l" and "chain intact" in last["chain"]
    assert captions.status(last).startswith("RULING, case app1-l")
    one = captions.status(last, "c03")
    assert one.startswith("c03 STRUCK") and "'0.12'" in one and "bond of 90" in one
    assert "No claim c09" in captions.status(last, "c09")
    assert "5 claims" in captions.claims_list("app1", last["claims"], last["locks"])
    assert "FABRICATED" in captions.why_line(last["claims"][4], last["locks"][4])
    assert f"{last['ruling']['catches']} caught the revival" in captions.reveal_list("app1", last["attacks"], last["verdicts"])
    head = last["events"][-1]["hash"]
    line = captions.ledger_line("app1", len(last["events"]), last["chain"], head)
    assert head[:12] in line and line.count(" events") == 1 and "chain intact" in line


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


def test_load_inputs_names_what_is_missing(tmp_path):
    with pytest.raises(case.MissingInput) as ex:
        case.load_inputs("app1", tmp_path)
    msg = str(ex.value)
    assert "dig/pile.py app1" in msg and "dig/reader.py app1" in msg and "revival" in msg
    assert "original" not in msg  # fixtures/app1 is the original
    with pytest.raises(case.MissingInput):
        case.load_inputs("../etc", tmp_path)


def test_apps_lists_ready_and_not_ready(runs):
    docket = case.apps(runs)
    assert docket["app1"] == "" and "sheet" in docket["todo"]


def test_cross_runs_known_keys_only(runs):
    x = case.cross("app1", "1/8=", runs=runs)
    assert x["steps"] == ["click:#k1", "click:#kdiv", "click:#k8", "click:#keq"] and x["observe"] == "#display"
    assert (x["original"], x["revival"], x["match"], x["flaky"]) == ("0.12", "0.12 (drift)", False, False)
    assert not list((runs / "app1").glob("ledger*"))  # ad hoc, like the feed's bench
    with pytest.raises(commands.CrossError):
        case.cross("app1", "2+2=", runs=runs)
