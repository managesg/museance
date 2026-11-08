# MUSÉANCE: final pitch and Q&A

Every number here is sourced from `DEMO.md` (repo facts) or the news links at the bottom (the attack).
Agents demo script: `agents/mesh/DEMO.md`. Backup chat (public): https://asi1.ai/shared-chat/5e74c8f6-5e2d-48d9-8734-baebd82e687b

## Pitch

**ALEJANDRO**

October 11th. Midnight. Hundreds of supermarkets across France.

Nobody breaks in. Nobody touches a thing.

Somewhere on the internet, someone logs into the refrigeration controllers and tells them to defrost. For about six hours, the freezers heat up to fifty degrees Celsius. In some stores, there are fires.

At dawn, staff open the doors to a wall of hot air. Every item goes in the bin. Intermarché's boss puts the bill at tens of millions of euros. One night.

Three weeks later, it happens again. Belgium. The Netherlands. Sweden. Ireland. Estonia.

Here's the part nobody's talking about. Danfoss says most of the hacked controllers were old models that no longer get security updates. In just three days, seventy percent of the exposed ones in France disappeared from the internet. Nobody patched them. They pulled the plug.

Because nobody can prove a patch is safe. Did you close the hole, or did you just change how the fridge cools?

We're MUSÉANCE, a team of three. We put patches on trial.

**LOKESH**

This is a cold-room controller we modeled on the ones that were attacked. It isn't vendor code. Two builds. The original has no authentication. Our patch adds two lines of code.

Watch. I send an unauthenticated command: set the fridge to 25 degrees.

The original accepts it. The patch rejects it.

Now the part that matters: did the patch break anything else? Our court has no AI in it. It runs every cooling behavior twice on both builds: compressor, defrost cycle, alarm timing. Six for six, identical. Two attacks, both blocked. Zero flaky results.

**VI**

That's a controller we wrote. Now the same method on something nobody wrote today: a real, dead 2016 todo app.

Fetch.ai's ASI-1 model reads the evidence and acts as our "medium". It swears to 16 claims about how the original behaved, and it stakes credit on every one.

The first AI rebuild matched the original on only 41% of 121 checks. One claim was outright perjury: it swore an empty task could be added. The original disagreed. The medium lost credit.

We hand the court's evidence back to the builder, and 71 mismatches go to zero. Fidelity goes from 41% to 100%. We ran the repair twice, independently, once with Codex and once with Meta's Muse. Both repairs took every attack mismatch to zero. On the 12 behaviors we already knew were correct, there were zero false strikes. The court never punishes the truth.

Here's what we built on this weekend. Fetch.ai's ASI-1 writes the claims, SubQ sets how confident each one is, and Codex and Meta's Muse do the repairs. The court itself is plain code: a real browser running every check twice. The stage can pull any case straight from MongoDB Atlas. And Fetch.ai's Agentverse puts the whole court on the network.

So this isn't a dashboard only we can read. Open ASI:One, type @thebailiff, and just ask in plain words: "Is the todo app really back from the dead?" Our live agents run the real court for you, right there in chat.

**ALEJANDRO**

This time, it was the food.

But the same kind of box runs the heating in our schools, the air in our hospitals, the pumps in our water plants. They're old, they're online, and they're never getting updated again.

In January 2024, in Lviv, hackers hit heating controllers. Six hundred apartment buildings went without heat for two days, in sub-zero cold. A year earlier, attackers took over a pump controller at an American water utility. The password was the factory default.

Pulling the plug is not a plan. Someone will patch these machines.

And there's only one thing more dangerous than a controller nobody patched: a patch nobody checked.

MUSÉANCE puts that patch on trial before it touches the freezer, the boiler, the school or the hospital.

Because next time, it won't be the ice cream that melts.

## Q&A: who answers what

Rule: the owner answers in two sentences or less. Anyone else adds one line at most. If nobody knows, say "We didn't measure that". Never guess a number.

### The attack and why it matters (Alejandro)

