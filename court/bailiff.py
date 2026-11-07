"""Bailiff: turns verdicts into the lock table. Deterministic, no model.

Same rules as P4's eval/score.py so the case file and locks.json never disagree:
- no verdict, or flaky verdict      -> UNSWORN  (never STRUCK)
- claim_true is None (the original errored: court could not judge) -> UNSWORN
- claim_true                        -> LOCKED
- otherwise                         -> STRUCK
- label FABRICATED and not STRUCK   -> FABRICATED
"""
from __future__ import annotations


def status(claim: dict, verdict: dict | None) -> tuple[str, str]:
    if verdict is None:
        s, why = "UNSWORN", "no verdict"
    elif verdict["flaky"]:
        s, why = "UNSWORN", "flaky: two runs on the same build disagreed"
    elif verdict.get("claim_true") is None:
        s, why = "UNSWORN", "court could not run the test on the original"
    elif verdict["claim_true"]:
        s, why = "LOCKED", f"original shows {verdict['original']!r} as claimed"
    else:
        s, why = "STRUCK", f"claimed {claim['test']['expect']!r}, original shows {verdict['original']!r}"
    if claim.get("label") == "FABRICATED" and s != "STRUCK":
        s, why = "FABRICATED", f"labelled FABRICATED by the Medium ({why})"
    return s, why


def locks(claims: list[dict], verdicts: list[dict]) -> list[dict]:
    by_ref = {v["ref"]: v for v in verdicts if v["kind"] == "claim"}
    out = []
    for c in claims:
        s, why = status(c, by_ref.get(c["id"]))
        out.append({"claim_id": c["id"], "status": s, "reason": why})
    return out
