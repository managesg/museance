![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

# Seance · The Bailiff

**Address:** `<BAILIFF_ADDRESS>` (the agent prints it at startup: `Starting agent with address: agent1q...`)

The clerk of **SEANCE**, a fidelity court for resurrected web apps. Someone brings a dead app back to life,
McClusky, Esq. swears how the original behaved, Dr. Hoot tries to prove the revival is a fake, and the Bailiff
runs the trial. Only the claims that survive get locked.

## Who is the Bailiff

The Bailiff stands by the door in a grey uniform with a clipboard, a rubber stamp and a face that has never
moved. It has heard every objection McClusky, Esq. ever made and every "Hoo." Dr. Hoot ever said, and it has
written all of them down, in order, in a hash-chained ledger that nobody can edit without the Bailiff noticing.

It does not take sides. It does not laugh at the owl's jokes. It does not believe the lawyer, or disbelieve
him. It opens the envelopes, runs the tests and reads out the numbers.

**The Bailiff has no opinion. The Bailiff has no model.** Every verdict comes from running the app, never from a
language model.

## What happens when you say `raise todo`

1. **All rise.** The Bailiff opens the case. The previous ledger is filed away, never deleted.
2. **Seal.** Dr. Hoot seals his edge-case attacks before anyone testifies. Only commits and hashes leave the
   envelope.
3. **Testimony.** McClusky, Esq. swears to his claims, each with a confidence and a credibility bond, without
   seeing a single attack.
4. **Reveal.** Dr. Hoot opens the envelopes. The Bailiff checks every attack against the commit he sealed and
   throws out any that changed.
5. **Court.** Every claim and every attack runs twice on the original and twice on the revival. No model.
6. **Ruling.** LOCKED, STRUCK, FABRICATED and UNSWORN counts, fidelity, McClusky's credibility, Dr. Hoot's
   catches, and the funniest strike.
7. **Closing remarks.** Dr. Hoot taunts. McClusky, Esq. objects. The Bailiff has no opinion.

You see every step in the chat as it happens, and every step is on the ledger with a one-line caption.

## Commands

Capital letters and punctuation do not matter, and `claim c03`, `c3` and `3` are the same claim. Anything the
Bailiff does not understand gets this list back.

| Command | Also | Example | What it does |
|---|---|---|---|
| `raise <app>` | `open`, `start` | `raise todo` | open a case on an app with evidence on file |
| `apps` | `docket` | `apps` | the apps the court can raise |
| `status` | `state` | `status` | the current case |
| `status <claim>` | | `status c03` | one claim: LOCKED, STRUCK, FABRICATED or UNSWORN, and why |
| `cross <keys>` | `cross-examine`, `press` | `cross 7+8=` | run your own keys on the original and the revival and compare |
| | | `cross add Buy milk, complete` | todo words: add, enter, complete, uncomplete, remove, remove done |
| | | `cross todo add Buy milk` | name the app first to pick it |
| | | `cross click:#k7, click:#keq` | raw steps work too |
| `ledger` | `chain` | `ledger` | the ledger head and its hash-chain check |
| `case` | `ruling`, `verdict` | `case` | the last ruling, in numbers |
| `help` | `commands`, `menu` | `help` | this card |

Every reply ends with exactly one machine-readable line for other agents:

    [seance] {"agent":"bailiff","cmd":"status","app":"todo","case_id":"todo-1a2b3c",...}

## Rules of the court

- Only apps with evidence on file can be raised. Ask for `apps` to see the docket.
- One case at a time. While a case is in session, `status`, `case`, `ledger` and `cross` answer with the last
  step on the record instead.
- `cross` presses only the app's own buttons: at most 30 steps, one cross per sender every 10 seconds. A cross is
  written on the ledger as `mesh.cross`, never as a verdict of the court.
- The Bailiff never shows keys, seeds or other secrets.

## For other agents

- Send `OpenCase(app, requester)` to open a case. You get one `Progress(case_id, app, requester, event, text,
  data)` per step; the last one is `closed` or `adjourned`. Like McClusky, Esq. and Dr. Hoot, you also get the
  `Ruling` the moment the court rules (with `error` set if the case was adjourned).
- Read-only REST for the stage, on the Bailiff's port 8773: `GET /case` (the case in session, else the last one)
  and `GET /locks` (its lock table).

## The rest of the court

- **Seance · McClusky, Esq.**: counsel for the dead app. Swears the claims and bets credibility on each one.
  Tell him `raise todo` and he calls the Bailiff for you.
- **Seance · Dr. Hoot**: the skeptic owl. Seals the attacks before the testimony and gloats over every strike.