1. **How many stores were hit?** (Alejandro) Reports differ. In France, Intermarché reported about 150 stores, Carrefour 80, and Coopérative U nearly 100. Some outlets say up to 700. The second wave hit around 100 supermarkets in at least six countries.
2. **What did it cost?** (Alejandro) Intermarché's boss estimated tens of millions of euros across France, in one night. The other chains haven't given figures.
3. **How many people were affected, and how much food was wasted?** (Alejandro) Nobody has published either number. The chains threw out everything in the affected fridges for health reasons.
4. **Was it really Danfoss?** (Alejandro) Danfoss confirmed its controllers were involved, mostly older models that no longer get updates. France's cyber agency, ANSSI, says Copeland and Dixell controllers were hit too. We don't name a model.
5. **Why not just unplug the controllers?** (Alejandro) That's what happened: 71% of the exposed ones in France went offline within three days. But stores still need to monitor their cold rooms remotely, so unplugging trades a cyber risk for a food-safety risk. Sooner or later someone reconnects them with a patch, and that's the moment we test.
6. **Who would pay for this?** (Alejandro) Anyone who has to patch equipment the manufacturer has stopped supporting: supermarket chains, the companies that maintain their refrigeration, and building operators for schools and hospitals. It's the sign-off you need before a patch goes live.

### Cold room and the court engine (Lokesh)

