"""The Bailiff: clerk of the Seance court and orchestrator of every case. No model anywhere in this process.

    agents/mesh/.venv/bin/python -m agents.mesh.bailiff [--mailbox]

A case opens on OpenCase (McClusky relaying a chat user, the Clerk, any agent) or on "raise <app>" in chat.
The Bailiff runs it through Dr. Hoot and McClusky over the mesh (case.hear with MeshParties): seal, testimony,
reveal (every attack checked against its seal), then judge() in this process, so during a case this process is
the only writer of runs/<app>/ledger.jsonl. Each hop is a mesh.<event> ledger entry with its caption and goes
out as a Progress to the front door, or as a ChatMessage to a chat user who raised the case here. The Ruling
goes to McClusky, Dr. Hoot and the front door. Read-only REST for the stage on port 8773: GET /case, GET /locks.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from uagents import Model  # noqa: E402

from agents.mesh import base, captions, case, commands  # noqa: E402
from agents.mesh.models import (CallMedium, CallSkeptic, OpenCase, Progress, Remark, RemarkRequest,  # noqa: E402
                                RequestReveal, RevealAttacks, Ruling, SealedAttacks, Testimony)

SEAL_S, TESTIFY_S, REMARK_S = 60, 240, 60  # testimony waits on the Medium's llm.chat, which allows 180 s


class CaseView(Model):
    """GET /case: the case in session, else the last one on file."""
    app: str = ""
    case_id: str = ""
    in_session: bool = False
    event: str = ""  # the last mesh event on the record: open, summon, ..., closed, adjourned, cross
    caption: str = ""
    ruling: dict = {}
    chain: str = ""


class LocksView(Model):
    """GET /locks: that case's lock table, [] until the court rules."""
    app: str = ""
    case_id: str = ""
    in_session: bool = False
    locks: list[dict] = []


def _ruling(r: dict, requester: str = "") -> Ruling:
    return Ruling(**{**r, "requester": requester, "text": captions.ruling_text(r)})


def _data(event: str, payload: dict) -> dict:
    """Progress.data and the chat machine line: the payload's numbers and short words; lists become counts."""
    out = {"event": event}
    for k, v in payload.items():
        v = len(v) if isinstance(v, list) else v
        if k not in ("text", "caption") and (isinstance(v, (bool, int, float, dict))
                                             or isinstance(v, str) and 0 < len(v) <= 40):
            out[k] = v
    return out


class MeshParties:
    """case.hear's four parties over the mesh. send_and_receive only accepts a reply signed by the address it
    asked, in this session, so every reply's sender is checked against base.address(role) by construction."""

    def __init__(self, ctx, requester: str = ""):
        self.ctx, self.requester = ctx, requester

    async def _ask(self, role: str, msg, reply_type, timeout: int):
        reply, status = await self.ctx.send_and_receive(base.address(role), msg, reply_type, timeout=timeout)
        who = captions.NAMES[role]
        if reply is None:
            raise case.CaseError(f"{who} did not answer ({status.detail})")
        if getattr(reply, "error", ""):
            raise case.CaseError(f"{who}: {reply.error}")
        if reply.case_id != msg.case_id:  # a late answer to an earlier case in the same chat session
            raise case.CaseError(f"{who} answered for case {reply.case_id}, not {msg.case_id}")
        return reply

    async def seal(self, case_id: str, app: str) -> dict:
        return (await self._ask("hoot", CallSkeptic(case_id=case_id, app=app), SealedAttacks, SEAL_S)).seal

    async def testify(self, case_id: str, app: str) -> tuple[list[dict], int]:
        t = await self._ask("mcclusky", CallMedium(case_id=case_id, app=app), Testimony, TESTIFY_S)
        return t.claims, t.dropped

    async def reveal(self, case_id: str, app: str) -> list[dict]:
        return (await self._ask("hoot", RequestReveal(case_id=case_id, app=app), RevealAttacks, SEAL_S)).attacks

    async def remark(self, speaker: str, case_id: str, app: str, r: dict, answer: str = "") -> str:
        msg = RemarkRequest(case_id=case_id, app=app, ruling=_ruling(r, self.requester), answer=answer)
        return (await self._ask(speaker, msg, Remark, REMARK_S)).text


