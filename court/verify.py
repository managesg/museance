"""Verify one app's case: python -m court.verify --app snarkr --original <url|dir> --revival <url|dir>

Runs court.court.run_case on runs/<app>/ (claims.json, optional attacks.json), prints one line
per claim (id, text, LOCKED / STRUCK / UNSWORN / FABRICATED), then the summary.
Exit code: 1 if any claim is STRUCK, else 0. Flaky results are UNSWORN, never STRUCK.
--original/--revival take a URL, or a local folder that is served for the run.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import pathlib
import sys

from court import serve
from court.court import default_workers, run_case


@contextlib.contextmanager
def _url_or_dir(value: str):
    if pathlib.Path(value).is_dir():
        with serve.folder(value) as url:
            yield url
    else:
        yield value


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="court.verify", description=__doc__.split("\n\n")[0])
    ap.add_argument("--app", required=True)
    ap.add_argument("--original", required=True, help="URL or local folder of the original build")
    ap.add_argument("--revival", required=True, help="URL or local folder of the revival build")
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--workers", type=int, default=default_workers())
    a = ap.parse_args(argv)

    with _url_or_dir(a.original) as orig, _url_or_dir(a.revival) as rev:
        summary = run_case(a.app, orig, rev, runs=a.runs, workers=a.workers)

    case = pathlib.Path(a.runs) / a.app
    claims = {c["id"]: c for c in json.loads((case / "claims.json").read_text(encoding="utf-8"))}
    locks = json.loads((case / "locks.json").read_text(encoding="utf-8"))
    out = sys.stdout
    try:
        out.reconfigure(encoding="utf-8")  # claim text may be non-ASCII; Windows consoles default to cp1252
    except (AttributeError, ValueError):
        pass
    for r in locks:
        text = claims.get(r["claim_id"], {}).get("text", "")
        out.write(f"{r['claim_id']:<10} {r['status']:<10} {text}\n")
    c = summary["counts"]
    out.write(f"\n{a.app}: LOCKED {c['LOCKED']} | STRUCK {c['STRUCK']} | UNSWORN {c['UNSWORN']} | "
              f"FABRICATED {c['FABRICATED']} | ledger head {str(summary['ledger_head'])[:12]}\n")
    if summary["struck"]:
        out.write(f"STRUCK: {', '.join(summary['struck'])}\n")
    return 1 if summary["struck"] else 0


if __name__ == "__main__":
    sys.exit(main())
