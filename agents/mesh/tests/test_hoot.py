import asyncio
import json
import logging
import pathlib

from uagents import Model
from uagents_core.contrib.protocols.chat import ChatAcknowledgement, ChatMessage, TextContent

from agents.mesh import base, captions, case, commands, hoot
from agents.mesh.models import CallSkeptic, RemarkRequest, RequestReveal, RevealAttacks, Ruling
from court.ledger import commit_hash
from eval import skeptic

ROOT = pathlib.Path(__file__).resolve().parents[3]
BAILIFF, STRANGER, USER = "agent1qbailiff", "agent1qstranger", "agent1quser"
STRUCK = [{"id": "c03", "text": "1 / 8 rounds to 0.13", "expect": "0.13", "original": "0.12", "bond": 90,
           "confidence": 0.6}]
R = {"case_id": "app1-r", "app": "app1", "counts": {"LOCKED": 3, "STRUCK": 1, "FABRICATED": 1, "UNSWORN": 0},
     "claims": 5, "attacks": 75, "catches": 9, "fidelity": 86, "brier": 0.173, "credibility_end": 963, "struck": STRUCK}


class Ctx:
    logger = logging.getLogger("test")

    def __init__(self):
        self.sent = []

    async def send(self, to, msg):
        self.sent.append((to, type(msg).parse_raw(msg.json())))  # what the other process reads off the wire


def call(handler, sender, msg):
    ctx = Ctx()
    asyncio.run(handler(ctx, sender, msg))
    return ctx.sent


def test_the_seal_hides_the_steps_and_the_reveal_matches_it(runs):
    h = hoot.Hoot(runs, bailiff=BAILIFF)
    [(to, sealed)] = call(h.on_call, BAILIFF, CallSkeptic(case_id="app1-h", app="app1"))
    p4 = json.loads((ROOT / "cases/app1.commits.json").read_text())
    assert to == BAILIFF and not sealed.error and "steps" not in json.dumps(sealed.seal)
    assert len(sealed.seal["attacks"]) == 75 and sealed.seal["attacks_sha256"] == p4["attacks_sha256"]
    [(_, rev)] = call(h.on_reveal, BAILIFF, RequestReveal(case_id="app1-h", app="app1"))
    assert len(rev.attacks) == 75 and case.verify_reveal(sealed.seal, rev.attacks) == (rev.attacks, [])
    [(_, old)] = call(h.on_reveal, BAILIFF, RequestReveal(case_id="app1-old", app="app1"))
    assert "sealed nothing" in old.error and not old.attacks
    [(_, bad)] = call(h.on_call, BAILIFF, CallSkeptic(case_id="pong-1", app="pong"))
    assert bad.error.startswith("Dr. Hoot cannot seal: pong:") and not bad.seal


def test_todo_attacks_keep_their_commits_on_the_wire():  # emoji, HTML and 500-character tasks
    sel = json.loads((ROOT / "eval/regression/todo-selectors.json").read_text())
    attacks = skeptic.generate("todo", sel)
    back = RevealAttacks.parse_raw(RevealAttacks(case_id="t", app="todo", attacks=attacks).json()).attacks
    assert back == attacks and all(commit_hash(a) == a["commit"] for a in back)


def test_only_the_bailiff_gets_envelopes_rulings_and_remarks(runs):
    h = hoot.Hoot(runs, bailiff=BAILIFF)
    [(_, s)] = call(h.on_call, STRANGER, CallSkeptic(case_id="x", app="app1"))
    assert s.error == hoot.STRANGER and not s.seal and not h.envelope
    call(h.on_call, BAILIFF, CallSkeptic(case_id="x", app="app1"))
    [(_, r)] = call(h.on_reveal, STRANGER, RequestReveal(case_id="x", app="app1"))
    assert r.error == hoot.STRANGER and not r.attacks
    assert call(h.on_remark, STRANGER, RemarkRequest(case_id="x", app="app1", ruling=Ruling(**R))) == []
    call(h.on_ruling, STRANGER, Ruling(**R))
    assert h.rulings == {}