7. **Is that a real Danfoss controller?** (Lokesh) No. It's our own model of the controllers that were attacked, not vendor code, and we say so on screen. The method doesn't change: same checks, run twice, on both builds.
8. **What does the two-line patch do?** (Lokesh) Any write to the setpoint or the defrost needs the PIN and has to stay within safe limits. Reading the fridge's state and the cooling logic are untouched, which is why all six control behaviors stay identical.
9. **What are the behaviors and the attacks?** (Lokesh) Behaviors include: the compressor switches off below the setpoint, the high-temperature alarm waits 10 minutes, defrost runs every 6 hours for 20 minutes, there are no alarms during 12 hours of normal cooling, and the room cools back down after a defrost. Attacks: setting the temperature to 25 °C without the PIN, and stretching the defrost from 20 minutes to 8 hours (480 minutes) without the PIN.
10. **Is an AI deciding the verdicts?** (Lokesh) No. The court runs each check twice per build and compares what it observes. Plain code turns the results into a verdict: locked (the original confirms the claim), struck (the original contradicts it), or unsworn (the court can't reproduce it reliably). AI writes the claims, repairs the code, and lets the Bailiff chat. It never judges.
11. **What does "zero flaky" mean?** (Lokesh) Every check runs twice on each build. If the two runs disagree, the check is marked unsworn, never struck. Today every check gave the same answer both times.
12. **What if the patch breaks a behavior?** (Lokesh) A behavior that differs between the two builds shows up as a mismatch, and the patch fails. The court also shrinks a failing case down to the shortest steps that reproduce it.
13. **Can someone tamper with the results?** (Lokesh) Every verdict goes into an append-only ledger, and the court checks it on every run. Today's ledger verified clean.
14. **Does it work on real industrial protocols?** (Lokesh) Yes, our backup build speaks Modbus, the protocol a lot of real controllers use: a three-line patch and three attacks, all blocked. Real firmware is next.

### The todo case and the AI "medium" (Vi, with Alejandro as backup)

15. **Where does the evidence come from?** (Vi) Old code, the issue tracker, documentation, and the running original app. Each piece is ranked by how strong it is. ASI-1 reads all of it and writes a behavior sheet.
16. **What's the medium, and what does it stake?** (Vi) The medium is ASI-1. It turns the behavior sheet into 16 sworn claims and stakes credit on each one. SubQ sets how confident each claim is, based on the evidence it cites. If the original contradicts a claim, the medium loses its stake. Its credit went from 1000 to 930.
17. **Only one claim struck out of 16. Is that rigged?** (Alejandro) The court drew a fine line on that bug. Input that's only spaces really does create a blank item, so that claim is locked. Truly empty input doesn't, so that claim is struck. Calibration (Brier) is 0.071, not a perfect 0.
18. **Why 121 checks when there are only 16 claims?** (Alejandro) Each claim and each sealed attack from the skeptic becomes a check, and every check runs on both the original and the rebuild.

### Repair, skeptic and scoring (Alejandro)

19. **100% fidelity. Isn't that overfitting?** (Alejandro) Partly, and we say so. The repair aimed at the checks that disagreed, so 100% isn't a held-out score. The separate test is a 20-behavior regression set the repair never targeted (12 good behaviors, 8 traps). It went from 19 of 20 to 20 of 20. We haven't yet run fresh attacks after the repair.
20. **How is the skeptic independent?** (Alejandro) It never sees the claim text. Its attacks and the regression set are fingerprinted and committed before the claims are revealed. By rule, the attacker and the repairer come from different vendors.
21. **What did Muse do, and what did Codex do?** (Alejandro) Codex made the repair on stage. Muse made a second, independent repair of the same broken build and reached the same result. Muse doesn't run live on stage.
22. **What's a false strike?** (Alejandro) We had 12 behaviors we already knew were true. A court that struck any of them would be punishing the truth. It struck zero.
23. **Is running AI-written code safe?** (Alejandro) Rebuilt code runs with restricted permissions, and on Linux it's blocked from the network. If it can't be sandboxed, it doesn't run there.

### Infrastructure and Fetch.ai (Vi)

24. **How does it work in ASI:One?** (Vi) Three Fetch.ai agents are registered on Agentverse: McClusky, the medium; Dr. Hoot, the skeptic; and the Bailiff, who runs the court. You chat with @thebailiff in plain English. ASI-1 understands you and writes the agents' lines, but every verdict and number comes from the court, which has no AI in it. Say "let them fight" and McClusky and Hoot argue it out, agent to agent.
25. **Can a judge test it with their own words?** (Vi) Yes. Say "add buy eggs and tick it off", and it becomes a test run live on both apps.
26. **Is that live?** (Vi) Yes. The agents are running on our laptop right now and connect through the Agentverse mailbox. There's also a public backup chat with both cases.
27. **What does MongoDB do?** (Vi) The stage can read a whole case straight from MongoDB Atlas, in the same format as our local files. Today's demo runs from the local files.
28. **Did you use Google or Gemini?** (Alejandro) No. We planned to, but the build went with ASI-1, SubQ, Codex and Muse.

### Wrap-up

29. **What's next?** (Alejandro) Real controller firmware, fresh attacks after every repair, writing every case to Atlas, and the sectors that worry us most: heating, water and hospitals.
30. **What was the hardest part?** (Lokesh) Making flakiness impossible to mistake for a verdict. That's why every check runs twice, and a disagreement is unsworn, never struck.

Never say: latency, cost per run, token counts, uptime, "accuracy", how many models were used, or "36" for fidelity.

## Sources (attack facts)

- CBC: https://www.cbc.ca/news/world/france-supermarket-freezers-overheated-cyberattack-9.7378180
- CNN: https://edition.cnn.com/2026/10/12/europe/france-supermarket-cyberattack-fridges-intl
- CNBC: https://www.cnbc.com/2026/10/13/france-supermarket-hack-cyberattack-fridges-fires.html
- NPR: https://www.npr.org/2026/11/03/nx-s1-6026676/cold-war-hackers-fridges
- The Hacker News (second wave): https://thehackernews.com/2026/11/second-wave-of-cyberattacks-hits.html
- Infosecurity Magazine (71% drop): https://www.infosecurity-magazine.com/news/france-expose-danfoss-controllers/
- Cybersecurity Dive (ANSSI, models): https://www.cybersecuritydive.com/news/refrigeration-france-cyber/832858/
- Lviv heating (FrostyGoop, Jan 2024) and the Aliquippa water utility (Nov 2023): from Dragos and CISA public reports; check them before quoting.
