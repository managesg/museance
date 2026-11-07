"""McClusky, Esq.: the Medium on the Seance mesh (ASI-1 brain), and the front door for chat users.

    agents/mesh/.venv/bin/python agents/mesh/mcclusky.py             # port 8771, local-only
    agents/mesh/.venv/bin/python agents/mesh/mcclusky.py --mailbox   # also on the Agentverse mailbox, for ASI:One

From the Bailiff (sender checked against base.address("bailiff")):
  CallMedium    -> Testimony   P2's Medium writes the cards (case.make_claims); McClusky never writes a claim
  Progress      -> relayed     to the chat user who said "raise <app>" here, in arrival order
  Ruling        -> logged      credibility is eval.score's, as the court computed it; stress 0-10; faints under 300
  RemarkRequest -> Remark      a short ASI-1 objection aimed at Dr. Hoot (under 300 credibility, a faint)
Chat: raise <app> (or "can you bring back the todo app?"), help, claims, credibility, why <claim>. Anything
else is free talk with ASI-1, told only the case on file; the sworn claims are read from the court's files.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from uagents_core.types import DeliveryStatus  # noqa: E402

from agents.mesh import base, captions, case, commands  # noqa: E402
from agents.mesh.models import CallMedium, OpenCase, Progress, Remark, RemarkRequest, Ruling, Testimony  # noqa: E402

ROLE = "mcclusky"
FAINT = 300  # credibility below this and McClusky faints
# plain-words raise. Not "revival" or "seance": people ask about the revival and about Seance all the time
INTENT = re.compile(r"(?i)\b(?:bring\b.{0,40}?\bback|resurrect\w*|reviv(?:e|ing)|reanimat\w*|exhum\w*|summon\w*"
                    r"|on\s+trial)\b")
RESERVED = {"ctx", "to", "agent", "text"}  # base.send_text's own parameter names, never machine-line keys


def stress(credibility: int) -> int:
    """0 at the credibility he walks in with, 10 at the line where he faints."""
    return max(0, min(10, round((case.START - credibility) * 10 / (case.START - FAINT))))


def meter(credibility: int) -> str:
    s = stress(credibility)
    if credibility < FAINT:
        return f"Stress {s}/10: McClusky, Esq. has fainted at credibility {credibility}. The scarves will take questions."
    if s <= 2:
        return f"Stress {s}/10: cool as a cucumber in a wig."
    return f"Stress {s}/10: dabbing my brow with scarf number {s}."


def objection(r: dict, answer: str = "") -> str:
    """Closing remark aimed at Dr. Hoot: ASI-1 in character (the canned line offline). Under 300, a faint."""
    cred, s = r["credibility_end"], stress(r["credibility_end"])
    if cred < FAINT:
        return f"*thud* McClusky, Esq. faints at credibility {cred}, stress {s}/10. His scarves will take questions, Dr. Hoot."
    prompt = (f"{captions.objection_prompt(r, answer)} Aim it at Dr. Hoot. Your stress meter reads {s}/10; "
              f"{'you are sweating through your scarves' if s >= 5 else 'stay smug'}.")
    return f"{base.persona(ROLE, prompt, captions.objection(r))} (Stress meter: {s}/10.)"


def intent_app(text: str, docket: dict) -> str | None:
    """'can you bring back the todo app?' -> 'todo'; None when nothing asks for a revival. An app the court never
    heard of comes back as the first word after the verb, so it gets the usual refusal."""
    m = INTENT.search(text or "")
    if not m:
        return None
    words = lambda s: [w for w in re.findall(r"[a-z0-9_-]+", s.lower()) if w not in commands.FILLER]  # noqa: E731
    return next((w for w in words(text) if w in docket), None) or next(iter(words(text[m.end():])), "")


def talk_prompt(text: str, last: dict, docket: dict) -> str:
    """Free talk is told only the case on file, so every number McClusky says is real."""
    r, status = last["ruling"], {x["claim_id"]: x["status"] for x in last["locks"]}
    if r:
        cred = r["credibility_end"]
        counts = ", ".join(f"{r['counts'].get(k, 0)} {k}" for k in captions.STATUSES)
        head = (f"Last case {r['case_id']} on the app {r['app']}: {counts} of {r['claims']} claims, fidelity "
                f"{r['fidelity']}, Dr. Hoot made {r['catches']} catches in {r['attacks']} attacks. Your credibility "
                f"went {r['credibility_start']} -> {cred}, stress {stress(cred)}/10{', you fainted' if cred < FAINT else ''}.")
    else:
        head = f"No ruling on file{' for ' + last['app'] if last['app'] else ''}."
    sworn = [f"{c['id']} {status.get(c['id'], 'PENDING')}, {c['confidence']:.0%}, bond {c['bond']}: "
             f"{captions.short(c['text'], 80)}" for c in last["claims"][:15]]
    ready = [a for a, why in docket.items() if not why]
    return "\n".join([
        "Facts, the only numbers you may use:", head,
        *(["Your sworn claims (quote them exactly; never add, change or withdraw one):", *sworn] if sworn else []),
        f"Apps you can put on trial now: {', '.join(ready) or 'none'}. The user starts a trial by typing: raise <app>.",
        f'The user says: "{captions.short(text, 500)}"'])


class McClusky:
    """Every handler is a plain coroutine, so tests drive them with a fake ctx; build() wires them to a uAgent."""

    def __init__(self, bailiff: str, hoot: str = "", runs=case.RUNS):
        self.bailiff, self.runs, self.app = bailiff, pathlib.Path(runs), ""
        self.peers = {bailiff, hoot} - {""}

    def _from_bailiff(self, ctx, sender: str, what: str) -> bool:
        if sender != self.bailiff:
            ctx.logger.warning(f"ignored {what} from {sender}: only the Bailiff sends that")
        return sender == self.bailiff

    # --- the Bailiff --------------------------------------------------------------------------------------
    async def on_call(self, ctx, sender: str, msg: CallMedium):
        if not self._from_bailiff(ctx, sender, "CallMedium"):
            return
        self.app = msg.app
        try:
            inp = case.load_inputs(msg.app, self.runs)
            claims, dropped = await asyncio.to_thread(case.make_claims, msg.app, inp)
            out = Testimony(case_id=msg.case_id, app=msg.app, claims=claims, dropped=len(dropped))
        except Exception as ex:  # noqa: BLE001 - an error answer adjourns the case now, not at the Bailiff's timeout
            out = Testimony(case_id=msg.case_id, app=msg.app,
                            error=base.redact(captions.short(f"{type(ex).__name__}: {ex}", 200)))
        await ctx.send(sender, out)

    async def on_progress(self, ctx, sender: str, p: Progress):
        if not self._from_bailiff(ctx, sender, "Progress") or not p.requester:
            return
        data = {k: v for k, v in {**p.data, "event": p.event, "case_id": p.case_id, "app": p.app}.items()
                if k not in RESERVED}
        await base.send_text(ctx, p.requester, ROLE, p.text, **data)

    async def on_ruling(self, ctx, sender: str, r: Ruling):
        if not self._from_bailiff(ctx, sender, "Ruling"):
            return
        self.app = r.app
        if not r.error:
            ctx.logger.info(f"case {r.case_id}: credibility {r.credibility_start} -> {r.credibility_end}. "
                            f"{meter(r.credibility_end)}")

    async def on_remark(self, ctx, sender: str, req: RemarkRequest):
        if not self._from_bailiff(ctx, sender, "RemarkRequest"):
            return
        text = await asyncio.to_thread(objection, req.ruling.dict(), req.answer)
        await ctx.send(sender, Remark(case_id=req.case_id, speaker=ROLE, text=text))

    # --- chat ----------------------------------------------------------------------------------------------
    async def chat(self, ctx, sender: str, text: str):
        if sender in self.peers:
            return None  # the Bailiff and Dr. Hoot talk to me in models; answering their chat could loop forever
        name, arg = commands.parse(ROLE, text)
        docket = case.apps(self.runs)
        if name == "talk" and (app := intent_app(text, docket)) is not None:
            name, arg = "raise", app
        if name == "help":
            return captions.help_card(ROLE), {"cmd": "help"}
        if name == "raise":
            return await self.raise_case(ctx, sender, arg, docket)
        last = self.on_file(arg if name in ("claims", "credibility") else "", docket)
        if name == "talk":
            return await asyncio.to_thread(base.persona, ROLE, talk_prompt(text, last, docket)), {"cmd": "talk"}
        r, claims, app = last["ruling"], last["claims"], last["app"]
        if not claims or (name == "credibility" and not r):
            return captions.no_case(app), {"cmd": name, "ok": False}
        if name == "claims":
            return captions.claims_list(app, claims, last["locks"]), {"cmd": "claims", "app": app, "claims": len(claims)}
        if name == "credibility":
            cred = r["credibility_end"]
            return (f"{captions.credibility_line(r)} {meter(cred)}",
                    {"cmd": "credibility", "app": app, "case_id": r["case_id"], "credibility": cred,
                     "stress": stress(cred), "fainted": cred < FAINT})
        c = next((c for c in claims if c["id"] == arg), None)  # why
        if not c:
            return (f"I swore no {arg} on {app}: my testimony runs {len(claims)} claims, c01 to c{len(claims):02d}. "
                    f"Next question.", {"cmd": "why", "claim": arg, "ok": False})
        lock = next((x for x in last["locks"] if x["claim_id"] == arg), None)
        return captions.why_line(c, lock), {"cmd": "why", "claim": arg, "status": lock["status"] if lock else "PENDING"}

    def on_file(self, app: str, docket: dict) -> dict:
        """case.last_case() for the app named, else my last case, else the newest ledger on disk."""
        if app not in docket:
            newest = max(self.runs.glob("*/ledger.jsonl"), key=lambda p: p.stat().st_mtime, default=None)
            app = self.app or (newest.parent.name if newest else "")
        last = case.last_case(app, self.runs)
        if not last["ruling"]:
            last["locks"] = []  # without a ruling the files on disk can mix new testimony with old verdicts
        return last

    async def raise_case(self, ctx, user: str, app: str, docket: dict):
        """Tell the user first, so this reply leads the Bailiff's progress lines, then open the case for them."""
        ready = [a for a, why in docket.items() if not why]
        if not app:
            return (f"Raise what, exactly? {captions.docket(docket).rstrip('.')}. Say: raise {(ready or ['todo'])[0]}",
                    {"cmd": "raise", "ok": False, "ready": ready})
        try:
            inp = case.load_inputs(app, self.runs)
        except case.MissingInput:
            return captions.refusal(app[:40], docket), {"cmd": "raise", "app": app[:40], "ok": False, "ready": ready}
        n_ev, n_lines = len(inp["evidence"]), len(inp["sheet"].get("lines", []))
        await base.send_text(ctx, user, ROLE, f"Splendid. McClusky, Esq. takes the case of {app}: {n_ev} pieces of "
                             f"evidence, a {n_lines}-line behavior sheet and my entire reputation. Calling the Bailiff; "
                             f"the trial plays out right here.", cmd="raise", app=app, ok=True, evidence=n_ev,
                             lines=n_lines)
        sent = await ctx.send(self.bailiff, OpenCase(app=app, requester=user))
        if sent.status == DeliveryStatus.FAILED:
            return (f"The Bailiff did not answer ({sent.detail}). He has no opinion, no model and, it seems, no pulse. "
                    f"Once he is up, say raise {app} again.", {"cmd": "raise", "app": app, "ok": False})
        self.app = app
        return None


