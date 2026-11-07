import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from case_file import build_case, to_yaml  # noqa: E402
from metrics_report import report  # noqa: E402

CLAIMS = [{"id": "c1", "screen": "s", "text": "t", "tier": "A", "bond": 100, "confidence": 0.8, "label": "SEEN"},
          {"id": "c2", "screen": "s", "text": "u", "tier": "A", "bond": 50, "confidence": 0.5, "label": "SEEN"}]
VERDICTS = [{"ref": "c1", "kind": "claim", "claim_true": True, "match": True, "flaky": False}]


def test_null_fields_are_not_measured_and_nothing_invented(tmp_path):
    cases, runs = tmp_path / "cases", tmp_path / "runs"
    cases.mkdir()
    (cases / "x.case.yml").write_text(to_yaml(build_case("x", CLAIMS, VERDICTS)), encoding="utf-8")
    md = report(cases, runs)
    assert "| Regression | not measured yet |" in md and "| False strikes | not measured yet |" in md
    assert "| Brier | 0.04 (n=1) |" in md and "| Credibility | 1000 -> 1020 |" in md and "| Fidelity | 100 |" in md
    assert "| Repairs | not measured yet |" in md
    assert "Not measured yet: Regression, False strikes, Traps caught, Repairs." in md


def test_regression_and_repairs_counts(tmp_path):
    cases, runs = tmp_path / "cases", tmp_path / "runs"
    (runs / "x").mkdir(parents=True), cases.mkdir()
    reg = [{"id": "g1", "kind": "good", "passed": True}, {"id": "g2", "kind": "good", "passed": False},
           {"id": "t1", "kind": "trap", "passed": False}]
    (cases / "x.case.yml").write_text(to_yaml(build_case("x", CLAIMS, VERDICTS, reg)), encoding="utf-8")
    (runs / "x" / "regression-result.json").write_text(json.dumps(reg), encoding="utf-8")
    (runs / "x" / "repairs.jsonl").write_text("\n".join(json.dumps({"decision": d}) for d in ("patched", "rollback", "patched")), encoding="utf-8")
    md = report(cases, runs)
    assert "| Regression | 1/3 |" in md and "| False strikes | 1/2 |" in md and "| Traps caught | 1/1 |" in md
    assert "| Repairs | patched 2, rollback 1, unsworn 0 |" in md
    assert "Not measured yet: none." in md
