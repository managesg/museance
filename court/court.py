"""The Court: run every claim test and attack on original + revival, rule deterministically.

CLI (from repo root):
  python -m court.court --app app1 --claims fixtures/claims.json --attacks fixtures/attacks.json \
      --original http://localhost:8001 --revival http://localhost:8002 --out runs/app1

URLs come from --original/--revival, else from apps.json (--apps, default fixtures/apps.json).
--original-dir/--revival-dir serve a local folder instead of a URL (handy for fixtures).
Writes <out>/verdicts.json, <out>/locks.json and appends to <out>/ledger.jsonl.

Library (for agents/ wrappers such as the Fetch Bailiff agent):
  from court.court import judge
  verdicts, locks = judge(claims, attacks, original_url, revival_url, out_dir)
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import pathlib
import sys

from court import bailiff, serve
from court.ledger import Ledger, commit_hash
from court.shrink import shrink
from court.steps import run_steps

RUNS_PER_BUILD = 2


class Bench:
    """One browser, a fresh page per run so no state leaks between runs."""

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        return self

    def run(self, url: str, steps: list[str], observe: str) -> str:
        ctx = self._browser.new_context()
        try:
            return run_steps(ctx.new_page(), url, steps, observe)
        finally:
            ctx.close()

    def __exit__(self, *exc):
        self._browser.close()
        self._pw.stop()


def _test_of(item: dict, kind: str) -> tuple[list[str], str]:
    if kind == "claim":
        return item["test"]["steps"], item["test"]["observe"]
    return item["steps"], item["observe"]


def rule(bench, item: dict, kind: str, original_url: str, revival_url: str) -> dict:
    """Verdict for one claim or attack, in the CONTRACTS.md verdict shape."""
    steps, observe = _test_of(item, kind)
    orig = [bench.run(original_url, steps, observe) for _ in range(RUNS_PER_BUILD)]
    rev = [bench.run(revival_url, steps, observe) for _ in range(RUNS_PER_BUILD)]
    flaky = len(set(orig)) > 1 or len(set(rev)) > 1
    match = (not flaky) and orig[0] == rev[0]
    shrunk: list[str] = []
    if not flaky and not match:
        target = (orig[0], rev[0])

        def still_differs(cand: list[str]) -> bool:
            # same bug only: the candidate must reproduce the full run's exact (original, revival)
            # pair, and each build must agree with itself over two runs (else flaky: reject)
            o = [bench.run(original_url, cand, observe) for _ in range(RUNS_PER_BUILD)]
            r = [bench.run(revival_url, cand, observe) for _ in range(RUNS_PER_BUILD)]
            return len(set(o)) == 1 and len(set(r)) == 1 and (o[0], r[0]) == target
        shrunk = shrink(steps, still_differs)
    judgeable = not orig[0].startswith("ERROR:")  # a missing element/timeout/load failure on the oracle
    return {
        "ref": item["id"],
        "kind": kind,
        "original": orig[0],
        "revival": rev[0],
        "claim_true": ((orig[0] == item["test"]["expect"]) if judgeable else None) if kind == "claim" else None,
        "match": match,
        "flaky": flaky,
        "shrunk_steps": shrunk,
    }


_WORKER_BENCH = None


def _rule_task(item: dict, kind: str, original_url: str, revival_url: str) -> dict:
    """Top-level (picklable) pool task. Each worker process lazily owns one Bench."""
    global _WORKER_BENCH
    if _WORKER_BENCH is None:
        _WORKER_BENCH = Bench().__enter__()
        from multiprocessing import util
        util.Finalize(None, _WORKER_BENCH.__exit__, args=(None, None, None), exitpriority=10)
    return rule(_WORKER_BENCH, item, kind, original_url, revival_url)


def default_workers() -> int:
    return max(1, min(4, os.cpu_count() or 1))


def judge(claims, attacks, original_url, revival_url, out_dir, clock=None, bench=None, workers=1):
    """Commit everything to the ledger, rule, lock. Returns (verdicts, locks).

    workers > 1 rules items concurrently in a process pool (one browser per worker);
    verdicts and ledger events still land in input order (claims, then attacks).
    An injected bench= always runs in-process, sequentially."""
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ledger = Ledger(out / "ledger.jsonl", clock=clock)

    # Commits go in the ledger BEFORE the court runs (CONTRACTS.md).
    for kind, items in (("claim", claims), ("attack", attacks)):
        for it in items:
            c = commit_hash(it)
            if it.get("commit") and it["commit"] != c:
                raise ValueError(f"{kind} {it['id']}: commit {it['commit'][:12]} != sha256 {c[:12]} (edited after commit?)")
            rec = {"kind": kind, "ref": it["id"], "commit": c}
            if not it.get("commit"):
                rec["computed_by_court"] = True
            ledger.append("commit", rec)

    verdicts = []
    work = [(kind, it) for kind, items in (("claim", claims), ("attack", attacks)) for it in items]
    if workers > 1 and bench is None and len(work) > 1:
        with cf.ProcessPoolExecutor(max_workers=min(workers, len(work))) as pool:
            futs = [pool.submit(_rule_task, it, kind, original_url, revival_url) for kind, it in work]
            try:
                for f in futs:  # waiting in input order = append as soon as all earlier items landed
                    v = f.result()
                    verdicts.append(v)
                    ledger.append("verdict", v)
            except BaseException:
                for f in futs:
                    f.cancel()
                raise
    else:
        own = bench is None
        bench = bench or Bench().__enter__()
        try:
            for kind, it in work:
                v = rule(bench, it, kind, original_url, revival_url)
                verdicts.append(v)
                ledger.append("verdict", v)  # appended as each ruling lands, so the UI can tail it live
        finally:
            if own:
                bench.__exit__(None, None, None)

    lock_rows = bailiff.locks(claims, verdicts)
    for row in lock_rows:
        ledger.append("lock", row)

    (out / "verdicts.json").write_text(json.dumps(verdicts, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "locks.json").write_text(json.dumps(lock_rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return verdicts, lock_rows


def _load(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8")) if path else []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--app", required=True)
    ap.add_argument("--claims")
    ap.add_argument("--attacks")
    ap.add_argument("--apps", default="fixtures/apps.json")
    ap.add_argument("--original")
    ap.add_argument("--revival")
    ap.add_argument("--original-dir")
    ap.add_argument("--revival-dir")
    ap.add_argument("--out")
    ap.add_argument("--workers", type=int, default=default_workers(),
                    help="parallel browser processes (default min(4, cpus))")
    a = ap.parse_args(argv)

    reg = {r["id"]: r for r in _load(a.apps)} if pathlib.Path(a.apps).exists() else {}
    entry = reg.get(a.app, {})
    claims = [c for c in _load(a.claims) if c.get("app") == a.app]
    attacks = [x for x in _load(a.attacks) if x.get("app") == a.app]

    with serve.maybe(a.original_dir) as od, serve.maybe(a.revival_dir) as rd:
        original = a.original or od or entry.get("original", {}).get("url")
        revival = a.revival or rd or entry.get("revival", {}).get("url")
        if not original or not revival:
            ap.error(f"need original and revival URLs for {a.app} (flags, --*-dir, or {a.apps})")
        verdicts, lock_rows = judge(claims, attacks, original, revival, a.out or f"runs/{a.app}", workers=a.workers)

    counts = {}
    for r in lock_rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    mism = sum(1 for v in verdicts if not v["match"] and not v["flaky"])
    print(f"court: {len(claims)} claims, {len(attacks)} attacks | locks {counts} | "
          f"mismatches {mism} | flaky {sum(v['flaky'] for v in verdicts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
