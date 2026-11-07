"""Dr. Hoot, the Skeptic: a grumpy owl in round spectacles with a stopwatch. Never impressed. "Hoo."

Attacks come only from P4's deterministic skeptic (case.make_attacks -> eval/skeptic.py, sealed with
eval/seal.py). No model writes, picks or edits an attack; ASI-1 (base.persona) only does his banter.

Peer messages, from the Bailiff only (anyone else is refused):
  CallSkeptic   -> SealedAttacks  commits and hashes; the steps stay in the envelope
  RequestReveal -> RevealAttacks  the attacks themselves, exactly as sealed
  Ruling        -> remembered: the catches he gloats about
  RemarkRequest -> Remark         captions.taunt: one line per STRUCK claim, with the numbers
Chat: help, attacks [app], seal [app], reveal [app] (only after a ruling); anything else is banter.

    agents/mesh/.venv/bin/python agents/mesh/hoot.py             # port 8772, local-only
    agents/mesh/.venv/bin/python agents/mesh/hoot.py --mailbox   # also on the Agentverse mailbox
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # `python agents/mesh/hoot.py` puts agents/mesh/ on sys.path, not the repo root
    sys.path.insert(0, str(ROOT))
from agents.mesh import base, captions, case, commands  # noqa: E402
from agents.mesh.models import (CallSkeptic, Remark, RemarkRequest, RequestReveal, RevealAttacks,  # noqa: E402
                                Ruling, SealedAttacks)

STRANGER = "Dr. Hoot answers only to the Bailiff. Hoo."
STYLE = ("You are grumpy, you wear round spectacles and carry a stopwatch, nothing has ever impressed you, "
         "and you say 'Hoo.' once.")


def scoreboard(r: dict | None) -> str:
    """Dr. Hoot's catches against McClusky's credibility, from a ruling dict (None: nothing ruled yet)."""
    if not r:
        return f"Scoreboard: 0 rulings on file, so McClusky, Esq. still has all {case.START} credibility. For now."
    return (f"Scoreboard, case {r['case_id']}: Dr. Hoot {r['catches']} catches in {r['attacks']} attacks; "
            f"McClusky, Esq. {r['credibility_end']} credibility ({r['credibility_end'] - r['credibility_start']:+d}), "
            f"{r['counts'].get('STRUCK', 0)} STRUCK.")


class Hoot:
    """Dr. Hoot's state and handlers; build() puts them on a uAgent."""

    def __init__(self, runs=case.RUNS, bailiff: str = ""):
        self.runs, self.bailiff = runs, bailiff  # bailiff: the only address he takes peer messages from
        self.envelope: dict = {}  # the case in progress: case_id, app, attacks (the Bailiff runs one at a time)
        self.rulings: dict[str, dict] = {}  # app -> the last Ruling, as a dict
        self.last_app = ""

    def _from_bailiff(self, ctx, sender: str, msg) -> bool:
        if sender == self.bailiff:
            return True
        ctx.logger.warning(f"refused {type(msg).__name__} from {sender}: not the Bailiff")
        return False

    def _remember(self, r: Ruling):
        if not r.error:
            self.rulings[r.app] = r.dict()
        self.last_app = r.app

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
            return await ctx.send(sender, SealedAttacks(**ids, error=f"Dr. Hoot cannot seal: {ex}"))
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
            self._remember(msg)

    async def on_remark(self, ctx, sender: str, msg: RemarkRequest):
        """The closing taunt: deterministic, the same words as --no-mesh (case.LocalParties)."""
        if not self._from_bailiff(ctx, sender, msg):
            return
        self._remember(msg.ruling)  # the ruling rides along, in case its own message was lost
        await ctx.send(sender, Remark(case_id=msg.case_id, speaker="hoot", text=captions.taunt(msg.ruling.dict())))

    # --- chat ---------------------------------------------------------------------------------------------------
    def _app(self, named: str) -> str:
        """The app a chat command means: the one named, else his last case, else the first app ready to raise."""
        return named or self.last_app or next((a for a, why in case.apps(self.runs).items() if not why), "todo")

    async def chat(self, ctx, sender: str, text: str):
        cmd = commands.parse("hoot", text)
        if cmd.name == "help":
            return captions.help_card("hoot"), {"cmd": "help", "ok": True}
        if cmd.name == "talk":
            return await self._banter(self._app(""), text)
        app = self._app(cmd.arg)
        out = {"cmd": cmd.name, "app": app, "ok": True}
        if cmd.name == "reveal":
            last = case.last_case(app, self.runs)
            if last["ruling"]:  # hear() archives the old ledger before a new case, so this ruling is the latest
                r = last["ruling"]
                return (f"{captions.reveal_list(app, last['attacks'], last['verdicts'])}\n{scoreboard(r)}",
                        {**out, "case_id": r["case_id"], "attacks": len(last["attacks"]), "catches": r["catches"]})
        try:
            inp = case.load_inputs(app, self.runs)
        except case.MissingInput:
            return captions.refusal(app, case.apps(self.runs)), {**out, "ok": False}
        attacks = case.make_attacks(app, inp)
        if cmd.name == "reveal":
            return captions.reveal_refused(len(attacks)), {**out, "ok": False, "attacks": len(attacks)}
        seal = case.seal_attacks(app, attacks, inp)
        out.update(attacks=len(attacks), attacks_sha256=seal["attacks_sha256"])
        if cmd.name == "attacks":
            screens = dict(collections.Counter(a["screen"] for a in attacks))
            return captions.attacks_line(app, seal, screens), {**out, "screens": screens}
        p4 = inp["sealed"]
        return captions.seal_line(app, seal, p4), {
            **out, "regression_sha256": seal["regression_sha256"],
            "p4_match": all(seal[k] == p4.get(k) for k in ("attacks_sha256", "regression_sha256"))}

    async def _banter(self, app: str, text: str):
        """Anything that is not a command: ASI-1 in character, fed only real numbers; a canned roast without it."""
        r = self.rulings.get(app) or case.last_case(app, self.runs)["ruling"]
        board = scoreboard(r)
        worst = f" McClusky's worst strike: {r['funniest']}" if r and r.get("funniest") else ""
        prompt = (f"{STYLE} Facts, use only these numbers: {board}{worst} To start a trial, people tell The Bailiff "
                  f"or McClusky, Esq.: raise {app}. Your own commands: attacks, seal, reveal. Someone in the chat "
                  f"says: \"{text[:500]}\". Answer them in character, and roast McClusky, Esq. with one of these "
                  f"numbers when it fits.")
        fallback = (f"Hoo. {board} Not impressed. My commands: attacks, seal, reveal. For a trial, tell The Bailiff: "
                    f"raise {app}.")
        data = {"cmd": "talk", "app": app, "ok": True}
        if r:
            data.update(case_id=r["case_id"], catches=r["catches"], credibility=r["credibility_end"])
        return await asyncio.to_thread(base.persona, "hoot", prompt, fallback), data


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
    ap = argparse.ArgumentParser(description="Dr. Hoot, the Seance skeptic (uAgent on port 8772).")
    ap.add_argument("--mailbox", action="store_true", help="also connect the Agentverse mailbox (SEANCE_MAILBOX=1)")
    if ap.parse_args(argv).mailbox:
        os.environ["SEANCE_MAILBOX"] = "1"
    base.load_env()  # before make_agent reads SEANCE_MAILBOX
    build().run()


if __name__ == "__main__":
    main()
