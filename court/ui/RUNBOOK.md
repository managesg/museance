# Demo runbook

Run from the repo root. Give each long-running command its own terminal.

## Builds (static servers on 127.0.0.1)

```sh
# app1 original
python3 -m http.server 8001 -b 127.0.0.1 -d fixtures/app1
# app1 revival
python3 -m http.server 8002 -b 127.0.0.1 -d court/tests/revival_app1
# todo original
python3 -m http.server 8011 -b 127.0.0.1 -d apps/todo/original
# todo revival
python3 -m http.server 8012 -b 127.0.0.1 -d revive/out/todo
```

## Court, feed, stage

```sh
# P1 court feed on 8797: serves runs/<app>/ and judges POST /<app>/bench (no --original-dir/--revival-dir, so builds come from each request)
.venv/bin/python -u -B -m court.feed --runs runs --port 8797
# P3 feed on 8787: stage data from runs/, bench requests forwarded to the court feed
cd court/ui && COURT_URL=http://127.0.0.1:8797 node server/feed.ts
# Stage (Vite, default port 5173; proxies /api to 8787)
cd court/ui && npm run dev
# Open the todo case from runs/
open 'http://localhost:5173/?source=runs&app=todo'
```

## Regenerate runs/todo

```sh
# First, for a clean replay: the court appends to ledger.jsonl, so move the old one aside
mv runs/todo/ledger.jsonl "runs/todo/ledger.$(date +%H%M%S).jsonl"
# Re-judge todo: serves both builds itself, rewrites verdicts.json and locks.json, writes a new ledger.jsonl
.venv/bin/python -B -m court.court --app todo --claims runs/todo/claims.json --attacks runs/todo/attacks.json --original-dir apps/todo/original --revival-dir revive/out/todo --out runs/todo
```

## Notes

- If 8797 is taken, use another `--port` and the same port in `COURT_URL`.
- `.venv` is Python 3.13 with `pip install playwright` and no `playwright install`. Until P1 supports a browser-channel setting, `.venv/lib/python3.13/site-packages/pwshim.py` (loaded by `pwshim.pth`) adds `channel="chrome"` to court's bare `chromium.launch()`, so it runs the installed Google Chrome. A venv `sitecustomize.py` would not load, because Homebrew Python's own `sitecustomize.py` shadows it.