class Bailiff:
    """The court's state and handlers, apart from uAgents so tests can drive them with a fake ctx."""

    def __init__(self, runs=case.RUNS, clock=None):
        self.runs, self.clock = pathlib.Path(runs), clock
        self.app = ""  # the app of the case in session, or of the last case raised here
        self.live = None  # the case in session; served from memory because judge() owns its files meanwhile
        self.rate = base.RateLimit(10)

    def last_app(self) -> str:
        if self.app:
            return self.app
        ledgers = sorted(self.runs.glob("*/ledger.jsonl"), key=lambda p: p.stat().st_mtime)
        return ledgers[-1].parent.name if ledgers else ""

    def snapshot(self) -> dict:
        """What GET /case and GET /locks serve."""
        if self.live:
            return {**self.live, "in_session": True}
        app = self.last_app()
        if not app:
            return {}
        last = case.last_case(app, self.runs)
        mesh = [e for e in last["events"] if e["type"].startswith("mesh.")]
        ev = mesh[-1] if mesh else {"type": "mesh.", "payload": {}}
        return {"app": app, "case_id": mesh[0]["payload"].get("case_id", "") if mesh else "",
                "event": ev["type"][5:], "caption": ev["payload"].get("caption", ""), "ruling": last["ruling"] or {},
                "locks": last["locks"] if last["ruling"] else [], "chain": last["chain"]}

    def busy(self, cmd: str) -> tuple[str, dict]:
        live = self.live
        return (f"{captions.busy(live['case_id'], live['app'])} On the record: {live['caption'] or 'All rise.'}",
                {"cmd": cmd, "ok": False, "busy": live["case_id"], "event": live["event"]})

    async def raise_case(self, ctx, app: str, sender: str, requester: str = "", chat: bool = False):
        """One whole case. sender is the front door (an agent that sent OpenCase) or, with chat=True, the chat
        user. -> None once the case ran (every hop already went out), else the refusal as (text, data)."""
        if self.live:
            return self.busy("raise")
        try:
            inputs = case.load_inputs(app, self.runs)
        except case.MissingInput:
            return captions.refusal(app, case.apps(self.runs)), {"cmd": "raise", "ok": False, "app": app}
        parties, sink = MeshParties(ctx, requester), case.ledger_sink(app, self.runs, self.clock)
        rulings_to = list(dict.fromkeys([base.address("mcclusky"), base.address("hoot")] + ([] if chat else [sender])))
        case_id = case.new_case_id(app)
        self.app, self.live = app, {"app": app, "case_id": case_id, "event": "", "caption": "", "ruling": {},
                                    "locks": [], "chain": ""}

        async def on_event(event: str, payload: dict, caption: str):
            sink(event, payload, caption)
            self.live.update(event=event, caption=caption)
            text = caption
            if event == "ruling":
                text = captions.ruling_text(payload)
                locks = json.loads((self.runs / app / "locks.json").read_text(encoding="utf-8"))  # judge() just wrote it
                self.live.update(ruling=payload, locks=locks, chain=payload["chain"])
            if event in ("ruling", "adjourned"):
                ruling = _ruling(payload, requester) if event == "ruling" else Ruling(
                    case_id=case_id, app=app, requester=requester, error=payload["reason"], text=caption)
                for to in rulings_to:
                    await ctx.send(to, ruling)
            data = _data(event, payload)
            if chat:
                await base.send_text(ctx, sender, "bailiff", text, **data)
            else:
                await ctx.send(sender, Progress(case_id=case_id, app=app, requester=requester, event=event,
                                                text=text, data=data))

        try:
            await case.hear(app, parties, on_event, case_id=case_id, requester=requester, front_door=sender,
                            runs=self.runs, clock=self.clock, inputs=inputs)
        finally:
            self.live = None
        return None

    async def on_open(self, ctx, sender: str, msg: OpenCase):
        out = await self.raise_case(ctx, msg.app, sender, msg.requester)
        if out:  # refused: a single, final Progress, so the front door stops waiting
            text, data = out
            await ctx.send(sender, Progress(case_id="", app=msg.app, requester=msg.requester, event="adjourned",
                                            text=text, data=data))

    async def cross(self, sender: str, text: str) -> tuple[str, dict]:
        """The sender's own attack, through case.cross (known selectors only, at most 30 steps). An optional app
        id comes first ("cross todo add Buy milk"). Recorded as mesh.cross, never as a court verdict."""
        apps = case.apps(self.runs)
        first, _, rest = text.partition(" ")
        app, text = (first.lower(), rest) if first.lower() in apps else (self.last_app(), text)
        if not app:
            return f"Cross which app? Say: cross todo add Buy milk. {captions.docket(apps)}", {"cmd": "cross", "ok": False}
        try:
            inputs = case.load_inputs(app, self.runs)
            commands.to_steps(inputs["selectors"], text)  # refuse before the sender's 10 s slot is taken
        except case.MissingInput:
            return captions.refusal(app, apps), {"cmd": "cross", "ok": False, "app": app}
        except commands.CrossError as ex:
            return captions.cross_refused(f"on {app}, {ex}"), {"cmd": "cross", "ok": False, "app": app}
        left = self.rate.wait(sender)
        if left:
            return captions.rate_limited(left), {"cmd": "cross", "ok": False, "wait": round(left)}
        x = await asyncio.to_thread(case.cross, app, text, inputs, self.runs)
        line = " ".join(captions.cross_result(app, x["steps"], x["observe"], x).split())
        if not (self.live and self.live["app"] == app):  # a case opened meanwhile: its judge() owns the ledger
            case.ledger_sink(app, self.runs, self.clock)("cross", {"app": app, **x}, line)
        return line, {"cmd": "cross", "app": app, "match": x["match"], "flaky": x["flaky"], "steps": len(x["steps"])}

    async def chat(self, ctx, sender: str, text: str):
        """commands.COMMANDS['bailiff']; anything else gets the help card."""
        cmd = commands.parse("bailiff", text)
        if cmd.name == "raise" and cmd.arg:
            return await self.raise_case(ctx, cmd.arg, sender, sender, chat=True)
        if cmd.name in ("raise", "apps"):
            apps = case.apps(self.runs)
            return (("Raise what? " if cmd.name == "raise" else "") + captions.docket(apps),
                    {"cmd": cmd.name, "ready": [a for a, why in apps.items() if not why]})
        if cmd.name == "help":
            return captions.help_card("bailiff"), {"cmd": "help", "commands": list(commands.COMMANDS["bailiff"])}
        if self.live:  # the rest read files that judge() may be writing
            return self.busy(cmd.name)
        if cmd.name == "cross":
            return await self.cross(sender, cmd.arg)
        app = self.last_app()
        if not app:
            return captions.no_case(), {"cmd": cmd.name, "ok": False}
        last = case.last_case(app, self.runs)
        if cmd.name == "ledger" and last["events"]:
            n, head = len(last["events"]), last["events"][-1]["hash"]
            return (captions.ledger_line(app, n, last["chain"], head),
                    {"cmd": "ledger", "app": app, "events": n, "chain": last["chain"], "head": head})
        r = last["ruling"]
        if not r:
            return captions.no_case(app), {"cmd": cmd.name, "ok": False, "app": app}
        claim = cmd.arg if cmd.name == "status" else ""
        lock = next((x for x in last["locks"] if x["claim_id"] == claim), {})
        nums = ({"claim": claim, "status": lock.get("status", "")} if claim else
                {k: r[k] for k in ("counts", "fidelity", "catches", "credibility_start", "credibility_end")})
        return captions.status(last, claim), {"cmd": cmd.name, "app": app, "case_id": r["case_id"], **nums}


