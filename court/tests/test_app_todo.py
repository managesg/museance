"""The vendored todo original, run as BOTH builds, must lock every claim (no mismatch, no flake)."""
import json
import pathlib

from court import serve
from court.court import judge

ROOT = pathlib.Path(__file__).resolve().parents[2]
ORIG = ROOT / "apps" / "todo" / "original"
CLAIMS = pathlib.Path(__file__).parent / "data" / "claims.todo.json"


def test_todo_original_locks_all_claims(tmp_path):
    claims = json.loads(CLAIMS.read_text(encoding="utf-8"))
    assert 5 <= len(claims) <= 8
    with serve.folder(ORIG) as url:
        verdicts, locks = judge(claims, [], url, url, tmp_path)
    for v in verdicts:
        assert v["claim_true"] is True, v
        assert v["match"] is True, v
        assert v["flaky"] is False, v
    assert {r["status"] for r in locks} == {"LOCKED"}
    assert len(locks) == len(claims)
