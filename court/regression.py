"""Regression check: run P4's regression set (good + traps) through the court.

CLI (from repo root):
  python -m court.regression <regression.json> --original-dir fixtures/app1 --revival-dir <dir> [--out report.json]
  (--original/--revival take URLs instead of folders)

Regression file (P4, eval/regression/<app>-fixture.json on p4-skeptic):
  {"app", "fixture", "good": [entry], "traps": [entry]}
  entry = {id, app, screen, text, steps, observe, expect}   (flat; a claim keeps these under `test`)
Every `expect` (good AND traps) is what the ORIGINAL shows; P4 verified this with eval/run_fixture.js.
- good : ordinary behaviours. Must never be struck, and must match on a faithful revival.
- traps: quirks of the original (truncation, /0 -> Error, ...) a naive revival gets wrong.
         Caught = the court rules a non-flaky mismatch between original and revival.

Each entry is ruled by court.court.rule() as a claim (two runs per build, flaky check, shrinker)
and given a status by court.bailiff. Reported:
- false strikes : good entries ruled STRUCK or non-flaky mismatch
- struck        : any entry whose expect the court does not see on the original (P4 says it does)
- caught/missed : traps with / without a non-flaky mismatch
- flaky         : entries whose two runs on one build disagreed (UNSWORN, never STRUCK)
Exit code 1 when there is any false strike or struck entry, else 0.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

from court import bailiff, serve
from court.court import Bench, rule


def _as_claim(entry: dict, group: str) -> dict:
    """Regression entry -> claim shape rule() expects. Accepts flat or `test`-nested entries."""
    test = entry.get("test") or {k: entry[k] for k in ("steps", "observe", "expect")}
    return {"id": entry["id"], "app": entry.get("app"), "screen": entry.get("screen"),
            "text": entry.get("text", ""), "test": test, "label": "SEEN", "group": group}


def load(path) -> list[dict]:
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):  # plain list = all good (same convention as eval/run_fixture.js)
        return [_as_claim(e, "good") for e in data]
    return [_as_claim(e, "good") for e in data.get("good", [])] + \
           [_as_claim(e, "trap") for e in data.get("traps", [])]


def check(entries: list[dict], original_url: str, revival_url: str, bench=None) -> dict:
    """Rule every entry; return the report dict (rows + counts)."""
    own = bench is None
    bench = bench or Bench().__enter__()
    rows, t0 = [], time.monotonic()
    try:
        for e in entries:
            v = rule(bench, e, "claim", original_url, revival_url)
            status, why = bailiff.status(e, v)
            mismatch = not v["match"] and not v["flaky"]
            rows.append({"id": e["id"], "group": e["group"], "expect": e["test"]["expect"],
                         "status": status, "reason": why, "mismatch": mismatch, **v})
    finally:
        if own:
            bench.__exit__(None, None, None)
    good = [r for r in rows if r["group"] == "good"]
    traps = [r for r in rows if r["group"] == "trap"]
    counts = {
        "good": len(good),
        "traps": len(traps),
        "false_strikes": sum(1 for r in good if r["status"] == "STRUCK" or r["mismatch"]),
        "struck": sum(1 for r in rows if r["status"] == "STRUCK"),
        "mismatches": sum(1 for r in rows if r["mismatch"]),
        "traps_caught": sum(1 for r in traps if r["mismatch"]),
        "traps_missed": sum(1 for r in traps if not r["mismatch"]),
        "flaky": sum(1 for r in rows if r["flaky"]),
        "seconds": round(time.monotonic() - t0, 1),
    }
    return {"counts": counts, "rows": rows}


def _print(report: dict, original: str, revival: str) -> None:
    print(f"original {original}\nrevival  {revival}")
    for r in report["rows"]:
        flag = "FLAKY" if r["flaky"] else ("MISMATCH" if r["mismatch"] else "match")
        extra = f" shrunk={r['shrunk_steps']}" if r["shrunk_steps"] else ""
        print(f"  {r['id']:<5} {r['group']:<4} {r['status']:<8} {flag:<8} "
              f"expect={r['expect']!r} orig={r['original']!r} rev={r['revival']!r}{extra}")
    c = report["counts"]
    print(f"regression: {c['good']} good, {c['traps']} traps | false strikes {c['false_strikes']} | "
          f"struck {c['struck']} | traps caught {c['traps_caught']}/{c['traps']} (missed {c['traps_missed']}) | "
          f"mismatches {c['mismatches']} | flaky {c['flaky']} | {c['seconds']} s")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("regression", help="P4 regression JSON ({good, traps}) or a plain list")
    ap.add_argument("--original")
    ap.add_argument("--revival")
    ap.add_argument("--original-dir")
    ap.add_argument("--revival-dir")
    ap.add_argument("--out", help="write the full report (rows + counts) as JSON here")
    a = ap.parse_args(argv)
    if not (a.original or a.original_dir) or not (a.revival or a.revival_dir):
        ap.error("need --original or --original-dir, and --revival or --revival-dir")

    entries = load(a.regression)
    with serve.maybe(a.original_dir) as od, serve.maybe(a.revival_dir) as rd:
        original, revival = a.original or od, a.revival or rd
        report = check(entries, original, revival)
    _print(report, a.original or a.original_dir, a.revival or a.revival_dir)
    if a.out:
        out = pathlib.Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    c = report["counts"]
    return 1 if c["false_strikes"] or c["struck"] else 0


if __name__ == "__main__":
    sys.exit(main())
