"""P2 lane test: pile -> reader -> medium on the app1 fixture, with a stubbed model. Run: py -3 -m pytest -q dig"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "dig"), str(ROOT / "agents"), str(ROOT / "eval")]
import pile, reader, medium
from commit import commit_hash

SEL = json.loads((ROOT / "eval/regression/app1-selectors.json").read_text())
SHEET_REPLY = """```json
[{"screen":"add","text":"7 + 8 = shows 15","label":"SEEN","citations":["e002"],"conflicts":[]},
 {"screen":"divide","text":"7 / 0 = shows Error","label":"SEEN","citations":["e003","e999"],"conflicts":[]},
 {"screen":"multiply","text":"7 x 8 = shows 56","label":"SEEN","citations":[],"conflicts":[]}]
```"""
CLAIM_REPLY = json.dumps([
    {"line": "b001", "text": "7 + 8 shows 15", "test": {"steps": ["click:#k7", "click:#kadd", "click:#k8", "click:#keq"], "observe": "#display", "expect": "15"}, "confidence": 0.9},
    {"line": "b002", "text": "7 / 0 shows Error", "test": {"steps": ["click:#k7", "click:#kdiv", "click:#k0", "click:#keq"], "observe": "#display", "expect": "Error"}, "confidence": 1.4},
    {"line": "b003", "text": "7 x 8 shows 56", "test": {"steps": ["click:#k7", "click:#kmul", "click:#k8", "click:#keq"], "observe": "#display", "expect": "56"}, "confidence": 0.5},
    {"line": "b001", "text": "uses a made-up button", "test": {"steps": ["click:#k9"], "observe": "#display", "expect": "9"}, "confidence": 0.5},
])


def test_pipeline():
    ev = pile.build("app1", ROOT / "dig/piles/app1")
    assert [e["id"] for e in ev] == ["e001", "e002", "e003", "e004"] and pile.words(ev) > 50
    lines = reader.read(ev, chat=lambda *a: SHEET_REPLY, provider="X")
    assert lines[1]["citations"] == ["e003"]                     # invented citation dropped
    assert lines[2]["label"] == "GUESSED"                        # SEEN without citations is downgraded
    claims, dropped = medium.cards("app1", {"lines": lines}, ev, SEL, chat=lambda *a: CLAIM_REPLY)
    assert len(claims) == 3 and dropped == ["uses a made-up button"]  # unknown selector rejected
    assert claims[1]["confidence"] == 1.0 and claims[1]["bond"] == 250  # clamped
    assert claims[0]["tier"] == "C" and claims[0]["label"] == "SEEN"
    assert claims[2]["label"] == "FABRICATED" and claims[2]["tier"] == "D"
    req = json.loads((ROOT / "contracts/claim.schema.json").read_text())["required"]
    for c in claims:
        assert all(k in c for k in req) and c["commit"] == commit_hash(c)


def test_subq_sets_confidence():
    ev = pile.build("app1", ROOT / "dig/piles/app1")
    lines = reader.read(ev, chat=lambda *a: SHEET_REPLY, provider="X")
    claims, _ = medium.cards("app1", {"lines": lines}, ev, SEL, chat=lambda *a: CLAIM_REPLY, decide=lambda *a: 0.4)
    assert all(c["confidence"] == 0.4 and c["bond"] == 40 for c in claims)
    assert claims[0]["medium_confidence"] == 0.9 and claims[0]["commit"] == commit_hash(claims[0])


def test_duplicate_test_dropped():
    ev = pile.build("app1", ROOT / "dig/piles/app1")
    lines = reader.read(ev, chat=lambda *a: SHEET_REPLY, provider="X")
    two = json.loads(CLAIM_REPLY)[:1] * 2
    two[1] = {**two[1], "text": "contradicting claim, same test"}
    claims, dropped = medium.cards("app1", {"lines": lines}, ev, SEL, chat=lambda *a: json.dumps(two))
    assert len(claims) == 1 and dropped == ["contradicting claim, same test (same test as c01)"]
