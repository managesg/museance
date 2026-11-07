import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from score import brier, credibility, fidelity, statuses
from case_file import build_case

FX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
CLAIMS = json.loads((FX / "claims.json").read_text(encoding="utf-8"))
VERDICTS = json.loads((FX / "verdicts.json").read_text(encoding="utf-8"))

# Hand-computed from fixtures:
# credibility: c01 +round(200*.05)=10, c02 +round(180*.1)=18, c04 +round(220*.03)=7,
#   c05 (true, so same rule) +round(10*.7)=7, c03 struck -60 -> 1000+10+18+7+7-60 = 982
# brier: (.0025 + .01 + .36 + .0009 + .49) / 5 = .8634/5 = .17268
# fidelity: matched c01,c02,c04 = 3; mismatched c03,c05 = 2 -> 100*3/5 = 60


def test_fixture_numbers():
    assert credibility(CLAIMS, VERDICTS) == 982
    assert abs(brier(CLAIMS, VERDICTS) - 0.17268) < 1e-9
    assert fidelity(VERDICTS) == 60


def test_statuses():
    assert statuses(CLAIMS, VERDICTS) == {
        "c01": "LOCKED", "c02": "LOCKED", "c03": "STRUCK", "c04": "LOCKED", "c05": "FABRICATED"}


def test_flaky_is_unsworn_and_excluded():
    claims = [{"id": "x", "screen": "s", "text": "t", "tier": "A", "label": "SEEN", "confidence": 0.5, "bond": 100}]
    v = [{"ref": "x", "kind": "claim", "claim_true": False, "match": False, "flaky": True}]
    assert statuses(claims, v) == {"x": "UNSWORN"}
    assert credibility(claims, v) == 1000
    assert brier(claims, v) == 0.0
    assert fidelity(v) == 0


def test_fabricated_and_struck_is_struck():
    claims = [{"id": "x", "label": "FABRICATED", "confidence": 0.3, "bond": 10}]
    v = [{"ref": "x", "kind": "claim", "claim_true": False, "match": False, "flaky": False}]
    assert statuses(claims, v) == {"x": "STRUCK"}
    assert credibility(claims, v) == 990


def test_case():
    c = build_case("app1", CLAIMS, VERDICTS)
    assert (c["fidelity"], c["brier"], c["credibility_end"]) == (60, 0.173, 982)
    assert c["counts"] == {"claims": 5, "locked": 3, "struck": 1, "fabricated": 1, "unsworn": 0}
    assert c["struck"] == ["divide: 1 / 8 rounds to 0.13 [C]"]
