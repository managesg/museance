# P4 workplan: Revival, Skeptic, Scoring (owner: Alejandro)

Lane P4 of SÉANCE. Folders: `revive/`, `eval/`, `cases/` only. Rules: `AGENTS.md`, data shapes: `CONTRACTS.md`.
Times are PT, Sat 2026-11-07. Submissions due 17:00; we submit 16:45.

## Agents and models (P4 only)
| Agent | Used for | Notes |
|---|---|---|
| Claude (orchestrator session, Alejandro's subscription) | plans, reviews, merges P4 branches, WhatsApp liaison | local PC |
| Claude subagents (local, background) | small, well-specified P4 tasks and independent review | one task each, report back |
| Codex (box, `hack:p4-codex` window; local CLI too) | main implementation; Skeptic attacks | different vendor from the reviser = independent |
| GLM (Z.AI coding plan, box `glm`) | bulk: attack variants, test data, second builder | on demand |
| Kimi (box) | long reads and a second review of revival vs sheet | on demand |
| Cursor (box, read-only) | review comments only | cannot write |
| Muse (Meta) | ONE visible repair on stage for the Meta prize | limited use |
| Docker (box) | runs model-written revival code, no network | |
No Gemini. Author and reviewer must be different vendors.

## Done
| ID | What | Where | Evidence |
|---|---|---|---|
| D1 | Scoring: credibility, Brier, fidelity, statuses; case file builder | `eval/score.py`, `eval/case_file.py` | main 95153ea, tests green |
| D2 | Skeptic v0 (deterministic attacks, hashed), Codex skeptic, `commit_hash` | `eval/skeptic.py`, `eval/skeptic_codex.py`, `eval/commit.py` | main, 75 attacks on fixture |
| D3 | Regression set fixture: 12 good + 8 traps, verified by running the fixture JS | `eval/regression/app1-fixture.json` | main |

## Task queue (do in order; each has a done-check)
| ID | By | Task | Agent | Done when |
|---|---|---|---|---|
| L1 | now | Liaison: send Roshni the answers (Atlas: Alejandro DMs the connection string, JSON files under `runs/<app>/` meanwhile; claim `commit` via `eval/commit.py`; use main's `contracts/claim.schema.json`; app1 locked by P1+P2 by 12:20) | liaison via WhatsApp Web in Orca's browser | message delivered in AIE Hack |
| T1 | 12:30 | Revival builder: `revive/build.py`, `check_revival.py`, `run_revival.js`, tests, testdata sheet; first real build of the fixture app | Codex (box), review by Claude subagent | tests green; score x/20 recorded; branch `p4-revival` pushed and merged to main |
| T2 | 12:30 | P4 fixture pipeline: one command `python eval/p4_fixture.py` = skeptic attacks -> revival check -> score -> case file | Claude subagent | prints numbers from fixtures; checkpoint status posted |
| T3 | 13:00 | Seal: `eval/seal.py` writes `cases/<app>.commits.json` (sha256 of regression set + attacks) before the Medium's claims are revealed; commit it | Claude subagent | hashes committed to git with a timestamp before claims exist |
| T4 | 13:15 | Repair loop: `revive/repair.py` takes a struck claim + `shrunk_steps` + revival HTML; builder either fixes the revival narrowly or moves the claim to UNSWORN; logs a rollback event (ledger shape) | Codex, review Kimi or Claude | one struck fixture claim repaired; rollback event written; regression still >= before |
| T5 | when app1 is locked by P1/P2 | Real app1: regression set (12 good + 8 traps) written from the RUNNING original by P4 (never by P2); selectors file; skeptic attacks; revival from P2's `sheet.json` | Codex + GLM for attack variants | files under `eval/regression/app1.json`, `runs/app1/` |
| T6 | 13:30 | End to end with P1 court: P2 claims -> P1 court on original + revival -> P4 score -> case file | coordinate with Lokesh | `cases/app1.case.yml` from real verdicts |
| T7 | 14:00 | Numbers feed for P3 UI: `runs/<app>/score.json` (credibility over time, Brier, fidelity, counts); agree format with Vi | Claude subagent | Vi confirms she reads it |
| T8 | 14:45 | Zero-false-strike check: run the 12 good behaviors with the original as its own "revival" through P1 court -> all LOCKED; traps caught x/8 | P4 + P1 | 0/12 false strikes, or court bug filed to P1 |
| T9 | 15:15 | Stage repair with Muse (Meta prize): one live repair via Muse; recorded fallback | Muse, limited | works twice in rehearsal |
| T10 | 15:30 | `METRICS.md` (only measured numbers, with counts), P4 section of README, CREDITS lines | Claude subagent | numbers match the case file |
| T11 | 15:30-16:45 | Freeze; support video and demo: repair beat + numbers bar | Alejandro + orchestrator | submitted |

## Loop (runs every 10 min while the session is open)
1. Check the active task: box window `hack:p4-codex`, `~/hack/out/*.log`, background subagents.
2. If done: verify (tests, done-check), copy results back from the box if needed, commit on a `p4-*` branch, push, merge to main only P4 folders with tests green.
3. Dispatch the next task to the right agent with a written brief (task file on the box or a subagent prompt).
4. Post a one-line P4 status via the WhatsApp liaison: `[P4] HH:MM ✅ … | ⏭ … | ⛔ …`.
5. If blocked on another lane (app1, sheet.json, court): post `NEED … from Px`, then continue with the next task that is not blocked.

## Never without Alejandro's OK
Merging other lanes' branches or PRs, changing `contracts/` or `CONTRACTS.md`, cutting scope, spending credits beyond the plan, keys (only he shares them, 1:1).

## Risks
| Risk | Fallback |
|---|---|
| app1 not locked by 12:45 | keep building on the fixture app; T5 starts when it lands |
| revival score low | that is fine: low fidelity is honest; the court and repair loop are the product |
| box push blocked (no deploy key) | copy results back to the PC and push from there |
| Muse quota | Codex repair on stage, Muse in the recorded video |