def test_the_remark_is_the_deterministic_taunt_and_the_ruling_is_kept():
    h = hoot.Hoot(bailiff=BAILIFF)
    ruling = Ruling(**R)
    [(to, remark)] = call(h.on_remark, BAILIFF, RemarkRequest(case_id="app1-r", app="app1", ruling=ruling))
    assert (to, remark.speaker, remark.text) == (BAILIFF, "hoot", captions.taunt(ruling.dict()))
    assert "90 points" in remark.text and "9 catches" in remark.text and "963" in remark.text
    call(h.on_ruling, BAILIFF, Ruling(case_id="app1-z", app="app1", error="Dr. Hoot did not answer in 60 s"))
    assert h.rulings["app1"]["catches"] == 9 and h.last_app == "app1"  # an adjourned case keeps the scoreboard


def test_chat_commands_and_banter(runs):
    h = hoot.Hoot(runs, bailiff=BAILIFF)

    def say(text):
        return asyncio.run(h.chat(Ctx(), USER, text))

    assert say("help") == (captions.help_card("hoot"), {"cmd": "help", "ok": True})
    text, data = say("Show attacks")  # no app named: app1 is the only one ready
    assert text.startswith("75 attacks on app1") and data["app"] == "app1" and sum(data["screens"].values()) == 75
    text, data = say("seal for app1")
    assert "matches the seal P4 committed" in text and data["p4_match"]
    assert say("reveal!") == (captions.reveal_refused(75), {"cmd": "reveal", "app": "app1", "ok": False, "attacks": 75})
    text, data = say("attacks pong")
    assert "cannot raise 'pong'" in text and "app1 (ready)" in text and not data["ok"]
    text, data = say("you are a bad owl")  # SEANCE_FAKE_LLM=1: the canned roast
    assert text.startswith("Hoo. Scoreboard: 0 rulings") and data == {"cmd": "talk", "app": "app1", "ok": True}

    r = case.run_case("app1", runs=runs, case_id="app1-c")
    text, data = say("reveal app1")
    assert text.startswith(f"Revealed for app1: 75 attacks, {r['catches']} caught the revival.")
    assert text.splitlines()[-1] == hoot.scoreboard(r) and (data["case_id"], data["catches"]) == ("app1-c", r["catches"])
    text, data = say("who is winning?")
    assert f"Dr. Hoot {r['catches']} catches in 75 attacks" in text and "963 credibility (-37)" in text
    assert (data["catches"], data["credibility"]) == (r["catches"], 963)


def test_a_chat_reply_ends_with_one_machine_line(runs):
    on_chat = base.chat_protocol("hoot", hoot.Hoot(runs, bailiff=BAILIFF).chat).signed_message_handlers[
        Model.build_schema_digest(ChatMessage)]
    ctx = Ctx()
    asyncio.run(on_chat(ctx, USER, ChatMessage(content=[TextContent(text="seal")])))
    (_, ack), (_, reply) = ctx.sent
    *body, line = reply.text().splitlines()
    assert isinstance(ack, ChatAcknowledgement) and not any("[seance]" in b for b in body)
    assert json.loads(line.removeprefix("[seance] "))["p4_match"] is True


def test_build_wires_the_peer_handlers_and_chat(monkeypatch):
    for role in ("hoot", "bailiff"):
        monkeypatch.setenv(f"{role.upper()}_SEED", f"unit test seed {role} 0001")
    agent = hoot.build()
    try:
        agent.include(agent._protocol)  # what Agent.setup() does at run time; it refuses a duplicate model
        want = (CallSkeptic, RequestReveal, Ruling, RemarkRequest, ChatMessage, ChatAcknowledgement)
        assert {Model.build_schema_digest(m) for m in want} <= set(agent._signed_message_handlers)
    finally:
        agent._loop.close()
        asyncio.set_event_loop(None)


def test_readme_lists_the_exact_commands():
    md = (ROOT / "agents/mesh/readme/hoot.md").read_text()
    assert "![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)" in md
    assert "![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)" in md and "<HOOT_ADDRESS>" in md
    for name, (aliases, example, what) in commands.COMMANDS["hoot"].items():
        assert f"`{example}`" in md and what in md and all(f"`{a}`" in md for a in aliases), name
