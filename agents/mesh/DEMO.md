# Demo: the SÉANCE court in ASI:One (Fetch.ai)

You play the judge in ASI:One. Talk only to **`@thebailiff`**. He runs the court and messages
McClusky and Dr. Hoot himself. Type anything: the Bailiff's brain (ASI-1) understands plain
words. Numbers (1, 2, 3) always work too.

## Before the judges arrive (2 minutes)

- Keep the laptop **plugged in with the lid open**. The three agents run on it.
- Open three tabs:
  1. ASI:One, **New Chat**, type `@thebailiff hello`. You should get a reply in about 5 s.
  2. The Bailiff's inspector, which shows the agents' messages to each other:
     https://agentverse.ai/inspect/?uri=http%3A//127.0.0.1%3A8781&address=agent1qw47zhtg9gj55676vy8myruj297339kqdjkj34e2n2xkt2mqewjn2ngyuw0
  3. The backup chat (both cases, public):
     https://asi1.ai/shared-chat/f44701fa-ef7d-4ef8-9fdf-6d29c93d42d5
- Optional: open each case once a few minutes before. Within 5 minutes the verdict comes back at
  once, and the Bailiff says when the court ran it ("The court ran this case 3 minutes ago").
  "Run it again" runs it fresh.

## The pitch (20 seconds)

"Old apps die, and people bring them back with AI. How do you know the revival is the same app?
SÉANCE is a court for that. McClusky, the medium, swears how the dead app behaved and bets his
credibility. Dr. Hoot, the skeptic, seals his attacks before anyone testifies. The Bailiff runs
every test twice, on the dead original and on the revival, in a real browser. Only claims that
survive get locked. And you're the judge."

## The demo (about 3 minutes)

| You type | You'll see (measured live at 17:15) | You say |
|---|---|---|
| `hey bailiff` | "All rise!", one line about each case, three choices (4 s) | "Three Fetch.ai agents on Agentverse. I'm the judge, chatting in ASI:One." |
| `is the todo app really back from the dead?` | "The court is testing…", then the verdict (22 s) | While it runs: "Hoot seals 20 attacks, McClusky swears 16 claims, and the court runs each one twice on both apps." |
| (the verdict) | 15 of 16 claims held, 1 thrown out, no differences | "The copy behaves exactly like the original. Even McClusky's own rumor got thrown out." |
| `why was one claim thrown out?` | "McClusky swore an empty task can be created, and the original shows nothing." (6 s) | "Every answer comes from the case file. The brain can't make up numbers." |
| `let them fight` | Hoot vs McClusky in plain English, then the Bailiff's numbers (5 s) | "Three separate agents messaging each other, with ASI-1 writing their lines." Flip to the inspector tab. |
| `add buy eggs and tick it off` | Both apps run it: same ✅ (7 s) | "My own words, turned into a test, run live on both apps." |
| `it's the real deal` | "Your Honor rules: Faithful. The evidence agrees with Your Honor." | |
| `now the calculator` | The verdict: all 11 claims held, but 7 differences (70 s) | Talk over the wait: "Here the medium was right about the old app, but the copy is off." |
| `what if I press 7 plus plus 8 equals?` | Original 15, copy 8 ❌ "They differ, Your Honor." (20 s) | "Caught live, from a plain-English question." |
| `it's a fake` | "Your Honor rules: Forgery. The evidence agrees with Your Honor." | |

**Short slot (2 minutes):** do the Todo rows, then show the Calculator in the backup chat.

## Words on the screen, in plain English

- **Claim**: something McClusky says the old app did. **Held up** or **locked** means it was true on
  the old app. **Proved false** or **struck** means it was thrown out, and he loses the points he bet.
- **Difference**: the old app and the copy did different things on the same test.
- **Match score** (fidelity): out of 100, how often the copy acted like the original.
- **Original**: the dead app. **Revival** or **copy**: the rebuilt one.

## Tie it to the Fetch.ai track

- Three uAgents are registered on Agentverse with handles (`@thebailiff`, `@mcclusky`, `@drhoot`),
  speak the Chat Protocol, and can be found in ASI:One.
- The agents really talk to each other: Hoot seals his attacks, McClusky testifies, the Bailiff
  runs the court, and the two argue. The inspector shows those messages.
- ASI-1 powers McClusky, Hoot and the Bailiff's understanding of chat. The court itself has no
  model: verdicts are deterministic, and every number comes from the case files.

## If something goes wrong

- **No reply in 30 s:** show the backup chat (tab 3).
- **Agents down:** on the laptop, `cd ~/.superset/projects/aie-code-p2-fetch` and run
  `SEANCE_MAILBOX=1 agents/mesh/.venv/bin/python -m agents.mesh.run up`.
  To stop them: `pkill -f agents.mesh`.
- Start a new chat for each demo. Don't type in the shared backup chat.
