"""The Bailiff: clerk of the Seance court and orchestrator of every case. No model anywhere in this process.

    agents/mesh/.venv/bin/python -m agents.mesh.bailiff [--mailbox]

A case opens on OpenCase (McClusky relaying a chat user, or the Clerk) or on "raise <app>" in chat. The Bailiff
runs it through Dr. Hoot and McClusky over the mesh (case.hear with MeshParties): seal, testimony, reveal (every
attack checked against its seal and P4's), then judge() in this process, so during a case this process is the
only writer of runs/<app>/ledger.jsonl. Each mesh event goes out as a Progress to the front door; at the end the
Ruling (McClusky's final chat reply, rendered here without a model) goes to the front door and Dr. Hoot.
Chat: the courtroom (courtroom.respond: the judge picks from three choices, the Bailiff answers in plain words), plus
the old commands status [claim], transcript, apps, raise <app>, cross <expr>. Read-only REST: GET /case, /locks.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from uagents import Model  # noqa: E402

from agents.mesh import base, captions, case, commands, courtroom  # noqa: E402
from agents.mesh.models import (CallMedium, CallSkeptic, OpenCase, Progress, Remark, RemarkRequest,  # noqa: E402
                                RequestReveal, RevealAttacks, Ruling, SealedAttacks, Testimony)

SEAL_S, TESTIFY_S, REMARK_S = 60, 240, 60  # testimony may wait on P2's reader and Medium (180 s each, cached)
TITLES = {"todo": "Todo", "app1": "the Calculator"}  # courtroom.CASES
FRESH_S = 90  # a case another judge finished this recently is the same evidence: reuse it, don't queue a rerun
OPENING = "🔨 All rise. The court is testing the original and the revival now, Your Honor."
ROUTED = {"raise", "cross", "transcript", "status", "case", "apps"}  # old commands that skip the courtroom


def summary(r: dict, runs=case.RUNS) -> dict:
    """courtroom.respond's case summary. Every field comes from the case files on disk, nothing is made up."""
    d = pathlib.Path(runs) / r["app"]
    verdicts, claims, attacks, locks = (json.loads((d / f"{n}.json").read_text())
                                        for n in ("verdicts", "claims", "attacks", "locks"))
    selectors = case.load_inputs(r["app"], runs)["selectors"]
    items = {("claim", c["id"]): c for c in claims} | {("attack", a["id"]): a for a in attacks}
    status = {x["claim_id"]: x["status"] for x in locks}

    def exhibit(v):
        it = items[(v["kind"], v["ref"])]
        steps = v.get("shrunk_steps") or (it["test"]["steps"] if v["kind"] == "claim" else it["steps"])
        return {"did": commands.human_steps(selectors, steps, limit=6),
                "original": captions.shown(v["original"]), "revival": captions.shown(v["revival"])}

    live = [v for v in verdicts if not v["flaky"]]
    held = sorted((v for v in live if v["match"] and status.get(v["ref"]) == "LOCKED"),
                  key=lambda v: -items[("claim", v["ref"])].get("bond", 0))

    def struck(s):
        seen = "nothing" if str(s["original"]).startswith("ERROR:observe") else f'"{captions.shown(s["original"], 10)}"'
        return f'"{s["text"].split("(")[0].split(":")[0].strip()}": McClusky swore it, the original shows {seen}.'

    c = r["counts"]
    return {"app": r["app"], "title": TITLES.get(r["app"], r["app"]), "claims": r["claims"],
            "locked": c["LOCKED"], "struck": c["STRUCK"], "unsworn": c["UNSWORN"], "fabricated": c["FABRICATED"],
            "attacks": r["attacks"], "seconds": r["seconds"]["court"], "fidelity": r["fidelity"],
            "differences": [exhibit(v) for v in live if not v["match"]], "examples": [exhibit(v) for v in held[:3]],
            "struck_examples": [struck(s) for s in r["struck"]],
            "credibility": [r["credibility_start"], r["credibility_end"]],
            "argument": [{"who": w, "line": r["remarks"][w]} for w in ("hoot", "mcclusky") if r["remarks"].get(w)],
            "ledger": {"intact": r["ledger"]["ok"]}}


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
        self.judges: dict[str, dict | None] = {}  # courtroom state per judge (sender:session)
        self.turns: dict[str, asyncio.Lock] = {}  # one courtroom turn at a time per judge
        self.case_lock = asyncio.Lock()  # one courtroom case at a time across judges

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

    async def raise_case(self, ctx, app: str, sender: str, requester: str = "", chat: bool = False, quiet=False):
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
            if chat and not quiet:  # quiet: the courtroom says one line before the case, not one per step
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
        x, verdict = await asyncio.to_thread(self._cross_core, sender, app, text, inputs)
        human = commands.human_steps(inputs["selectors"], x["shrunk_steps"] or x["steps"])
        return (captions.cross_result(app, human, x),
                {"cmd": "cross", "app": app, "verdict": verdict, "steps": len(x["steps"])})

    def _cross_core(self, sender: str, app: str, text: str, inputs: dict) -> tuple[dict, str]:
        """Blocking (a real browser on both builds). Logged as mesh.cross, never as a verdict."""
        x = case.cross(app, text, inputs, self.runs)
        verdict = "flaky" if x["flaky"] else "match" if x["match"] else "differ"
        payload = {"who": sender, "steps": x["steps"], "verdict": verdict}
        line = captions.caption("cross", payload, steps=commands.human_steps(inputs["selectors"], x["steps"]),
                                original=x["original"], revival=x["revival"])
        if not self.live:  # a case opened meanwhile: its judge() owns the ledger
            case.ledger_sink(app, self.runs, self.clock)("cross", {**payload, "agent": "bailiff", "caption": line})
        return x, verdict

    # --- the courtroom: what judges see in ASI:One ------------------------------------------------------------
    def judge_cross(self, sender: str, app: str, raw: str) -> dict:
        """courtroom's run_cross (worker thread): the judge's own test on both builds. ValueError = plain words."""
        inputs = case.load_inputs(app, self.runs)
        try:
            commands.to_steps(inputs["selectors"], raw)
        except commands.CrossError as ex:  # the parser's own words are for engineers
            raise ValueError(f'The court can\'t try that. Try something like "{courtroom.EXAMPLES[app]}".') from ex
        left = self.rate.wait(sender)
        if left:
            raise ValueError(f"One test every 10 seconds, Your Honor. Wait {round(left)} more.")
        x, _ = self._cross_core(sender, app, raw, inputs)  # during another case it runs, off the record
        return {"did": commands.human_steps(inputs["selectors"], x["steps"]),
                "original": captions.shown(x["original"]), "revival": captions.shown(x["revival"])}

    async def case_summary(self, ctx, sender: str, app: str) -> dict:
        """courtroom's run_case: a real case on both builds, one at a time across judges. A judge who waited on
        another judge's case of the same app gets that one (finished seconds ago, same evidence)."""
        ruling = self.runs / app / "ruling.json"
        async with self.case_lock:
            if not (ruling.exists() and time.time() - ruling.stat().st_mtime < FRESH_S):
                await base.send_text(ctx, sender, "bailiff", OPENING, cmd="court", app=app)
                while self.live:  # a case McClusky opened is still in session
                    await asyncio.sleep(1)
                text, data = await self.raise_case(ctx, app, sender, sender, chat=True, quiet=True)
                if data.get("ok") is False:
                    raise case.CaseError(text)
        r = case.last_case(app, self.runs)["ruling"]
        if not r or r.get("error"):
            raise case.CaseError((r or {}).get("error") or "The case file is missing.")
        return summary(r, self.runs)

    async def debate(self, ctx, app: str) -> list[dict]:
        """Hear them argue, live over the mesh: Hoot taunts, McClusky answers him (ASI-1), Hoot rebuts (ASI-1).
        The Bailiff only relays (no model here); every remark goes on the record as mesh.remark."""
        r = case.last_case(app, self.runs)["ruling"]
        sink = None if self.live else case.ledger_sink(app, self.runs, self.clock)  # a case in session owns it
        parties, said, answer = MeshParties(ctx), [], ""
        for who in ("hoot", "mcclusky", "hoot"):
            answer = await parties.remark(who, r["case_id"], app, r, answer)
            said.append({"who": who, "line": answer})
            if sink:
                p = {"from": who, "text": answer}
                sink("remark", {**p, "agent": who, "caption": captions.caption("remark", p)})
        c = r["counts"]
        return said + [{"who": "bailiff", "line": f"{c['LOCKED']} locked, {c['STRUCK']} struck, {r['differ']} "
                                                  f"differences. The Bailiff has no opinion."}]

    async def court_chat(self, ctx, sender: str, text: str):
        """The chat judges get: courtroom.respond (at most three choices, plain words). respond is plain code, so
        it runs in a worker thread and reaches the mesh (cases, debates) back on this loop."""
        if text.split()[:1] and text.split()[0].lower() in ROUTED:
            return await self.chat(ctx, sender, text)
        key, loop = f"{sender}:{ctx.session}", asyncio.get_running_loop()

        def on_loop(coro):
            return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=300)

        async with self.turns.setdefault(key, asyncio.Lock()):
            reply, state = await asyncio.to_thread(
                courtroom.respond, self.judges.get(key), text,
                run_case=lambda app: on_loop(self.case_summary(ctx, sender, app)),
                run_cross=lambda app, raw: self.judge_cross(sender, app, raw),
                run_argue=lambda app: on_loop(self.debate(ctx, app)))
            self.judges[key] = state
        return reply, {"cmd": "court", "stage": (state or {}).get("stage", "adjourned")}

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
    agent.include(base.chat_protocol("bailiff", court.court_chat), publish_manifest=base.flag("SEANCE_MAILBOX"))

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
