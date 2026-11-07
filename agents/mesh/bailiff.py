"""The Bailiff: clerk of the Seance court and orchestrator of every case. No model anywhere in this process.

    agents/mesh/.venv/bin/python -m agents.mesh.bailiff [--mailbox]

A case opens on OpenCase (McClusky relaying a chat user, or the Clerk) or on "raise <app>" in chat. The Bailiff
runs it through Dr. Hoot and McClusky over the mesh (case.hear with MeshParties): seal, testimony, reveal (every
attack checked against its seal and P4's), then judge() in this process, so during a case this process is the
only writer of runs/<app>/ledger.jsonl. Each mesh event goes out as a Progress to the front door; at the end the
Ruling (McClusky's final chat reply, rendered here without a model) goes to the front door and Dr. Hoot.
Chat: help, status [claim], transcript, case, apps, raise <app>, cross <expr>. Read-only REST: GET /case, /locks.
"""
from __future__ import annotations

import argparse
import asyncio
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

SEAL_S, TESTIFY_S, REMARK_S = 60, 240, 60  # testimony may wait on P2's reader and Medium (180 s each, cached)


class CaseView(Model):
    """GET /case: the case in session, else the last one on file."""
    app: str = ""
    case_id: str = ""
    in_session: bool = False
    event: str = ""  # the last mesh event on the record
    caption: str = ""
    ruling: dict = {}


class LocksView(Model):
    """GET /locks: that case's lock table, [] until the court rules."""
    app: str = ""
    case_id: str = ""
    in_session: bool = False
    locks: list[dict] = []


class MeshParties:
    """case.hear's four parties over the mesh. send_and_receive only accepts a reply from the address it asked,
    in this session, so every reply's sender is checked against base.address(role) by construction."""

    def __init__(self, ctx):
        self.ctx = ctx

    async def _ask(self, role: str, msg, reply_type, timeout: int):
        reply, status = await self.ctx.send_and_receive(base.address(role), msg, reply_type, timeout=timeout)
        who = captions.NAMES[role]
        if reply is None:
            raise case.CaseError(f"{who} did not answer ({status.detail})")
        if getattr(reply, "error", ""):
            raise case.CaseError(f"{who}: {reply.error}")
        if reply.case_id != msg.case_id:  # a late answer to an earlier case in the same session
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
        msg = RemarkRequest(case_id=case_id, app=app, ruling=r, answer=answer)
        return (await self._ask(speaker, msg, Remark, REMARK_S)).text


def ruling_message(r: dict, requester: str = "") -> Ruling:
    return Ruling(case_id=r["case_id"], app=r["app"], requester=requester, error=r.get("error", ""),
                  text=captions.final_reply(r), data={"cmd": "raise", **case.numbers(r)}, shots=r.get("shots", []))


