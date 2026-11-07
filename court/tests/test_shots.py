"""Evidence photo tests. Run: python -m pytest -q court"""
import json
import pathlib

from court import serve, shots
from court.court import Bench, judge

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIX = ROOT / "fixtures"
REVIVAL = pathlib.Path(__file__).parent / "revival_app1"
PNG = b"\x89PNG\r\n\x1a\n"


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_shots_for_mismatches_only(tmp_path):
    claims, attacks = load("claims.json"), load("attacks.json")
    with serve.folder(FIX / "app1") as orig, serve.folder(REVIVAL) as rev:
        with Bench() as bench:
            verdicts, _ = judge(claims, attacks, orig, rev, tmp_path, bench=bench)
        index = shots.take_shots(verdicts, claims, attacks, orig, rev, tmp_path)
        index2 = shots.take_shots(verdicts, claims, attacks, orig, rev, tmp_path)  # rerun overwrites
    assert [e["ref"] for e in index] == [e["ref"] for e in index2]

    mism = {v["ref"]: v for v in verdicts if not v["match"] and not v["flaky"]}
    assert {"c03", "c05"} <= set(mism)
    sd = tmp_path / "shots"
    on_disk = json.loads((sd / "index.json").read_text(encoding="utf-8"))
    assert {e["ref"] for e in on_disk} == set(mism)

    for e in on_disk:
        v = mism[e["ref"]]
        assert e["original_text"] == v["original"] and e["revival_text"] == v["revival"]
        for key in ("original", "revival", "original_observe", "revival_observe"):
            assert e["files"][key] is not None  # #display exists in app1
            assert (sd / e["files"][key]).read_bytes()[:8] == PNG

    assert {p.name.split(".")[0] for p in sd.glob("*.png")} == set(mism)  # none for matches


def test_missing_observe_element_is_null(tmp_path):
    attack = {"id": "a9", "app": "app1", "screen": "s", "steps": ["click:#k1"], "observe": "#nope"}
    v = {"ref": "a9", "kind": "attack", "original": "x", "revival": "y", "match": False,
         "flaky": False, "claim_true": None, "shrunk_steps": []}
    with serve.folder(FIX / "app1") as url:
        index = shots.take_shots([v], [], [attack], url, url, tmp_path)
    assert index[0]["files"]["original_observe"] is None
    assert (tmp_path / "shots" / "a9.original.png").read_bytes()[:8] == PNG
