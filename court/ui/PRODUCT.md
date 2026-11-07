# Product

<!-- impeccable:product-schema 1 -->

Scope: lane P3 (Court UI & cast) of SÉANCE, folder `court/ui/`. Repo-wide truth lives in `AGENTS.md` and `CONTRACTS.md`.

## Platform

web

## Stack

Vite + React 19 + TypeScript 7 in `court/ui/`, plus a small Node 24 server (`server/feed.ts`) that streams case data from `runs/<app>/` files or MongoDB Atlas to the stage over server-sent events. Vi chose "Vite, React, and TypeScript, or maybe Next … whatever works with Atlas"; Vite was picked for start-up speed and parallel component work, and the feed server is the Atlas bridge.

## Users

- The room at the AIE Code Summit hackathon demo: judges and attendees watching one 16:9 projector driven by one laptop, for a run of about 3 minutes.
- The human judge at the bench, who types an unrehearsed input that the court rules on live.
- The team driving the run from the keyboard (Vi, P3).

## Product Purpose

SÉANCE is a fidelity court for resurrected software. Agents dig up evidence of a dead app, a medium rebuilds it and swears claims about each behavior with a confidence and a bond, a skeptic attacks, and a deterministic court rules. The P3 stage makes that court watchable. Success: a stranger understands within seconds that a revival is on trial, sees a claim fail and get repaired, and trusts the numbers because each one was measured.

## Positioning

The agent commits to every behavior, in public and with a stake, before anything checks it; a court with no model rules; only survivors lock. The stage dramatizes that commitment and its falsification. It is not a diff tool and not a dashboard.

## Operating Context

- Hackathon day 2026-11-07. Checkpoints: 12:30 lanes run on fixtures, 13:30 app1 end to end in the terminal, 14:45 full run through the UI, 15:30 freeze, submit by 16:45 PT.
- Data arrives through the shared contracts in `CONTRACTS.md`: repo fixtures first, then `runs/<app>/` JSON files, then Atlas collections of the same names.
- Lane status goes to the WhatsApp group "AIE Hack" every 30 minutes.

## Capabilities and Constraints

- Phases on stage: Dig, Read, Raise, Swear, Cross, Repair, Bench, Sentence.
- Claim statuses: LOCKED, STRUCK (stamped PERJURY), UNSWORN (flaky test), FABRICATED. Evidence tiers A to D.
- Scoring rules belong to P4 and `CONTRACTS.md`; the stage displays them and never decides a verdict.
- P3 edits only `court/ui/`; shared files change only after a `[CONTRACT]` post.
- Undecided: P1's bench endpoint (`COURT_URL`), the Atlas connection, the path of P4's revival build, and which licensed dead app replaces the fixture calculator.

## Brand Commitments

- Name SÉANCE. Lines: "The dead app gets a lawyer, not a fan." and "He's not a good medium. He's a measurable one."
- Cast: The Departed (translucent ghost wearing its broken app icon as a hat), McClusky, Esq. (round penguin barrister with wig, too many scarves, candlestick, clipboard; speaks only in subtitles), Dr. Hoot (owl skeptic with spectacles, clipboard, stopwatch), Faux (cardboard standee of the app with googly eyes), the little guys (one creature per app feature that glitches when its claim fails), the Judge (a human).
- Visual style is pinned by Vi's reference illustration: flat ink-outline cartoon, teal wall, sand floor, terracotta and walnut furniture, candlelight. Cast art is hand-authored SVG.
- Tone: funny without being a joke; every joke has a number behind it; machine log is machine text.

## Evidence on Hand

- `fixtures/claims.json`, `attacks.json`, `verdicts.json` (5 each) and `fixtures/app1/`, a fixture calculator written today, not a real dead app.
- Vi's reference illustration (held outside the repo).
- No measured metrics yet. The numbers in Vi's pitch doc (294,118 words, 8/8 traps, Brier 0.09, 71/100) are placeholders and must not appear on stage.

## Product Principles

1. Prove, don't claim: every number on stage was measured today or shows as a dash.
2. The ruling is the show: a strike reads from the back of the room without reading a number.
3. Honest gaps are content: UNSWORN and FABRICATED are first-class and printed in red.
4. The court decides, the stage shows: no verdict is computed by a model or invented by the UI.
5. Survives failure: the fixture replay runs offline if every API is down.

## Accessibility & Inclusion

Projector legibility (no text under 20 design px, high contrast), reduced-motion support, full keyboard control, and rulings announced through an aria-live region.