def build(runs=case.RUNS, clock=None):
    """The uAgent around a Bailiff. Call it inside main(): judge() spawns workers that re-import the main module."""
    agent = base.make_agent("bailiff")
    court = Bailiff(runs, clock)
    agent.include(base.chat_protocol("bailiff", court.chat), publish_manifest=base.flag("SEANCE_MAILBOX"))

    @agent.on_message(OpenCase)
    async def _open(ctx, sender: str, msg: OpenCase):
        await court.on_open(ctx, sender, msg)

    @agent.on_rest_get("/case", CaseView)
    async def _case(ctx):
        return court.snapshot()

    @agent.on_rest_get("/locks", LocksView)
    async def _locks(ctx):
        return court.snapshot()

    return agent


def main(argv=None):
    ap = argparse.ArgumentParser(description="The Bailiff: clerk of the Seance court. No model.")
    ap.add_argument("--mailbox", action="store_true", help="reach Agentverse and ASI:One (same as SEANCE_MAILBOX=1)")
    a = ap.parse_args(argv)
    base.load_env()
    if a.mailbox:
        os.environ["SEANCE_MAILBOX"] = "1"
    for role in ("hoot", "mcclusky"):
        base.address(role)  # a missing party seed fails here, not in the middle of a case
    agent = build()
    print(f"The Bailiff {agent.address} at {base.local_url('bailiff')}; read-only REST: GET /case, GET /locks")
    agent.run()


if __name__ == "__main__":
    main()
