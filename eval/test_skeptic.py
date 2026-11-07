import json, pathlib, shutil, subprocess, sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from commit import commit_hash
from skeptic import generate
from skeptic_codex import parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "contracts" / "attack.schema.json").read_text())
SEL = json.loads((ROOT / "eval" / "regression" / "app1-selectors.json").read_text())
REG = ROOT / "eval" / "regression" / "app1-fixture.json"


def test_attacks_match_schema():
    attacks = generate("app1", SEL)
    assert len(attacks) > 20
    assert len({a["id"] for a in attacks}) == len(attacks)
    for a in attacks:
        assert all(k in a for k in SCHEMA["required"] + ["commit"])
        assert set(a) <= set(SCHEMA["properties"])
        assert a["steps"] and all(s.startswith("click:") for s in a["steps"])
        assert a["commit"] == commit_hash(a)


def test_commit_stable_and_sensitive():
    a = generate("app1", SEL)[0]
    assert commit_hash(a) == commit_hash(dict(reversed(list(a.items()))))
    assert commit_hash(a) == commit_hash({k: v for k, v in a.items() if k != "commit"})
    assert commit_hash({**a, "steps": a["steps"] + ["click:#k7"]}) != commit_hash(a)
    assert generate("app1", SEL) == generate("app1", SEL)


def test_no_claim_text_in_attacks():
    blob = json.dumps(generate("app1", SEL)).lower()
    for c in json.loads((ROOT / "fixtures" / "claims.json").read_text(encoding="utf-8")):
        assert c["text"].lower() not in blob
    assert "claims" not in (ROOT / "eval" / "skeptic.py").read_text()


def test_codex_parse_validates():
    flat = ["#k7", "#kc"]
    reply = 'ok [{"screen":"digit","steps":["click:#k7","wait:5"]},{"screen":"digit","steps":["click:#nope"]},{"screen":"bad","steps":["click:#k7"]},{"screen":"digit","steps":["junk"]}]'
    out = parse(reply, "app1", "#display", ["digit"], flat)
    assert len(out) == 1 and out[0]["commit"] == commit_hash(out[0])


def test_regression_shape():
    d = json.loads(REG.read_text())
    assert len(d["good"]) == 12 and len(d["traps"]) == 8
    ids = [r["id"] for r in d["good"] + d["traps"]]
    assert len(set(ids)) == 20
    assert ids[:12] == [f"g{i:02d}" for i in range(1, 13)] and ids[12:] == [f"t{i:02d}" for i in range(1, 9)]
    for r in d["good"] + d["traps"]:
        assert r["steps"] and r["observe"] == "#display" and isinstance(r["expect"], str)


@pytest.mark.skipif(not shutil.which("node"), reason="node missing")
def test_regression_expects_match_fixture_app():
    got = json.loads(subprocess.run(["node", str(ROOT / "eval" / "run_fixture.js"), str(REG)], capture_output=True, text=True, check=True).stdout)
    d = json.loads(REG.read_text())
    assert {r["id"]: r["expect"] for r in d["good"] + d["traps"]} == got
