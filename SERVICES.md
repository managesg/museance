# Services and accounts (consolidated)

One owner for the demo machine and its single `.env`: **Vi** (runs the GitHub repo and the demo laptop). Every key reaches Vi by 1:1 DM only, never in the group chat or the repo. After the hackathon every key below is rotated.

| Service | Env var | Used by (code) | Account today | Consolidated owner |
|---|---|---|---|---|
| MongoDB Atlas, cluster `seance`, db `seance` | `MONGODB_URI` | `court/ui/server/feed.ts`; P2 one-off load (evidence, claims, sheet) | separate hackathon project in Alejandro's Atlas org | Vi invited as Project Owner (needs Vi's email by DM) |
| ASI-1 (Fetch.ai LLM) | `ASI1_API_KEY` | `agents/mesh/voice.py`, `agents/llm.py`, `agents/medium.py` | Vi's key and Lokesh's key both in use | Vi's key only |
| Agentverse / ASI:One agents | `AGENTVERSE_API_KEY`, `MCCLUSKY_SEED`, `HOOT_SEED`, `BAILIFF_SEED` | `agents/mesh/*` | Vi | Vi |
| SubQ (reader) | `SUBQ_API_KEY` | `agents/llm.py`, `agents/medium.py` | Alejandro | DM to Vi |
| Meta Muse Code (repair builder) | CLI login (no key in repo) | `revive/build.py --builder muse` | Alejandro's CLI login | runs from Alejandro's laptop; evidence is committed |
| Codex / Claude / GLM (builders, skeptic) | CLI logins | `revive/build.py`, `eval/skeptic_codex.py` | each person's own | not needed at demo time (results committed) |
| Gemini | `GEMINI_API_KEY` | not used | none | leave empty |
| GitHub `vihuynh72/aie-code` | none | repo | Vi | Vi |

Demo-time rule: the demo only needs `MONGODB_URI`, `ASI1_API_KEY`, the Agentverse key and the three agent seeds on Vi's laptop. Everything P4 shows (revivals, repairs, seals, scores) is committed and runs offline: `python eval/demo_p4.py --fast`.
