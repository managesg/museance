"""Evidence photos: replay each mismatch's minimal repro on both builds and screenshot it.

Post-pass over <runs>/<app>/verdicts.json; does not touch court.py or the verdict schema.

CLI (from repo root):
  python -m court.shots --app app1 --runs runs --claims fixtures/claims.json \
      --attacks fixtures/attacks.json --original http://localhost:8001 --revival http://localhost:8002
--original-dir/--revival-dir serve a local folder instead of a URL. URLs otherwise come from apps.json.

Writes <runs>/<app>/shots/<ref>.{original,revival}.png, <ref>.{original,revival}.observe.png
(element shot of the `observe` selector, skipped when absent) and shots/index.json:
  [{ref, kind, original_text, revival_text, files: {original, revival, original_observe, revival_observe}}]
File paths in `files` are relative to shots/ (null where a shot was not possible).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from court import serve
from court.steps import run_steps

VIEWPORT = {"width": 800, "height": 600}


class Shooter:
    """One browser, a fresh 800x600 context per shot."""

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        return self

    def shoot(self, url: str, steps: list[str], observe: str, page_png: pathlib.Path,
              observe_png: pathlib.Path) -> tuple[str, bool]:
        """Replay steps, save the page shot, and the observe-element shot if it exists.
        Returns (replayed text, whether the observe shot was saved)."""
        ctx = self._browser.new_context(viewport=VIEWPORT)
        try:
            page = ctx.new_page()
            text = run_steps(page, url, steps, observe)
            page.screenshot(path=str(page_png))
            if observe_png.exists():
                observe_png.unlink()  # never leave a stale shot from a previous run
            got = False
            try:
                loc = page.locator(observe).first
                if loc.count():
                    loc.screenshot(path=str(observe_png), timeout=2000)
                    got = True
            except Exception:  # noqa: BLE001 - missing/hidden element: skip
                got = False
            return text, got
        finally:
            ctx.close()

    def __exit__(self, *exc):
        self._browser.close()
        self._pw.stop()


def _test_of(item: dict, kind: str) -> tuple[list[str], str]:
    if kind == "claim":
        return item["test"]["steps"], item["test"]["observe"]
    return item["steps"], item["observe"]


def take_shots(verdicts, claims, attacks, original_url, revival_url, out_dir, shooter=None) -> list[dict]:
    """Screenshot every non-flaky mismatch. Returns (and writes) the index."""
    shots = pathlib.Path(out_dir) / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    items = {("claim", c["id"]): c for c in claims}
    items.update({("attack", a["id"]): a for a in attacks})

    own = shooter is None
    shooter = shooter or Shooter().__enter__()
    index = []
    try:
        for v in verdicts:
            if v.get("match") or v.get("flaky"):
                continue
            item = items.get((v["kind"], v["ref"]))
            if item is None:
                print(f"shots: no {v['kind']} {v['ref']} in claims/attacks, skipped", file=sys.stderr)
                continue
            full, observe = _test_of(item, v["kind"])
            steps = v.get("shrunk_steps") or full
            files = {}
            replayed = {}
            for side, url in (("original", original_url), ("revival", revival_url)):
                page_png = shots / f"{v['ref']}.{side}.png"
                obs_png = shots / f"{v['ref']}.{side}.observe.png"
                replayed[side], got = shooter.shoot(url, steps, observe, page_png, obs_png)
                files[side] = page_png.name
                files[f"{side}_observe"] = obs_png.name if got else None
            index.append({
                "ref": v["ref"], "kind": v["kind"],
                "original_text": v["original"], "revival_text": v["revival"],
                "steps": steps, "observe": observe,
                "replayed_original": replayed["original"], "replayed_revival": replayed["revival"],
                "files": files,
            })
    finally:
        if own:
            shooter.__exit__(None, None, None)
    (shots / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return index


def _load(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8")) if path else []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--app", required=True)
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--claims")
    ap.add_argument("--attacks")
    ap.add_argument("--apps", default="fixtures/apps.json")
    ap.add_argument("--original")
    ap.add_argument("--revival")
    ap.add_argument("--original-dir")
    ap.add_argument("--revival-dir")
    a = ap.parse_args(argv)

    out = pathlib.Path(a.runs) / a.app
    vpath = out / "verdicts.json"
    if not vpath.exists():
        ap.error(f"{vpath} not found; run court.court first")
    reg = {r["id"]: r for r in _load(a.apps)} if pathlib.Path(a.apps).exists() else {}
    entry = reg.get(a.app, {})
    claims = [c for c in _load(a.claims) if c.get("app") == a.app]
    attacks = [x for x in _load(a.attacks) if x.get("app") == a.app]

    with serve.maybe(a.original_dir) as od, serve.maybe(a.revival_dir) as rd:
        original = a.original or od or entry.get("original", {}).get("url")
        revival = a.revival or rd or entry.get("revival", {}).get("url")
        if not original or not revival:
            ap.error(f"need original and revival URLs for {a.app} (flags, --*-dir, or {a.apps})")
        index = take_shots(_load(vpath), claims, attacks, original, revival, out)
    print(f"shots: {len(index)} mismatches photographed -> {out / 'shots'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
