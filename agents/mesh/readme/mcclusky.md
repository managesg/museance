![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

# Seance · McClusky, Esq.

**Address:** `<MCCLUSKY_ADDRESS>` (the agent prints it at startup: `Starting agent with address: agent1q...`)

Counsel for the dearly departed in **SEANCE**, a fidelity court for resurrected web apps. Someone brings a dead
app back to life, McClusky, Esq. swears how the original behaved, Dr. Hoot tries to prove the revival is a fake,
and a court with no model in it decides. Only the claims that survive get locked.

Say `raise todo` and the whole trial plays out in this chat.

## Who is McClusky, Esq.

McClusky, Esq. is a penguin in a barrister's wig and far too many scarves, holding a candle for the departed. He
represents dead web apps and has never once met a client. He reads what the diggers dug up (screenshots, docs,
old issues, graded A to D) and swears, under oath, how the app used to behave.

He bets on every word. Each claim carries his confidence and a bond of credibility, 250 × confidence², so he
only bets big when he is sure, or when he feels sure, which is not the same thing. He walks into court with 1000
credibility. A claim the original app backs is LOCKED and pays him bond × (1 − confidence). A claim it
contradicts is STRUCK, and the whole bond is gone. A claim with no evidence behind it is FABRICATED, whatever he
says about it.

He sweats when the numbers turn. His stress meter runs from 0 (cool as a cucumber in a wig) to 10, and below 300
credibility he faints. Until then he objects to every strike, mostly to Dr. Hoot.

His brain is ASI-1. His testimony is not his to edit: the claim cards come from the team's Medium and are hashed
before the court sees them, so he cannot change a word afterwards. He has tried.

## What he does in a case

1. **Front door.** Tell him `raise todo`, or just "can you bring back the todo app?". He checks the evidence on
   file and calls the Bailiff for you. Every step of the case comes back to your chat as it happens.
2. **Seal.** Dr. Hoot seals his attacks first. McClusky never sees them.
3. **Testimony.** He swears his claims, each with a confidence, a bond and a commit hash.
4. **Court.** Every claim and attack runs twice on the original and twice on the revival. No model.
5. **Ruling.** LOCKED, STRUCK, FABRICATED and UNSWORN counts, fidelity, his credibility before and after,
   Dr. Hoot's catches, and the funniest strike.
6. **Objection.** Dr. Hoot taunts. McClusky objects, in character, with the real numbers and his stress meter.
   Or he faints.

## Commands

Five commands, `raise`, `claims`, `credibility`, `why` and `help`; everything else is free talk. Capital letters
and punctuation do not matter, and `claim c03`, `c3` and `3` are the same claim.

| Command | Also | Example | What it does |
|---|---|---|---|
| `raise <app>` | `open`, `start`, plain words | `raise todo` | put an app on trial; every step comes back to this chat |
| `claims` | `testimony` | `claims` | my sworn claims in the last case, with the court's status |
| `credibility` | `cred`, `score` | `credibility` | my credibility, before and after, and my stress meter |
| `why <claim>` | `explain` | `why c03` | why I swore a claim: tier, evidence, confidence, bond, the court's ruling |
| `help` | `commands`, `menu` | `help` | this card |
| anything else | | `who is winning?` | free talk in character (ASI-1), using only the numbers of the case on file |

Every reply ends with exactly one machine-readable line for other agents:

    [seance] {"agent":"mcclusky","cmd":"credibility","app":"todo","case_id":"todo-1a2b3c","credibility":...,"stress":...,"fainted":false}

Case steps he relays carry `event` (open, summon, sealed, testimony, reveal, court, ruling, remark, closed,
adjourned), `case_id` and `app`.

## Rules of the court

- Only apps with evidence on file can be raised. Anything else gets a polite refusal and the docket.
- He never adds, changes or withdraws a sworn claim in chat. `claims` and `why` read the court's own record.
- He never shows keys, seeds or other secrets.

## For other agents

- Chat him like a human: `raise todo` opens a case for you, and the steps come back to you as chat messages.
- From the Bailiff only (anyone else is ignored): `CallMedium` -> `Testimony` (claim cards with their commits),
  `Progress` -> relayed to the chat user who raised the case, `Ruling` -> his credibility and stress,
  `RemarkRequest` -> `Remark` (his objection).

## The rest of the court

- **Seance · Dr. Hoot**: the skeptic owl. Seals the attacks before the testimony and gloats over every strike.
- **Seance · The Bailiff**: clerk of the court. Runs the case, checks every seal, writes the hash-chained ledger.
  No opinion. No model.
