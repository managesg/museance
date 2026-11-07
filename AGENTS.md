# SÉANCE — rules for every human and every coding agent

Read this file and `CONTRACTS.md` before writing code. Everything here was written on 2026-11-07 during the AIE Code Summit Hackathon.

## What we are building
A fidelity court for resurrected software. Agents dig up evidence of a dead app, a medium rebuilds it and makes claims with confidence and a bond, a skeptic attacks, and a deterministic court rules. Only claims that survive are locked. See `CONTRACTS.md` for the data that flows between lanes.

## Lanes and folders (edit only your own folder)
| Lane | Owner | Folders | Delivers |
|---|---|---|---|
| P1 Court engine | Lokesh | `apps/`, `court/` (not `court/ui/`) | serve the original app; run claim tests and attacks on original + revival (Playwright); flaky check (run twice); shrinker; Bailiff lock table; ledger |
| P2 Dig & Medium | Roshni | `dig/`, `agents/` | evidence pile with tiers A-D; SubQ reader -> behavior sheet; Medium (ASI-1 / Fetch uAgent) -> claim cards |
| P3 Court UI & cast | Vi | `court/ui/` | stage, cast, claim cards, meters, glitches, bench console, live feed |
| P4 Revival, Skeptic, Scoring | Alejandro | `revive/`, `eval/`, `cases/` | Muse revival + repair; Gemini attacks (hashed first); Brier + credibility; regression set; case file |

Shared, change only with a `[CONTRACT]` post in WhatsApp and a 👍 from affected lanes: `contracts/`, `fixtures/`, `CONTRACTS.md`, `AGENTS.md`, `Makefile`.

## Working rules
- Branch per lane: `p1-<topic>`, `p2-<topic>`, ... Open a PR to `main` when `make check` and your lane test pass. Small PRs, often.
- Build against `fixtures/` until the real data from the other lane exists. Never block on another lane.
- Secrets: only in your local `.env` (see `.env.example`). Never in the repo, never in WhatsApp group messages.
- Model-written code that runs untrusted input goes in a container or sandbox, no network.
- No model in the Court or the Bailiff. Verdicts are deterministic.
- Only report numbers we measured today. No invented metrics in README, UI or pitch.
- Third-party apps, libraries and art: credit them with their license in `CREDITS.md`.

## Reporting (WhatsApp group "AIE Hack")
Every 30 minutes and at each checkpoint, post one line:

```
[P2] 12:30 ✅ evidence pile app1 (41 items) | ⏭ reader pass | ⛔ none
```

Tags: `⛔ BLOCKED`, `NEED <what> from <lane>`, `[CONTRACT]` (schema change request), `[MERGED]`.
Coding agents: draft this line for your human at the end of each task.

## Checkpoints (PT)
- 12:30 every lane runs on fixtures
- 13:30 app1 runs end to end in the terminal
- 14:45 full run through the UI, 0 false strikes on the regression set
- 15:30 freeze, then video; submit by 16:45 (due 17:00)
