"""Dr. Hoot, the Skeptic: a grumpy owl in round spectacles with a stopwatch. Never impressed. "Hoo."

Attacks come only from P4's deterministic skeptic (case.make_attacks: eval/skeptic.py, restricted to the ids P4
sealed, sealed again with eval/seal.py). No model writes, picks or edits an attack; ASI-1 only does his banter.

Peer messages, from the Bailiff only (anyone else is refused):
  CallSkeptic   -> SealedAttacks  commits and hashes; the steps stay in the envelope
  RequestReveal -> RevealAttacks  the attacks themselves, exactly as sealed
  Ruling        -> remembered     the case he gloats about
  RemarkRequest -> Remark         captions.taunt: deterministic, with the numbers
Chat: help, attacks [app], seal [app], reveal [app] (only after a ruling); anything else is banter.

    agents/mesh/.venv/bin/python -m agents.mesh.hoot [--mailbox]      # port 8783
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from agents.mesh import base, captions, case, commands, voice  # noqa: E402
from agents.mesh.models import (CallSkeptic, Remark, RemarkRequest, RequestReveal, RevealAttacks,  # noqa: E402
                                Ruling, SealedAttacks)

STRANGER = "Dr. Hoot answers only to the Bailiff. Hoo."
STYLE = "You are grumpy, wear round spectacles, carry a stopwatch, and nothing has ever impressed you."


class Hoot:
    """Dr. Hoot's state and handlers; build() puts them on a uAgent."""

    def __init__(self, runs=case.RUNS, bailiff: str = ""):
        self.runs, self.bailiff = pathlib.Path(runs), bailiff  # bailiff: the only address he takes peer messages from
        self.envelope: dict = {}  # the case in progress: case_id, app, attacks (the Bailiff runs one at a time)
        self.last_app = ""

    def _from_bailiff(self, ctx, sender: str, msg) -> bool:
        if sender == self.bailiff:
            return True
        ctx.logger.warning(f"refused {type(msg).__name__} from {sender}: not the Bailiff")
        return False

    # --- the court path ---------------------------------------------------------------------------------------
    async def on_call(self, ctx, sender: str, msg: CallSkeptic):
        """Seal before anyone testifies: commits and hashes leave, the steps stay in the envelope."""
        ids = {"case_id": msg.case_id, "app": msg.app}
        if not self._from_bailiff(ctx, sender, msg):
            return await ctx.send(sender, SealedAttacks(**ids, error=STRANGER))
        try:
            inp = case.load_inputs(msg.app, self.runs)
            attacks = case.make_attacks(msg.app, inp)
            seal = case.seal_attacks(msg.app, attacks, inp)
        except Exception as ex:  # noqa: BLE001 - the Bailiff adjourns on this line instead of waiting out a timeout
            return await ctx.send(sender, SealedAttacks(**ids, error=f"Dr. Hoot cannot seal: {captions.short(ex, 150)}"))
        self.envelope, self.last_app = {**ids, "attacks": attacks}, msg.app
        await ctx.send(sender, SealedAttacks(**ids, seal=seal))

    async def on_reveal(self, ctx, sender: str, msg: RequestReveal):
        """Open the envelope exactly as sealed; the Bailiff checks every attack against its commit."""
        ids = {"case_id": msg.case_id, "app": msg.app}
        if not self._from_bailiff(ctx, sender, msg):
            return await ctx.send(sender, RevealAttacks(**ids, error=STRANGER))
        if (self.envelope.get("case_id"), self.envelope.get("app")) != (msg.case_id, msg.app):
            return await ctx.send(sender, RevealAttacks(**ids, error=f"Dr. Hoot sealed nothing for case {msg.case_id}"))
        await ctx.send(sender, RevealAttacks(**ids, attacks=self.envelope["attacks"]))

    async def on_ruling(self, ctx, sender: str, msg: Ruling):
        if self._from_bailiff(ctx, sender, msg):
            self.last_app = msg.app or self.last_app

    async def on_remark(self, ctx, sender: str, msg: RemarkRequest):
        """The closing taunt: deterministic, the same words as --no-mesh (case.LocalParties)."""
        if self._from_bailiff(ctx, sender, msg):
            await ctx.send(sender, Remark(case_id=msg.case_id, speaker="hoot", text=captions.taunt(msg.ruling)))

    # --- chat ---------------------------------------------------------------------------------------------------
    def _app(self, named: str) -> str:
        """The app a chat command means: the one named, else his last case, else the first app ready to raise."""
        return named or self.last_app or next((a for a, why in case.apps(self.runs).items() if not why), "todo")

    async def chat(self, ctx, sender: str, text: str):
        cmd = commands.parse("hoot", text)
        if cmd.name == "help":
            return captions.help_card("hoot"), {"cmd": "help", "ok": True}
        app = self._app(cmd.arg if cmd.name != "talk" else "")
        if cmd.name == "talk":
            return await self._banter(app, text)
        out = {"cmd": cmd.name, "app": app, "ok": True}
        try:
            inp = case.load_inputs(app, self.runs)
        except case.MissingInput:
            return captions.refusal(app, case.apps(self.runs)), {**out, "ok": False}
        if cmd.name == "reveal":
            last = case.last_case(app, self.runs)
            r = last["ruling"]
            if not r or r.get("error"):
                return captions.reveal_refused(len(case.make_attacks(app, inp))), {**out, "ok": False}
            by = {v["ref"]: v for v in last["verdicts"] if v["kind"] == "attack"}
            rows = [(a["id"], commands.human_steps(inp["selectors"], by[a["id"]]["shrunk_steps"] or a["steps"], 6),
                     by[a["id"]]["original"], by[a["id"]]["revival"]) for a in last["attacks"]
                    if a["id"] in by and not by[a["id"]]["match"] and not by[a["id"]]["flaky"]]
            return captions.reveal_list(app, rows, len(last["attacks"])), {
                **out, "case_id": r["case_id"], "attacks": len(last["attacks"]), "caught": len(rows)}
        attacks = case.make_attacks(app, inp)
        seal = case.seal_attacks(app, attacks, inp)
        out.update(attacks=len(attacks), attacks_sha256=seal["attacks_sha256"])
        if cmd.name == "attacks":
            screens = dict(collections.Counter(a["screen"] for a in attacks))
            sealed_of = len(inp["sealed"]["attacks"]) if inp["sealed"] else 0
            return captions.attacks_line(app, len(attacks), sealed_of, screens), {**out, "screens": screens}
        problems = case.p4_check(app, inp, attacks)[1] if inp["sealed"] else None
        return captions.seal_line(app, seal, problems), {**out, "p4_ok": problems == []}

    async def _banter(self, app: str, text: str):
        """Anything that is not a command: ASI-1 in character, fed only real numbers; a canned roast without it."""
        r = case.last_case(app, self.runs)["ruling"]
        facts = (f"Last case on {app}: {r['counts']['STRUCK']} claims struck, {r['differ']} revival behaviors differ, "
                 f"fidelity {r['fidelity']}, McClusky's credibility {r['credibility_end']}."
                 if r and not r.get("error") else "No ruling on file yet.")
        prompt = (f"{STYLE} Facts, use only these numbers: {facts} Your commands: attacks, seal, reveal; trials "
                  f"start when someone tells McClusky, Esq.: raise {app}. Someone says: \"{captions.short(text, 400)}\". "
                  f"Answer in character.")
        fallback = f"Hoo. {facts} Not impressed. Try: attacks, seal, reveal."
        return await asyncio.to_thread(voice.persona, "hoot", prompt, fallback), {"cmd": "talk", "app": app, "ok": True}


