# SÉANCE demo script

Written from the repo files on 2026-11-07. Not rehearsed by the author of this file: every item marked **VERIFY** is a thing to try once before going on stage. Numbers appear only if a file in this repo holds them (section 3 lists the file). Judging: Technical Demo 35, Implementation Difficulty 30, Impact 20, Creativity 15.

Cast (court/ui/src/cast, subtitles in court/ui/src/engine/lines.ts): the Departed (ghost, wears the dead app's icon as a hat), **McClusky** (penguin barrister, the Medium: swears claims with a confidence and a bond), **Dr. Hoot** (owl, the Skeptic: attacks without seeing the claims), **Faux** (cardboard standee of the app), **the Bailiff** (stamps the lock table; `court/bailiff.py`, no model).

## 0. Setup before the room fills

Commands are from `court/ui/RUNBOOK.md`. Run from the repo root, one terminal each.

```sh
python3 -m http.server 8011 -b 127.0.0.1 -d apps/todo/original     # original (MIT oracle, themaxsandelin/todo)
python3 -m http.server 8012 -b 127.0.0.1 -d revive/out/todo        # revival (index.html = v2; index.v1.html kept)
.venv/bin/python -u -B -m court.feed --runs runs --port 8797       # court: judges the bench live
cd court/ui && COURT_URL=http://127.0.0.1:8797 node server/feed.ts # stage feed on 8787
cd court/ui && npm run dev                                          # stage on 5173
```

- `runs/` is gitignored. On this checkout `runs/todo/` holds verdicts, locks, attacks and ledger but **not** `evidence.json`, `sheet.json`, `claims.json`, `case.json` (the stage feed reads all of them, `court/ui/server/feed.ts` `fromRuns`). Copy P2's outputs in: `cp dig/out/todo/{evidence,sheet,claims}.json runs/todo/`. The case file exists only as `cases/todo.case.yml`; if the numbers bar shows dashes, write a `runs/todo/case.json` from it. **VERIFY.**
- Tab 1: `http://localhost:5173/?source=runs&app=todo&view=stage` (the todo case; phase keys 1-8 only work with `&view=stage`; the plain URL shows the courtroom view without credibility/Brier). Tab 2: `http://localhost:5173/` (default fixture = calculator `app1`, used only for the judge's bench input, see beat 7). Tab 3: `cases/BEFORE_AFTER.md` open in a viewer, scrolled to the `## todo` table.
- Stage keys (`court/ui/src/stage/useKeyboard.ts`): Space play/pause, Left/Right step, **1-8** jump to a phase (dig, read, raise, swear, cross, repair, bench, sentence), **B** bench, **R** restart, **F** fullscreen, **+/-** speed.
- Known gap (read this): for `source=runs` the stage has **no repair replay** (`repairs: []` in `feed.ts`; the repair phase replays only for the fixture bundle). So beat 6 shows the repair from the committed files, not from an animation. Do not say the stage "ran" the repair.
- Fallback if the stage dies: terminal only: `python eval/p4_fixture.py` and `cat cases/BEFORE_AFTER.md`.

## 1. Three-minute run of show (rehearsed target: 2:50)

| # | Clock | On-screen action | Say (verbatim) | Behind it |
|---|---|---|---|---|
| 1 | 0:00-0:12 | Tab 1, press **F**. Ghost, McClusky, Dr. Hoot, Faux visible, docket along the top. | "A dead app gets a lawyer, not a fan. This is a todo list from 2016. We resurrected it from evidence, and now it stands trial." | `README.md` tagline; app `apps/todo/original` (MIT, `CREDITS.md`) |
| 2 | 0:12-0:27 | Press **1**, then **2**. Dig ticker fills, behavior sheet scrolls. | "Agents dug up 55 exhibits: pages, issues, our own screenshots of the original. A reader turned them into 24 behaviors, each labelled seen or guessed." | `dig/out/todo/evidence.json` (55), `sheet.json` (24 lines); `dig/collect.py`, `dig/reader.py` |
| 3 | 0:27-0:47 | Press **3**. Original exhibit left, revival boots right in the gilt frame. In the frame, type "Buy milk", click Add on both. | "The revival was built only from that sheet, never from the original's source. It boots, and it adds Buy milk. Looks alive. Looking alive is not evidence." | `revive/build.py` (builder sees sheet + selectors only); `revive/out/todo/index.html` |
| 4 | 0:47-1:05 | Press **4**. McClusky deals claim cards with confidence and bond. Subtitle: claims and credits. | "McClusky swears 16 claims. Each has a confidence and a bond he loses if he is wrong. Dr. Hoot has already attacked the revival with 105 tests, hashed before McClusky spoke. He never saw a claim." | `dig/out/todo/claims.json` (16); `cases/todo.commits.json` (sealed hashes); `eval/seal.py`, `agents/medium.py` |
| 5 | **1:05-1:35** | Press **5**. Cards flip LOCKED one by one. Stop on claim **c07** (Right arrow if needed): the PERJURY stamp lands, ghost glitches. | "Fifteen claims lock. Then McClusky swears an empty task can be created, because GitHub issue 38 says so. He bonds 198 credits at 89 percent. The court runs it on the original. No empty task. PERJURY. Minus 198. No model in that ruling; the Bailiff is plain code." | claim c07 `dig/out/todo/claims.json` (evidence e007 = issue #38, `evidence.json`); STRUCK in `cases/todo/locks.json`; `court/court.py` `rule()`, `court/bailiff.py`; `cases/todo.case.yml` |
| 6 | **1:35-2:10** | Switch to Tab 3 (BEFORE_AFTER todo table). Point at v1 row then v2 row. Optional: open `revive/out/todo/index.v1.html` and `index.v2.html` side by side. | "Now the repair. The first revival was wrong in 68 of Dr. Hoot's attacks and fidelity was 41. We hand the court's evidence to a builder, narrow patch only. Second revival: 68 mismatches become 0, fidelity 41 becomes 100, regression 19 of 20 becomes 20 of 20. And the court's false strikes on good behavior: zero of twelve." | `cases/BEFORE_AFTER.md`, `cases/before_after.json`, `cases/todo/v1-16claims/verdicts.json` (fidelity 41), `cases/todo/v2-16claims/verdicts.json` (fidelity 100), `cases/todo/repairs.jsonl`; `revive/repair.py` (cases mode); `cases/METRICS.md` |
| 7 | 2:10-2:35 | Tab 2 (calculator), press **B**. Invite a judge to type any key sequence into the bench field (placeholder `7/0=`), press Enter. Two runs per build; verdict and smallest diverging input shown. | "Judge, you are the last cross-examiner. Type anything. The court runs it twice on the original and twice on the revival and tells you if they agree." | `court/ui/src/bench/BenchConsole.tsx`; `POST /<app>/bench` in `court/feed.py`; flaky check + shrinker in `court/court.py`, `court/shrink.py` |
| 8 | 2:35-2:50 | Tab 1, press **8**. Numbers bar and credibility meter settle. | "Verdict: fidelity 100, credibility 1000 to 930, Brier 0.071. Every number on this screen was measured today, and the court can be wrong in public." | `cases/todo.case.yml`; `cases/METRICS.md` |

Timing rule: if running long, cut beat 2 to 8 seconds (one key press) and beat 7 to 15 seconds. Never cut beats 5 and 6.

**Beat 7 caveat (VERIFY).** The bench console builds steps from the original's buttons (`readKeys`, `parseShortcut` in `court/ui/src/bench/benchRun.ts`) and has no `type:` step input. The todo original has one button (`#add`, `apps/todo/original/index.html`), so a judge cannot type a task string into the todo bench today. The calculator tab supports free key entry. Say "calculator" out loud on that beat; do not imply the judge typed a todo item. If time allows, ask P3 for a text-step input on the bench; do not promise it. Backup for a todo bench without the UI: the court itself takes todo steps (P1 verified 14:37 on main): `curl -s -X POST localhost:8797/todo/bench -H 'content-type: application/json' -d '{"steps":["type:#item:Buy milk","key:Enter"],"observe":"#todo"}'` returns one verdict (original vs revival, run twice). Todo selectors: `#item #add #todo #completed .complete .remove`.

**Beat 5 naming note.** The struck claim is **c07** in the committed files, not c15. c15 is "Completed items stack with the most recently completed on top" and is LOCKED. The empty-task claim is the one tied to issue #38.

**Muse on stage (only if rehearsed twice, workplan T9).** Replace the second half of beat 6 with a live repair in cases mode against v1: `python revive/repair.py --claims <claims.json> --verdicts <v1 verdicts.json> --attacks cases/todo/attacks.json --html revive/out/todo/index.v1.html --builder muse` (needs the box court, `revive/box_verify.py`: ssh `seabridge-pilot`). Do not use `--claim c07`: c07's committed verdict has `match: true` (the claim is false, but the revival already matches the original), so `repair.py` refuses it. Muse is run with shell, write and web tools disabled (`revive/build.py`). A Muse repair of v1 is already committed (`cases/todo/repairs.jsonl` line 2, `revive/out/todo/index.muse.html`, 68 -> 0 mismatches, 20/20); the promoted `index.html` is the Codex repair. If the live run does not work twice in rehearsal, point at the committed Muse row in `cases/BEFORE_AFTER.md` instead.

## 2. One-minute video: shot list (text cards only, 60 s)

Cards are white on black, one idea each, no voiceover required. Only show what was built today. The vendored todo app is third party and credited on the last card.

| Time | Card text | Number source |
|---|---|---|
| 0:00-0:06 | SÉANCE. A fidelity court for resurrected software. Built today at AIE Code Summit. | README.md |
| 0:06-0:14 | A dead todo app. 55 pieces of evidence dug up. 24 behaviors read. | dig/out/todo/evidence.json, sheet.json |
| 0:14-0:22 | A revival built from the sheet alone. 16 claims sworn, each with a confidence and a bond. | dig/out/todo/claims.json |
| 0:22-0:29 | A skeptic who never saw the claims. 105 attacks, hashed before the claims were revealed. | cases/todo/verdicts.json, cases/todo.commits.json |
| 0:29-0:37 | The court has no model in it. 15 claims locked. 1 struck: PERJURY. The claim: an empty task can be created (issue #38). Bond lost: 198 (net credibility 1000 to 930, the stage shows -70). | cases/todo.case.yml, dig/out/todo/claims.json |
| 0:37-0:47 | Repair. Attack mismatches 68 to 0. Fidelity 41 to 100 (measured, all 121 verdicts). Regression 19/20 to 20/20. | cases/before_after.json, cases/todo/v{1,2}-16claims/verdicts.json |
| 0:47-0:53 | False strikes on good behavior: 0 of 12. | cases/METRICS.md |
| 0:53-0:58 | Credibility 1000 to 930. Brier 0.071 over 16 claims. | cases/todo.case.yml |
| 0:58-1:00 | The dead app gets a lawyer, not a fan. Oracle app: themaxsandelin/todo, MIT. | README.md, CREDITS.md |

## 3. Numbers we say (every number and its source)

All paths relative to the repo root. "Counted" means counted from the named file's contents.

| Number we say | Value | Source |
|---|---|---|
| Evidence items dug up | 55 (14 tier B, 41 tier C) | `dig/out/todo/evidence.json`, counted |
| Behaviors read | 24 | `dig/out/todo/sheet.json`, counted |
| Claims sworn | 16 | `cases/todo.case.yml` (`counts.claims`) |
| Locked / struck / fabricated / unsworn | 15 / 1 / 0 / 0 | `cases/todo.case.yml` |
| Struck claim | c07, "An empty task can be created"; confidence 0.8906, bond 198; evidence e007 = issue #38 | `dig/out/todo/claims.json`, `dig/out/todo/evidence.json`, `cases/todo/locks.json` |
| Attacks (sealed, blind to claims) | 105 | `cases/todo/verdicts.json` (kind attack), counted; hashes `cases/todo.commits.json` |
| Court verdicts | 121 (16 claims + 105 attacks), all revival-matches-original on v2 | `cases/todo/verdicts.json`, counted |
| Attack mismatches, v1 to v2 | 68 to 0 (attacks only); the stage's "Differences" counter shows 71 to 0 = 68 attacks + 3 claims (c06, c14, c16) | `cases/before_after.json`, `cases/todo/repairs.jsonl` |
| Fidelity, v1 to v2 | 41 to 100, MEASURED: CONTRACTS.md definition (100*matched/(matched+mismatched), flaky excluded) over all 121 verdicts (P2's 16 claims + the sealed 105 attacks). v1: 50 of 121 match (71 mismatches: 68 attacks + claims c06, c14, c16) = 41; v2: 121 of 121 = 100; 0 flaky. Re-run on the box (court.court, original vs `revive/out/todo/index.v1.html` and `index.html`; seal verified with `eval/seal.py --verify`) and committed as `cases/todo/v1-16claims/` and `cases/todo/v2-16claims/` (`verdicts.json`, `locks.json`); scored with `eval/score.py:fidelity`. Older, different denominators: attacks only 35 to 100 (`cases/before_after.json`, `repairs.jsonl`); `cases/todo/verdicts.json` at 9a5877c used P1's 8 claims and gives 36. | `cases/todo/v1-16claims/verdicts.json`, `cases/todo/v2-16claims/verdicts.json`, `cases/before_after.json` (`fidelity_all_verdicts`), `cases/BEFORE_AFTER.md` |
| Regression, v1 to v2 | 19/20 to 20/20 | `cases/before_after.json`, `cases/METRICS.md` |
| False strikes | 0/12 | `cases/METRICS.md`, `cases/todo.case.yml` |
| Traps flagged | v1 1/8, v2 0/8 (fewer after repair means the revival now matches the original on them) | `cases/before_after.json`, `cases/BEFORE_AFTER.md` |
| Brier | 0.071 (n=16) | `cases/todo.case.yml`, `cases/METRICS.md` |
| Credibility | 1000 to 930 | `cases/todo.case.yml` |
| Repairs | patched 2, rollback 0, unsworn 0 (todo): Codex v1 -> v2 (promoted) and an independent Muse repair of v1 (`index.muse.html`, not promoted) | `cases/METRICS.md`, `cases/todo/repairs.jsonl` |
| Fixture calculator (app1), if asked | 3 repairs; regression 18/20 to 20/20; fidelity 60 final; Brier 0.173 (n=5); credibility 1000 to 982 | `cases/BEFORE_AFTER.md`, `cases/METRICS.md` |
| Stage phases | 8 (dig, read, raise, swear, cross, repair, bench, sentence) | `court/ui/src/engine/types.ts` |
| Runs per build for the flaky check | 2 | `CONTRACTS.md`, `court/court.py` |

Do not say: any latency, token count, cost, "N models", uptime, or accuracy figure; none is in the repo. Do not say "36" for fidelity.

## 4. Sponsor usage (only what the code does)

- **Muse (Meta), partial.** `revive/build.py` has a `muse` builder: `muse exec` with shell, file-write and web tools disabled, prompt passed by file; `revive/repair.py --builder muse` selects it; `dig/reader.py` prefers a `META` provider when configured (`agents/llm.py first_provider`). Unit test: `revive/test_build.py`. **Muse produced one committed repair of todo v1** (`cases/todo/repairs.jsonl` line 2, builder `muse`: 68 -> 0 attack mismatches, regression 19 -> 20; output `revive/out/todo/index.muse.html`, row `v2-muse` in `cases/BEFORE_AFTER.md`). The promoted revival (`index.html` = v2) is the Codex repair. No revival was built from scratch by Muse. Say "Muse repaired it too, independently"; do not say the stage runs Muse.
- **ASI-1 (Fetch.ai's model API), yes.** `agents/llm.py` defaults to `https://api.asi1.ai/v1`, model `asi1`. It is the reader (`dig/reader.py`) and the Medium (`agents/medium.py`) that wrote the todo behavior sheet and claim cards (commit 63dc375). Say "ASI-1", not "agents".
- **Fetch uAgents on Agentverse + ASI:One, yes (verified live 15:51 PT).** `agents/mesh/` (PR #14) has three uAgents: McClusky (medium, ASI-1), Dr. Hoot (skeptic), the Bailiff (court, no model), registered ACTIVE in the Agentverse almanac with mailbox endpoints. Live test from ASI:One: `@thebailiff hello` → "All rise! Your Honor...", choose *The case of Todo* → the court runs the real case on both builds and replies: 16 claims, 20 attacks, 15 held, 1 struck ("An empty task can be created"), no differences between the apps. Then *Hear them argue* (live Hoot vs McClusky debate, agent to agent on ASI-1) or *Test it yourself*. The agents run on Vi's laptop: start them before the demo.
- **MongoDB Atlas, optional read path only.** `court/ui/server/feed.ts` reads the case collections from Atlas when `MONGODB_URI` is set (the masthead shows "MongoDB Atlas" in that mode). Nothing in the repo writes to Atlas, and the demo run above reads `runs/` files. Say "the stage can read a case from Atlas", not "stored in Atlas".
- **SubQ Snap, yes.** `agents/llm.py decide`, used in `agents/medium.py` to set each claim's sworn confidence from its cited evidence.
- **Codex, yes.** `revive/build.py --builder codex`; produced the todo repair v1 to v2 and the app1 t04 repair (`cases/BEFORE_AFTER.md`); also the Skeptic variant `eval/skeptic_codex.py`.
- **Claude and GLM, builders exist, no recorded revival from them.** `revive/build.py --builder claude|glm`. Claude sessions and subagents did the orchestration and reviews per `revive/P4_WORKPLAN.md`. Do not say Gemini: `AGENTS.md` lists it but `revive/P4_WORKPLAN.md` says "No Gemini" and the code has none.

## 5. Likely judge questions

1. **Is a model deciding the verdicts?** No. `court/court.py` runs each test twice per build in a browser and compares text; `court/bailiff.py` maps results to LOCKED, STRUCK, UNSWORN, FABRICATED. Credibility and Brier are pure functions in `eval/score.py`.
2. **100 fidelity after repair: is that overfit?** Partly, and we say so. The repair targeted the diverging attack verdicts, so 105/105 matching is not a held-out score. The separate 20-behavior regression set (12 good, 8 traps) went 19/20 to 20/20. We did not measure fresh attacks after the repair.
3. **Only one claim struck out of 16. Rigged?** The strike cost 198 credits at 0.89 confidence, and the court told issue #38 apart: whitespace-only input does create a blank item (locked), a truly empty input does not (struck). Brier 0.071 is the calibration score; it is not 0.
4. **How is the Skeptic independent?** It never sees claim text. Its attacks and the regression set are hashed and committed before the claims are revealed (`eval/seal.py`, `cases/todo.commits.json`). The attacker and the reviser are different vendors by rule (`revive/P4_WORKPLAN.md`).
5. **Is model-written code safe to run? What is real versus fixture?** Revival code is evaluated with Node permissions plus a seccomp network block, failing closed on Linux (`revive/README.md`; on Windows there is no seccomp, so untrusted revivals are scored on the Linux box); the stage exhibits are static pages. Everything in the repo was written today; the todo app is a vendored MIT oracle (`CREDITS.md`), and app1 is a fixture calculator.
6. **Where do the sponsors fit?** ASI-1 reads the evidence and writes the claims; SubQ Snap sets the confidence; Codex builds and repairs; the Muse builder is wired for the repair step (see section 4 for what has and has not run); Atlas is an optional stage data source.

## 6. Risks to settle before the demo

- Beat 7 judge input works on the calculator only (see caveat). Todo bench takes button presses only.
- Stage repair replay does not exist for `source=runs`; beat 6 uses files.
- Muse has one committed repair of v1 (not promoted); no live Muse run on stage unless rehearsed twice. Fetch: the uAgents answer in ASI:One only while they run on Vi's laptop; start them before the demo and keep a recording as backup.
- `runs/todo/` needs the P2 files copied in and possibly a `case.json`.
- `court.feed` and the venv Chrome shim in `court/ui/RUNBOOK.md` are the P1 and P3 teams' to confirm.

## Why it matters (impact line, checked by P1 against news reports)
"In October and November 2026, attackers hit Danfoss refrigeration controllers at supermarkets across Europe and set them to defrost overnight: up to ~700 stores in France on 11 Oct, then a second wave across ~10 EU countries on 2 Nov (SecurityWeek, The Hacker News, NPR). Much of that legacy software can't be patched anymore; the fix is to rebuild it, but a rebuild you can't verify is a new risk. MUSÉANCE is the court that checks a rebuild against the original before you swap it in: claims the original contradicts are STRUCK; anything the court can't reproduce reliably is UNSWORN, never struck. Today we demo a dead todo app and 2048, not a controller."
Do not name specific controller models (not confirmed for these attacks), and do not link Copeland's separate Frostbyte10 disclosure to them.


## Demo laptop commands (verified by the P4 smoke test, 16:12 PT)
Run from the repo root, one terminal each (`python` or `.venv/bin/python`); on macOS/Linux use `export VAR=...` instead of `set VAR=...`:
```
python -m http.server 8011 -b 127.0.0.1 -d apps/todo/original
python -m http.server 8012 -b 127.0.0.1 -d revive/out/todo
set COURT_BROWSER_CHANNEL=chrome && python -u -B -m court.feed --runs runs --port 8797
cd court/ui && npm ci && npm run seed -- todo
cd court/ui && set COURT_URL=http://127.0.0.1:8797 && node server/feed.ts
cd court/ui && npm run dev
```
Open `http://localhost:5173/?source=runs&app=todo&view=stage`. Expected: fidelity 41 to 100, differences 71 to 0, 15 LOCKED / 1 STRUCK (c07), Brier 0.071, credibility 1000 to 930, false strikes 0 of 12. If a port is taken, set `PORT=` for the feed and point vite's `/api` proxy at it.

## FINAL demo order (16:30 PT, Cold Room leads per Alejandro)
1. **Cold Room Court (fridge, ~60 s).** Same cold-room controller, two builds: `revive/out/coldroom/original.py` (port 5020, no auth) vs `patched.py` (port 5021, +3 lines in `PATCH.diff`). The court (P1, `court/ics`) starts a fresh controller per run and runs every check twice per build. Result (P1 gate, 16:28): **6/6 control behaviors identical** (compressor hysteresis, alarm after 10 min, defrost 6 h / 20 min), **3/3 attacks blocked on the patched build** (unauthenticated setpoint 25.0 °C, out-of-range, wrong PIN), 0 flaky, ledger intact. Say: "modeled on the Danfoss controllers in the Oct/Nov 2026 EU supermarket attacks, not vendor code."
2. **Todo case (~75 s).** `?source=runs&app=todo&view=stage`: fidelity 41 → 100 (121 verdicts), differences 71 → 0, 15 of 16 claims locked, c07 PERJURY (empty task, issue #38), 0/12 false strikes, repaired independently by Codex and Meta Muse.
3. **ASI:One live (~30 s).** `@thebailiff hello` → choose *The case of Todo* → the Fetch.ai agents run the real court.

Cold Room commands (repo root, `pip install pymodbus`):
```
python revive/out/coldroom/original.py --port 5020
python revive/out/coldroom/patched.py --port 5021
```
then P1's court per `court/ics/README.md`.
