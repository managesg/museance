# Data contracts

All lanes exchange JSON objects with these shapes. Schemas live in `contracts/`, examples in `fixtures/`. Until MongoDB Atlas is wired, lanes pass these as JSON files under `runs/<app>/` (gitignored). Atlas collections use the same names.

## Steps (how a test or attack drives an app)
A list of strings, run in order in a browser on the app page:
- `click:<css selector>` e.g. `click:#k7`
- `type:<css selector>:<text>` e.g. `type:#name:Ada`
- `key:<key name>` e.g. `key:Enter`
- `wait:<ms>`

`observe` is a CSS selector; the court reads its `innerText` after the steps.

## Objects
| Object | Writer | File | Fields |
|---|---|---|---|
| evidence | P2 | `evidence.json` | id, app, tier (A/B/C/D), kind (page, screenshot, video, issue, doc), source, text or path, license |
| behavior_sheet | P2 | `sheet.json` | app, lines[]: {id, screen, text, label SEEN/GUESSED, citations[], conflicts[]} |
| claim | P2 (Medium) | `claims.json` | id, app, screen, text, test {steps, observe, expect}, tier, label SEEN/GUESSED/FABRICATED, evidence[], confidence (0-1), bond (int), commit |
| attack | P4 (Skeptic) | `attacks.json` | id, app, screen, steps, observe, commit. The skeptic never sees claim text. |
| verdict | P1 (Court) | `verdicts.json` | ref (claim or attack id), kind (claim/attack), original, revival, claim_true (claims only), match, flaky, shrunk_steps |
| lock | P1 (Bailiff) | `locks.json` | claim_id, status LOCKED/STRUCK/UNSWORN/FABRICATED, reason |
| ledger event | P1 | `ledger.jsonl` | seq, ts, type, payload, prev_hash, hash (sha256 of prev_hash + payload) |
| case | P4 | `cases/<app>.case.yml` | app, fidelity, brier, credibility_start/end, locked[], struck[], fabricated[], unsworn[], counts |

## Rules the court applies
- `claim_true` = the claim's test on the ORIGINAL returns `expect`. Feeds credibility and Brier.
- `match` = original and revival give the same observed text. Feeds fidelity.
- Each test runs twice per build; different results = `flaky: true` = UNSWORN, never STRUCK.
- `commit` = sha256 of the object (without `commit`) written to the ledger before the court runs.

## Scoring (P4)
- Credibility starts at 1000. STRUCK: lose `bond`. LOCKED: gain `round(bond * (1 - confidence))`.
- Brier = mean over claims of (confidence - claim_true)^2.
- Fidelity = 100 * matched / (matched + mismatched), flaky excluded.
