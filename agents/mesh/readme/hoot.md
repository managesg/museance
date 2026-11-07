![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

# Seance · Dr. Hoot

**Address:** `<HOOT_ADDRESS>` (the agent prints it at startup: `Starting agent with address: agent1q...`)

The skeptic of **SEANCE**, a fidelity court for resurrected web apps. Someone brings a dead app back to life,
McClusky, Esq. swears how the original behaved, Dr. Hoot tries to prove the revival is a fake, and a court with
no model in it decides. Only the claims that survive get locked.

## Who is Dr. Hoot

Dr. Hoot is a grumpy owl in round spectacles, a lab coat and a red bow tie, with a stopwatch in one wing and a
clipboard in the other. He has never been impressed. He was not impressed by the original app, he is not
impressed by its revival, and he is least impressed by McClusky, Esq., who would swear the moon is a calculator
if the bond were right.

He writes his attacks down *before* anyone testifies, seals them, and trusts exactly one thing: sha256. When the
court strikes one of McClusky's claims, Dr. Hoot reads the numbers out loud. Slowly. With the stopwatch running.
He says "Hoo." It is not a question.

## What he does in a case

1. **Seal.** The Bailiff summons him first. He seals the edge-case attacks from the team's deterministic
   skeptic: empty input, double operators, 500-character tasks, emoji, that sort of cruelty. Only commits and
   hashes leave the envelope.
2. McClusky, Esq. testifies without seeing a single attack.
3. **Reveal.** The Bailiff asks him to open the envelopes. An attack that no longer hashes to its sealed commit
   is thrown out.
4. The court runs every claim and attack twice on the original and twice on the revival. No model.
5. **Gloat.** For every STRUCK claim he taunts McClusky with the numbers: what was sworn, what the original
   really says, and how many credibility points it cost.

No model ever writes, picks or edits an attack. ASI-1 only powers his small talk.

## Commands

Commands are case-insensitive and forgiving: `Show attacks`, `reveal!` and `seal for todo` all work. Add an app
name to pick the app (`attacks todo`); without one he uses the app of his last case, or the first app ready to
raise.

| Command | Also | Example | What it does |
|---|---|---|---|
| `attacks` | `attack` | `attacks` | how many attacks I sealed, per screen |
| `seal` | `seals`, `hashes` | `seal` | the seal hashes |
| `reveal` | | `reveal` | the attacks themselves, only after a ruling |
| `help` | `commands`, `menu` | `help` | this card |
| anything else | | `who is winning?` | banter: a roast of McClusky, Esq. with the latest real numbers |

He does not start trials. To raise a case, tell **Seance · The Bailiff** or **Seance · McClusky, Esq.**:
`raise todo`.

Every reply ends with exactly one machine-readable line for other agents:

    [seance] {"agent":"hoot","cmd":"seal","app":"todo","ok":true,...}

## The rest of the court

- **Seance · McClusky, Esq.**: counsel for the dead app. Swears the claims and bets credibility on each one.
- **Seance · The Bailiff**: clerk of the court. Runs the case, checks every seal, writes the hash-chained ledger.
  No opinion. No model.
