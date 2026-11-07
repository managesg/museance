"""McClusky, Esq.: the Medium on the Seance mesh (ASI-1 voice), and the front door for chat users.

    agents/mesh/.venv/bin/python -m agents.mesh.mcclusky [--mailbox]      # port 8782

From the Bailiff only (sender checked):
  CallMedium    -> Testimony   P2's sworn claims (case.make_claims); McClusky never writes a claim himself
  Progress      -> queued      for the chat user's raise handler: at most 4 short status lines
  Ruling        -> queued      the final reply, rendered by the Bailiff from the court's files
  RemarkRequest -> Remark      one ASI-1 line aimed at Dr. Hoot, with the ruling's numbers
Chat: raise <app> (or "can you bring back the todo app?"), help, claims, credibility, why <claim>; anything else
is free talk with ASI-1, told only the case on file. The raise handler waits for the case and answers from inside
the chat handler (ASI:One threads replies by session and shows only the last message), so the final reply is
complete on its own. With AGENTVERSE_API_KEY it carries the first mismatch's two screenshots.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import pathlib
import re
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from uagents_core.types import DeliveryStatus  # noqa: E402

from agents.mesh import base, captions, case, commands, voice  # noqa: E402
from agents.mesh.models import CallMedium, OpenCase, Progress, Remark, RemarkRequest, Ruling, Testimony  # noqa: E402

ROLE = "mcclusky"
CASE_S = 600  # the longest a chat user waits for a case
# plain-words raise. Not "revival" or "seance": people ask about the revival and about Seance all the time
INTENT = re.compile(r"(?i)\b(?:bring\b.{0,40}?\bback|resurrect\w*|reviv(?:e|ing)|reanimat\w*|exhum\w*|summon\w*"
                    r"|on\s+trial|put\b.{0,30}?\bon\s+trial)\b")


def intent_app(text: str, docket: dict) -> str | None:
    """'can you bring back the todo app?' -> 'todo'; None when nothing asks for a revival. An unknown app comes
    back as the first word after the verb, so it gets the usual refusal."""
    m = INTENT.search(text or "")
    if not m:
        return None
    words = lambda s: [w for w in re.findall(r"[a-z0-9_-]+", s.lower()) if w not in commands.FILLER]  # noqa: E731
    return next((w for w in words(text) if w in docket), None) or next(iter(words(text[m.end():])), "")


def talk_prompt(text: str, last: dict, docket: dict) -> str:
    """Free talk is told only the case on file, so every number McClusky says is real."""
    r = last["ruling"]
    if r and not r.get("error"):
        c = r["counts"]
        head = (f"Last case {r['case_id']} on {r['app']}: claims about the original {c['LOCKED']} locked, "
                f"{c['STRUCK']} struck, {c['UNSWORN']} unsworn of {r['claims']}; revival {r['differ']} of "
                f"{r['judged']} behaviors differ, fidelity {r['fidelity']}; your credibility "
                f"{r['credibility_start']} to {r['credibility_end']}.")
    else:
        head = "No ruling on file yet."
    ready = [a for a, why in docket.items() if not why]
    return (f"Facts, the only numbers you may use: {head} Apps you can put on trial: {', '.join(ready) or 'none'}; "
            f"the user starts one by typing: raise <app>. The user says: \"{captions.short(text, 400)}\"")


def attach(user: str, shots: list[dict]) -> list:
    """R8: the first mismatch's original and revival screenshots as ResourceContent, stored on Agentverse and
    readable by the chat user. [] without AGENTVERSE_API_KEY or on any failure. Blocking (requests)."""
    key = os.environ.get("AGENTVERSE_API_KEY")
    if not key or not shots:
        return []
    try:
        from uagents_core.config import AgentverseConfig
        from uagents_core.contrib.protocols.chat import Resource, ResourceContent
        from uagents_core.storage import ExternalStorage
        cfg = AgentverseConfig()
        store = ExternalStorage(api_token=key, storage_url=getattr(cfg, "storage_endpoint", None) or cfg.storage_api)
        out = []
        for side in ("original", "revival"):
            png = (ROOT / shots[0][side]).read_bytes()
            asset = store.create_asset(f"{shots[0]['ref']}.{side}.png", png, mime_type="image/png")
            store.set_permissions(asset, agent_address=user)
            out.append(ResourceContent(resource_id=uuid.uuid4(), resource=Resource(
                uri=f"agent-storage://{store.storage_url}/{asset}", metadata={"mime_type": "image/png", "role": "image"})))
        return out
    except Exception as ex:  # noqa: BLE001 - screenshots are optional; the text line says where they are
        base.log.warning("screenshots not attached (%s)", type(ex).__name__)
        return []


class McClusky:
    """Every handler is a plain coroutine, so tests drive them with a fake ctx; build() wires them to a uAgent."""

    def __init__(self, bailiff: str, hoot: str = "", runs=case.RUNS):
        self.bailiff, self.runs, self.app = bailiff, pathlib.Path(runs), ""
        self.peers = {bailiff, hoot} - {""}
        self.waiting: dict[str, asyncio.Queue] = {}  # chat user -> what the Bailiff sends for their case

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
            claims, dropped = await asyncio.to_thread(case.make_claims, msg.app, inp, self.runs)
            out = Testimony(case_id=msg.case_id, app=msg.app, claims=claims, dropped=len(dropped))
        except Exception as ex:  # noqa: BLE001 - an error answer adjourns the case now, not at the Bailiff's timeout
            out = Testimony(case_id=msg.case_id, app=msg.app,
                            error=base.redact(captions.short(f"{type(ex).__name__}: {ex}", 200)))
        await ctx.send(sender, out)

    async def on_progress(self, ctx, sender: str, p: Progress):
        if self._from_bailiff(ctx, sender, "Progress") and p.requester in self.waiting:
            await self.waiting[p.requester].put(p)

    async def on_ruling(self, ctx, sender: str, r: Ruling):
        if not self._from_bailiff(ctx, sender, "Ruling"):
            return
        self.app = r.app or self.app
        if r.requester in self.waiting:
            await self.waiting[r.requester].put(r)

    async def on_remark(self, ctx, sender: str, req: RemarkRequest):
        if not self._from_bailiff(ctx, sender, "RemarkRequest"):
            return
        text = await asyncio.to_thread(voice.mcclusky_line, req.ruling, req.answer)
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
            return await asyncio.to_thread(voice.persona, ROLE, talk_prompt(text, last, docket)), {"cmd": "talk"}
        r, claims, app = last["ruling"], last["claims"], last["app"]
        if not claims or not r or r.get("error"):
            return captions.no_case(app), {"cmd": name, "ok": False}
        if name == "claims":
            return captions.claims_list(app, claims, last["locks"]), {"cmd": "claims", "app": app, "claims": len(claims)}
        if name == "credibility":
            return (f"🐧 Credibility {r['credibility_start']} → {r['credibility_end']}, Brier {r['brier']}, "
                    f"{r['counts']['LOCKED']} locked of {r['claims']}. A rounding error, Your Honor.",
                    {"cmd": "credibility", "app": app, "case_id": r["case_id"], "credibility": r["credibility_end"]})
        c = next((c for c in claims if c["id"] == arg), None)  # why
        if not c:
            return (f"I swore no {arg} on {app}: my testimony runs c01 to c{len(claims):02d}. Next question.",
                    {"cmd": "why", "claim": arg, "ok": False})
        lock = next((x for x in last["locks"] if x["claim_id"] == arg), None)
        return captions.why_line(c, lock), {"cmd": "why", "claim": arg, "status": lock["status"] if lock else "PENDING"}

    def on_file(self, app: str, docket: dict) -> dict:
        """case.last_case() for the app named, else my last case, else the newest ruling on disk."""
        if app not in docket:
            newest = max(self.runs.glob("*/ruling.json"), key=lambda p: p.stat().st_mtime, default=None)
            app = self.app or (newest.parent.name if newest else "")
        return case.last_case(app, self.runs) if app else {"app": "", "ruling": None, "claims": [], "locks": []}

    async def raise_case(self, ctx, user: str, app: str, docket: dict):
        """Open the case at the Bailiff for this user, relay at most 4 status lines, then answer with the final
        reply, all from inside the chat handler."""
        ready = [a for a, why in docket.items() if not why]
        if not app:
            return (f"Raise what, exactly? {captions.docket(docket)} Say: raise {(ready or ['todo'])[0]}",
                    {"cmd": "raise", "ok": False, "ready": ready})
        if app not in docket or docket[app]:
            return captions.refusal(app[:40], docket), {"cmd": "raise", "app": app[:40], "ok": False, "ready": ready}
        if user in self.waiting:
            return f"{captions.IN_SESSION} Your case is still running; the ruling lands here.", {"cmd": "raise", "ok": False}
        q = self.waiting[user] = asyncio.Queue()
        try:
            sent = await ctx.send(self.bailiff, OpenCase(app=app, requester=user))
            if sent.status == DeliveryStatus.FAILED:
                return (f"The Bailiff did not answer ({captions.short(sent.detail, 60)}). Once he is up, say raise "
                        f"{app} again.", {"cmd": "raise", "app": app, "ok": False})
            self.app, shown = app, 0
            while True:
                msg = await asyncio.wait_for(q.get(), CASE_S)
                if isinstance(msg, Ruling):
                    break
                if msg.event in case.PROGRESS and shown < len(case.PROGRESS):
                    shown += 1
                    await base.send_text(ctx, user, ROLE, case.PROGRESS[msg.event], cmd="raise", app=app,
                                         case_id=msg.case_id, event=msg.event, ok=True)
        except asyncio.TimeoutError:
            return f"No ruling after {CASE_S} s; ask the Bailiff: status.", {"cmd": "raise", "app": app, "ok": False}
        finally:
            self.waiting.pop(user, None)
        if msg.error and not msg.case_id:  # refused before the case opened
            return msg.text, {"cmd": "raise", "app": app, "ok": False}
        pics = await asyncio.to_thread(attach, user, msg.shots)
        text = msg.text
        if pics:  # the screenshots ride along, so drop the line that says where they are
            text = "\n\n".join(p for p in text.split("\n\n") if not p.startswith("📸"))
        return text, msg.data, pics


def _address(role: str) -> str:
    try:
        return base.address(role)
    except RuntimeError:  # that seed is not in .env: nothing of ours to recognize
        return ""


def build(runs=case.RUNS):
    """The uAgent on port 8782. Call it inside main(): worker processes re-import the main module."""
    agent = base.make_agent(ROLE)
    mc = McClusky(base.address("bailiff"), _address("hoot"), runs)
    agent.include(base.chat_protocol(ROLE, mc.chat), publish_manifest=base.flag("SEANCE_MAILBOX"))
    for model, handler, replies in ((CallMedium, mc.on_call, Testimony), (Progress, mc.on_progress, None),
                                    (Ruling, mc.on_ruling, None), (RemarkRequest, mc.on_remark, Remark)):
        agent.on_message(model, replies=replies)(handler)
    return agent


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="McClusky, Esq.: the Seance Medium as a uAgent.")
    ap.add_argument("--mailbox", action="store_true", help="also on the Agentverse mailbox, for ASI:One (SEANCE_MAILBOX=1)")
    if ap.parse_args(argv).mailbox:
        os.environ["SEANCE_MAILBOX"] = "1"
    base.load_env()
    agent = build()
    print(f"{base.NAMES[ROLE]} {agent.address} on :{base.PORTS[ROLE]}; chat him: raise todo", flush=True)
    agent.run()


if __name__ == "__main__":
    main()
