"""Every uAgents message the Seance mesh sends between our agents (chat users get the Agent Chat Protocol).

Messages route by schema digest (class name + every field + defaults), so all agents import these classes and an
edit here must ship to every agent at once.

A case, in order (sender -> receiver: message, reply):
  front door -> Bailiff     OpenCase       a chat user said "raise <app>" to McClusky (or the Clerk CLI asked)
  Bailiff -> front door     Progress       one per mesh event; McClusky turns at most 4 into status lines
  Bailiff -> Hoot           CallSkeptic    -> SealedAttacks (commits and seal only, no steps yet)
  Bailiff -> McClusky       CallMedium     -> Testimony (claims, each with its commit)
  Bailiff -> Hoot           RequestReveal  -> RevealAttacks (each attack must hash to its sealed commit)
  Bailiff -> Hoot, then McClusky (Hoot's taunt in `answer`):  RemarkRequest -> Remark
  Bailiff -> front door and Hoot:  Ruling (text = McClusky's final chat reply, data = its machine line)
Replies to requests go back in the request's session, so the Bailiff awaits them with ctx.send_and_receive.
Claims and attacks travel as plain dicts (CONTRACTS.md shapes): a typed model would drop fields it does not know,
change the object and break its commit hash.
"""
from uagents import Model


class OpenCase(Model):
    app: str
    requester: str = ""  # the chat user the front door relays for; "" = the front door itself


class Progress(Model):
    case_id: str
    app: str
    requester: str = ""
    event: str  # mesh event type without "mesh.": open, sealed, sworn, revealed, ruling, remark
    text: str  # the event's caption


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


class RemarkRequest(Model):
    case_id: str
    app: str
    ruling: dict = {}  # runs/<app>/ruling.json so far
    answer: str = ""  # the remark to answer (Hoot's taunt, sent to McClusky)


class Remark(Model):
    case_id: str
    speaker: str  # "hoot" or "mcclusky"
    text: str


class Ruling(Model):
    case_id: str
    app: str
    requester: str = ""
    error: str = ""  # set when the case was adjourned
    text: str = ""  # McClusky's final chat reply, without the machine line
    data: dict = {}  # the machine line's fields (case.numbers)
    shots: list[dict] = []  # first mismatches: {ref, original, revival} PNG paths relative to the repo
