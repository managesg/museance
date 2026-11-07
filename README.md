# aie-code

**SÉANCE**: a fidelity court for resurrected software. Built at the AIE Code Summit Hackathon, 2026-11-07.

The dead app gets a lawyer, not a fan.

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

**Builders** (`revive/build.py --builder ...`): `codex`, `claude`, `glm`, and `muse`. Muse is used once,
for the on-stage repair (`revive/repair.py`); it has no tools and cannot write files. Details: `revive/README.md`.

**Scoring.** Credibility, Brier and fidelity are pure functions in `eval/score.py`, defined in the
"Scoring (P4)" section of `CONTRACTS.md`. There is no model in the court or in the scoring.

```sh
python -m pytest -q eval revive dig      # lane tests
python eval/metrics_report.py            # rewrite cases/METRICS.md from case files
```

Numbers: see `cases/METRICS.md` (measured only).