def build(hoot: Hoot | None = None):
    """Dr. Hoot as a uAgent: the four peer handlers plus the chat protocol. Call it inside main()."""
    hoot = hoot or Hoot(bailiff=base.address("bailiff"))
    agent = base.make_agent("hoot")
    for model, handler in ((CallSkeptic, hoot.on_call), (RequestReveal, hoot.on_reveal), (Ruling, hoot.on_ruling),
                           (RemarkRequest, hoot.on_remark)):
        agent.on_message(model)(handler)
    agent.include(base.chat_protocol("hoot", hoot.chat), publish_manifest=base.flag("SEANCE_MAILBOX"))
    return agent


def main(argv=None):
    ap = argparse.ArgumentParser(description="Dr. Hoot, the Seance skeptic (uAgent).")
    ap.add_argument("--mailbox", action="store_true", help="also connect the Agentverse mailbox (SEANCE_MAILBOX=1)")
    if ap.parse_args(argv).mailbox:
        os.environ["SEANCE_MAILBOX"] = "1"
    base.load_env()  # before make_agent reads SEANCE_MAILBOX
    agent = build()
    print(f"{base.NAMES['hoot']} {agent.address} on :{base.PORTS['hoot']}", flush=True)
    agent.run()


if __name__ == "__main__":
    main()
