import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from before_after import build_app, render  # noqa: E402

ROW = lambda k, p: {"id": k, "kind": k[0] == "g" and "good" or "trap", "passed": p}  # noqa: E731
HEAD = [ROW("g1", True), ROW("g2", True), ROW("t1", True)]
OLD = [ROW("g1", True), ROW("g2", True), ROW("t1", False)]
REP = [{"claim_id": "c1", "decision": "patched", "from_sha256": "a", "to_sha256": "b", "reason": "regression score 2 -> 3"},
       {"claim_id": "c2", "decision": "patched", "from_sha256": "b", "to_sha256": "c", "reason": "x", "regression": [3, 3]}]


def test_versions_chain_and_missing_stay_null():
    rows = build_app("x", REP, OLD, HEAD, 60, 60, ["codex", None])
    assert [r["version"] for r in rows] == ["v1", "v2", "v3"] and [r["sha256"] for r in rows] == ["a", "b", "c"]
    v1, v2, v3 = rows
    assert (v1["regression_passed"], v1["traps_flagged"], v1["traps_of"], v1["fidelity"]) == (2, 1, 1, 60)
    assert (v2["regression_passed"], v2["traps_flagged"], v2["traps_of"], v2["fidelity"]) == (3, None, None, None)
    assert "traps_flagged" in v2["not_recorded"] and v2["repair_builder"] is None and v1["repair_builder"] == "codex"
    assert (v3["regression_passed"], v3["traps_flagged"], v3["repair_to"]) == (3, 0, None)
    assert "not recorded" in render(rows) and json.dumps(rows)


def test_builder_source_carried():
    rows = build_app("x", REP, OLD, HEAD, 60, 60, [("muse", "repairs.jsonl"), None])
    assert (rows[0]["repair_builder"], rows[0]["repair_builder_source"]) == ("muse", "repairs.jsonl")
    assert (rows[1]["repair_builder"], rows[1]["repair_builder_source"]) == (None, None)


def test_stored_regression_file_ignored_when_it_disagrees_with_recorded_score():
    rows = build_app("x", REP, HEAD, HEAD, None, None, [None, None])  # HEAD passes 3 but v1 recorded 2
    assert rows[0]["regression_passed"] == 2 and rows[0]["traps_flagged"] is None
