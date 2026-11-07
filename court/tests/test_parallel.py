"""workers=3 must equal workers=1: same verdicts, same ledger order, chain intact."""
import json
import pathlib

from court import ledger, serve
from court.court import judge

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIX = ROOT / "fixtures"
REVIVAL = pathlib.Path(__file__).parent / "revival_app1"
CLOCK = lambda: "2026-11-07T20:30:00+00:00"  # noqa: E731


def _load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_parallel_matches_sequential(tmp_path):
    claims, attacks = _load("claims.json"), _load("attacks.json")
    with serve.folder(FIX / "app1") as orig, serve.folder(REVIVAL) as rev:
        v1, l1 = judge(claims, attacks, orig, rev, tmp_path / "w1", clock=CLOCK, workers=1)
        v3, l3 = judge(claims, attacks, orig, rev, tmp_path / "w3", clock=CLOCK, workers=3)
    assert v3 == v1 and l3 == l1
    assert [v["ref"] for v in v3] == [i["id"] for i in claims + attacks]
    e1, e3 = ledger.read(tmp_path / "w1" / "ledger.jsonl"), ledger.read(tmp_path / "w3" / "ledger.jsonl")
    assert [(e["type"], e["payload"].get("ref", e["payload"].get("claim_id"))) for e in e3] == \
           [(e["type"], e["payload"].get("ref", e["payload"].get("claim_id"))) for e in e1]
    assert [e["hash"] for e in e3] == [e["hash"] for e in e1]  # fixed clock: byte-identical chain
    assert ledger.verify(tmp_path / "w3" / "ledger.jsonl")[0]
