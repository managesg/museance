# aie-code

**SÉANCE**: a fidelity court for resurrected software. Built at the AIE Code Summit Hackathon, 2026-11-07.

The dead app gets a lawyer, not a fan.

## What it is

SÉANCE is a fidelity court for resurrected software: a dead app is revived from its observed behavior, then tried in an automated court.
A Skeptic attacks the revival without seeing the claims, the court rules deterministically (no model in the verdict), and `eval/` scores every ruling.
The stage UI in `court/ui/` plays the trial; the demo app is the archived `themaxsandelin/todo`.

## Quick start

```sh
make check                          # validate fixtures against contracts (same as: python eval/check_fixtures.py)
python eval/p4_fixture.py           # skeptic, revival check, score, case file
python -m pytest -q eval revive dig # lane tests
python -m court.court --app app1 --claims fixtures/claims.json --attacks fixtures/attacks.json     --original http://localhost:8001 --revival http://localhost:8002 --out runs/app1   # the court (needs Playwright)
```

Serve the apps first: `make serve-fixture` (port 8001), `python -m http.server 8011 -d apps/todo/original`. Stage UI: see `court/ui/RUNBOOK.md`.

## Repo map

| Folder | Lane | What |
| --- | --- | --- |
| `court/` | P1 | Court engine: serves apps, runs claims and attacks on original + revival, shrinker, Bailiff, ledger |
| `apps/` | P1 | Vendored dead apps (oracles) |
| `dig/` | P2 | Evidence piles, reader, behavior sheets |
| `agents/` | P2 | LLM client and the Medium |
| `court/ui/` | P3 | React stage UI, cast, live feed |
| `revive/` | P4 | Builds and repairs the revival from a behavior sheet |
| `eval/` | P4 | Skeptic, seal, scoring, regression |
| `cases/` | P4 | Case files, commits, metrics |
| `contracts/`, `fixtures/` | shared | JSON schemas and fixture data (`CONTRACTS.md`) |

## Built today

All code in this repo was written on 2026-11-07 at the AIE Code Summit Hackathon. Third-party apps, libraries and assets are listed in `CREDITS.md`.

Start with `AGENTS.md` (lanes, rules, reporting) and `CONTRACTS.md` (data between lanes). `make check` validates the fixtures; `make serve-fixture` serves the fixture app on port 8001.

## P4: Revival, Skeptic, Scoring

Lane P4 (`revive/`, `eval/`, `cases/`) builds the revival from a behavior sheet, attacks it with a
Skeptic that never sees the claims, and scores the court's verdicts. Plan: `revive/P4_WORKPLAN.md`.

**One-command fixture run** (skeptic attacks, revival check, score, case file, one summary block):

```sh
python eval/p4_fixture.py
```

**Seal and verify.** The regression set and the Skeptic's attacks are hashed and committed before the
Medium's claims are revealed (`cases/<app>.commits.json`):

```sh
python eval/seal.py --app app1 --regression eval/regression/app1-fixture.json \
  --attacks runs/app1/attacks.json --out cases/app1.commits.json          # seal
python eval/seal.py --app app1 --regression eval/regression/app1-fixture.json \
  --attacks runs/app1/attacks.json --out cases/app1.commits.json --verify  # verify
```

`--verify` checks content only (the files still hash to the seal). The "before reveal" part is the git history:
`cases/todo.commits.json` was committed in 5a51fc4 (20:44 UTC), P2's todo claims in 63dc375 and 9bdd377 (21:00 and
21:16 UTC), and the seal file has not changed since. Verify the todo seal with
`python eval/seal.py --app todo --regression eval/regression/todo.json --attacks cases/todo/attacks.json --out cases/todo.commits.json --verify`.

**Builders** (`revive/build.py --builder ...`): `codex`, `claude`, `glm`, and `muse`. Muse runs with no tools and
cannot write files; it produced an independent repair of todo v1 (`cases/todo/repairs.jsonl`, `revive/out/todo/index.muse.html`).
Details: `revive/README.md`.

**Scoring.** Credibility, Brier and fidelity are pure functions in `eval/score.py`, defined in the
"Scoring (P4)" section of `CONTRACTS.md`. There is no model in the court or in the scoring.
Todo fidelity, all 121 verdicts (P2's 16 claims + 105 sealed attacks), MEASURED: 41 for revival v1 (`cases/todo/v1-16claims/verdicts.json`), 100 for v2 (`cases/todo/v2-16claims/verdicts.json`); `cases/BEFORE_AFTER.md`.

```sh
python -m pytest -q eval revive dig      # lane tests
python eval/metrics_report.py            # rewrite cases/METRICS.md from case files
```

Numbers: see `cases/METRICS.md` (measured only).
