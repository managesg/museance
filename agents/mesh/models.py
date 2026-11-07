"""Every uAgents message the Seance mesh sends. Final: stage 2 must not change it.

Messages route by schema digest (class name + every field + defaults), so all agents import these classes
and an edit here must ship to every agent at once.

A case, in order (sender -> receiver: message, reply):
  front door -> Bailiff     OpenCase       a chat user said "raise <app>". Front door = the envelope sender:
                                           McClusky (relaying for a chat user), the Clerk CLI, or any agent.
  Bailiff -> front door     Progress       one per hop; `text` is the one-line caption, ready for chat.
                                           The last one of every case has event "closed" or "adjourned".
  Bailiff -> Hoot           CallSkeptic    -> SealedAttacks (commits and seal only, no steps yet)
  Bailiff -> McClusky       CallMedium     -> Testimony (claims, each with its commit)
  Bailiff -> Hoot           RequestReveal  -> RevealAttacks (each attack must hash to its sealed commit)
  Bailiff -> McClusky, Hoot, and the front door when it is another agent:  Ruling
  Bailiff -> Hoot, then McClusky (with Hoot's taunt in `answer`):  RemarkRequest -> Remark
Replies go back in the request's session, so the Bailiff can await them with ctx.send_and_receive.
Claims and attacks travel as plain dicts (CONTRACTS.md shapes): a typed model would drop fields it does
not know, change the object and break its commit hash.
"""
from uagents import Model


class OpenCase(Model):
    app: str
    requester: str = ""  # the chat user the front door relays for; "" = the front door itself


class Progress(Model):
    case_id: str
    app: str
    requester: str = ""  # echoed from OpenCase so the front door knows whose chat to relay to
    event: str  # mesh event type without "mesh.": open, summon, sealed, ..., closed, adjourned
    text: str  # caption, one line (the ruling: a few lines)
    data: dict = {}  # small payload for the [seance] machine line


class CallSkeptic(Model):
    case_id: str
    app: str


class SealedAttacks(Model):
    case_id: str
    app: str
    seal: dict = {}  # eval.seal.seal() shape: app, created_utc, regression_sha256, attacks [{id, commit}], attacks_sha256
    error: str = ""


class CallMedium(Model):
    case_id: str
    app: str


class Testimony(Model):
    case_id: str
    app: str
    claims: list[dict] = []  # CONTRACTS.md claim objects, each with commit
    dropped: int = 0  # cards the Medium wrote that broke the contract
    error: str = ""


class RequestReveal(Model):
    case_id: str
    app: str


class RevealAttacks(Model):
    case_id: str
    app: str
    attacks: list[dict] = []  # CONTRACTS.md attack objects, each with commit
    error: str = ""


class Ruling(Model):
    case_id: str
    app: str
    requester: str = ""
    error: str = ""  # set when the case was adjourned; the numbers below are then empty
    counts: dict[str, int] = {}  # LOCKED, STRUCK, FABRICATED, UNSWORN
    claims: int = 0
    attacks: int = 0  # attacks the court ran
    refused: int = 0  # attacks thrown out at reveal (content no longer matched the sealed commit)
    catches: int = 0  # attacks where original and revival disagreed (not flaky): Hoot's score
    fidelity: int = 0
    brier: float = 0.0
    credibility_start: int = 1000
    credibility_end: int = 1000  # McClusky's score
    struck: list[dict] = []  # per STRUCK claim: id, text, expect, original, bond, confidence
    funniest: str = ""  # the most overconfident STRUCK claim, as one line
    chain: str = ""  # court.ledger.verify() message after the court ruled
    text: str = ""  # chat-ready summary


class RemarkRequest(Model):
    case_id: str
    app: str
    ruling: Ruling
    answer: str = ""  # the remark to answer (Hoot's taunt, sent to McClusky)


class Remark(Model):
    case_id: str
    speaker: str  # "hoot" or "mcclusky"
    text: str