def _address(role: str) -> str:
    try:
        return base.address(role)
    except RuntimeError:  # that seed is not in .env: nothing of ours to recognize
        return ""


def build(runs=case.RUNS):
    """The uAgent on port 8771. Call it inside main(): worker processes re-import the main module."""
    agent = base.make_agent(ROLE)
    mc = McClusky(base.address("bailiff"), _address("hoot"), runs)
    agent.include(base.chat_protocol(ROLE, mc.chat), publish_manifest=base.flag("SEANCE_MAILBOX"))
    for model, handler, replies in ((CallMedium, mc.on_call, Testimony), (Progress, mc.on_progress, None),
                                    (Ruling, mc.on_ruling, None), (RemarkRequest, mc.on_remark, Remark)):
        agent.on_message(model, replies=replies)(handler)
    return agent


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="McClusky, Esq.: the Seance Medium as a uAgent on port 8771.")
    ap.add_argument("--mailbox", action="store_true", help="also on the Agentverse mailbox, for ASI:One (SEANCE_MAILBOX=1)")
    if ap.parse_args(argv).mailbox:
        os.environ["SEANCE_MAILBOX"] = "1"
    base.load_env()
    agent = build()
    print(f"McClusky, Esq. {agent.address} at {base.local_url(ROLE)}; chat him: raise todo")
    agent.run()


if __name__ == "__main__":
    main()