class Bailiff:
    """The court's state and handlers, apart from uAgents so tests can drive them with a fake ctx."""

    def __init__(self, runs=case.RUNS, clock=None):
        self.runs, self.clock = pathlib.Path(runs), clock
        self.app = ""  # the app of the case in session, or of the last case raised here
        self.live = None  # the case in session: {app, case_id, event, caption}
        self.rate = base.RateLimit(10)

    def last_app(self) -> str:
        if self.app:
            return self.app
        done = sorted(self.runs.glob("*/ruling.json"), key=lambda p: p.stat().st_mtime)
        return done[-1].parent.name if done else ""

    def snapshot(self) -> dict:
        """What GET /case and GET /locks serve."""
        if self.live:
            return {**self.live, "in_session": True}
        app = self.last_app()
        if not app:
            return {}
        last = case.last_case(app, self.runs)
        r = last["ruling"] or {}
        mesh = [e for e in last["events"] if e["type"].startswith("mesh.")]
        return {"app": app, "case_id": r.get("case_id", ""), "event": mesh[-1]["type"][5:] if mesh else "",
                "caption": mesh[-1]["payload"].get("caption", "") if mesh else "",
                "ruling": {k: v for k, v in r.items() if k not in ("case_file",)}, "locks": last["locks"]}

    def busy(self, cmd: str) -> tuple[str, dict]:
        live = self.live
        return (f"{captions.busy(live['case_id'], live['app'])}\n\nOn the record: {live['caption'] or 'All rise.'}",
                {"cmd": cmd, "ok": False, "busy": live["case_id"], "event": live["event"]})

    async def raise_case(self, ctx, app: str, sender: str, requester: str = "", chat: bool = False):
        """One whole case. sender is the front door (an agent that sent OpenCase) or, with chat=True, the chat
        user. -> the final reply (chat=True), None once the Ruling went out, or a refusal as (text, data)."""
        if self.live:
            return self.busy("raise")
        try:
            inputs = case.load_inputs(app, self.runs)
        except case.MissingInput:
            return captions.refusal(app, case.apps(self.runs)), {"cmd": "raise", "ok": False, "app": app}
        sink, case_id = case.ledger_sink(app, self.runs, self.clock), case.new_case_id(app)
        self.app, self.live = app, {"app": app, "case_id": case_id, "event": "", "caption": ""}

        async def on_event(event: str, payload: dict):
            sink(event, payload)
            self.live.update(event=event, caption=payload["caption"])
            if not chat:
                await ctx.send(sender, Progress(case_id=case_id, app=app, requester=requester, event=event,
                                                text=payload["caption"]))

        async def progress(line: str):
            if chat:
                await base.send_text(ctx, sender, "bailiff", line, cmd="raise", app=app, case_id=case_id, ok=True)

        try:
            r = await case.hear(app, MeshParties(ctx), on_event, case_id=case_id, requested_by=requester or sender,
                                runs=self.runs, clock=self.clock, inputs=inputs, progress=progress)
        finally:
            self.live = None
        msg = ruling_message(r, requester)
        for to in dict.fromkeys(([] if chat else [sender]) + [base.address("hoot")]):
            await ctx.send(to, msg)
        return (msg.text, msg.data) if chat else None

    async def on_open(self, ctx, sender: str, msg: OpenCase):
        out = await self.raise_case(ctx, msg.app, sender, msg.requester)
        if out:  # refused: a Ruling with the reason, so the front door stops waiting
            text, data = out
            await ctx.send(sender, Ruling(case_id="", app=msg.app, requester=msg.requester, error=text, text=text,
                                          data=data))

    async def cross(self, sender: str, text: str) -> tuple[str, dict]:
        """The sender's own attack (known selectors only, at most 30 steps), on both builds through court.court.rule.
        An optional app id comes first ("cross todo add Buy milk"). Logged as mesh.cross, never as a verdict."""
        apps = case.apps(self.runs)
        first, _, rest = text.partition(" ")
        app, text = (first.lower(), rest) if first.lower() in apps else (self.last_app() or "todo", text)
        try:
            inputs = case.load_inputs(app, self.runs)
            steps, _ = commands.to_steps(inputs["selectors"], text)  # refuse before the 10 s slot is taken
        except case.MissingInput:
            return captions.refusal(app, apps), {"cmd": "cross", "ok": False, "app": app}
        except commands.CrossError as ex:
            return captions.cross_refused(f"on {app}, {ex}"), {"cmd": "cross", "ok": False, "app": app}
        left = self.rate.wait(sender)
        if left:
            return captions.rate_limited(left), {"cmd": "cross", "ok": False, "wait": round(left)}
        x = await asyncio.to_thread(case.cross, app, text, inputs, self.runs)
        human = commands.human_steps(inputs["selectors"], x["shrunk_steps"] or x["steps"])
        verdict = "flaky" if x["flaky"] else "match" if x["match"] else "differ"
        payload = {"who": sender, "steps": x["steps"], "verdict": verdict}
        line = captions.caption("cross", payload, steps=commands.human_steps(inputs["selectors"], x["steps"]),
                                original=x["original"], revival=x["revival"])
        if not self.live:  # a case opened meanwhile: its judge() owns the ledger
            case.ledger_sink(app, self.runs, self.clock)("cross", {**payload, "agent": "bailiff", "caption": line})
        return (captions.cross_result(app, human, x),
                {"cmd": "cross", "app": app, "verdict": verdict, "steps": len(x["steps"])})

    async def chat(self, ctx, sender: str, text: str):
        """commands.COMMANDS['bailiff']; anything else gets the help card."""
        cmd = commands.parse("bailiff", text)
        if cmd.name == "help":
            return captions.help_card("bailiff"), {"cmd": "help", "commands": list(commands.COMMANDS["bailiff"])}
        if cmd.name in ("raise", "apps") and not (cmd.name == "raise" and cmd.arg):
            apps = case.apps(self.runs)
            return (("Raise what? " if cmd.name == "raise" else "") + captions.docket(apps),
                    {"cmd": cmd.name, "ready": [a for a, why in apps.items() if not why]})
        if self.live:  # a case is in session: no second case, no cross, and judge() owns the files
            return self.busy(cmd.name)
        if cmd.name == "raise":
            return await self.raise_case(ctx, cmd.arg, sender, sender, chat=True)
        if cmd.name == "cross":
            return await self.cross(sender, cmd.arg)
        app = self.last_app()
        last = case.last_case(app, self.runs) if app else {"ruling": None, "events": [], "ledger": {}}
        if cmd.name == "transcript":
            return (captions.transcript(last["events"], last["ledger"]),
                    {"cmd": "transcript", "app": app, "ledger": last["ledger"].get("entries", 0),
                     "chain": last["ledger"].get("ok", False)})
        r = last["ruling"]
        if not r:
            return captions.no_case(app), {"cmd": cmd.name, "ok": False, "app": app}
        if cmd.name == "status" and cmd.arg:
            c = next((c for c in last["claims"] if c["id"] == cmd.arg), None)
            lock = next((x for x in last["locks"] if x["claim_id"] == cmd.arg), None)
            return (captions.claim_status(r, c, lock, cmd.arg),
                    {"cmd": "status", "app": app, "claim": cmd.arg, "status": lock["status"] if lock else ""})
        text = captions.case_text(r) if cmd.name == "case" else captions.status_text(r)
        return text, {"cmd": cmd.name, **case.numbers(r)}


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
    print(f"{base.NAMES['bailiff']} {agent.address} on :{base.PORTS['bailiff']}; read-only REST: GET /case, GET /locks",
          flush=True)
    agent.run()


if __name__ == "__main__":
    main()
