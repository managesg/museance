"""McClusky, Esq. at handler level: a fake ctx records every send. The runs fixture turns both fakes on."""
import asyncio
import json
import logging
import pathlib
import uuid

import pytest
from uagents_core.contrib.protocols.chat import ChatMessage
from uagents_core.types import DeliveryStatus, MsgStatus

from agents.mesh import captions, case, commands, mcclusky, models
from agents.mesh.models import CallMedium, OpenCase, Progress, Remark, RemarkRequest, Ruling
from court.ledger import commit_hash

BAILIFF, HOOT, USER = "agent1qbailiff", "agent1qhoot", "agent1quser"
MESH_ORDER = ["open", "summon", "sealed", "summon", "testimony", "summon", "reveal", "court", "ruling",
              "remark", "remark", "closed"]


class Ctx:
    """The slice of a uAgents context McClusky uses: sends are recorded, then delivered (or failed)."""

    def __init__(self, status=DeliveryStatus.DELIVERED):
        self.sent, self.status, self.logger, self.session = [], status, logging.getLogger("test"), uuid.uuid4()

    async def send(self, to, msg):
        self.sent.append((to, msg))
        return MsgStatus(status=self.status, detail="connection refused", destination=to, endpoint="")


def chats(ctx, to=USER):
    return [m.text() for t, m in ctx.sent if t == to and isinstance(m, ChatMessage)]


def machine(text):
    return json.loads(text.splitlines()[-1].removeprefix("[seance] "))


def test_testimony_is_the_mediums_cards_with_their_commits(runs):
    mc, ctx = mcclusky.McClusky(BAILIFF, HOOT, runs), Ctx()
    asyncio.run(mc.on_call(ctx, BAILIFF, CallMedium(case_id="app1-t", app="app1")))
    asyncio.run(mc.on_call(ctx, "agent1qimpostor", CallMedium(case_id="app1-t", app="app1")))
    asyncio.run(mc.on_call(ctx, BAILIFF, CallMedium(case_id="pong-t", app="pong")))
    (to, t), (_, err) = ctx.sent  # the impostor got nothing
    assert to == BAILIFF and (t.error, t.dropped) == ("", 0)
    wire = models.Testimony.parse_raw(t.json()).claims  # what the Bailiff receives
    assert [c["id"] for c in wire] == ["c01", "c02", "c03", "c04", "c05"] and wire[4]["label"] == "FABRICATED"
    assert all(c["commit"] == commit_hash(c) for c in wire)
    assert err.case_id == "pong-t" and not err.claims and err.error.startswith("MissingInput: ") and "pong" in err.error


def test_plain_words_raise_tells_the_user_first_then_opens_the_case(runs):
    mc, ctx = mcclusky.McClusky(BAILIFF, HOOT, runs), Ctx()
    assert asyncio.run(mc.chat(ctx, USER, "Can you bring back the app1 app?")) is None
    (to1, hello), (to2, opened) = ctx.sent
    assert to1 == USER and "4 pieces of evidence, a 5-line behavior sheet" in hello.text()
    assert machine(hello.text()) == {"agent": "mcclusky", "cmd": "raise", "app": "app1", "ok": True,
                                     "evidence": 4, "lines": 5}
    assert to2 == BAILIFF and opened == OpenCase(app="app1", requester=USER)
    text, data = asyncio.run(mc.chat(Ctx(DeliveryStatus.FAILED), USER, "raise app1"))
    assert "did not answer (connection refused)" in text and data["ok"] is False


@pytest.mark.parametrize("text,want", [
    ("please resurrect myspace", "cannot raise 'myspace': 0 pieces of evidence"),
    ("raise todo", "todo is on the docket but not ready"),
    ("raise", "Raise what, exactly?"),
])
def test_raise_refuses_apps_without_evidence_and_shows_the_docket(runs, text, want):
    ctx = Ctx()
    reply, data = asyncio.run(mcclusky.McClusky(BAILIFF, HOOT, runs).chat(ctx, USER, text))
    assert want in reply and "app1 (ready)" in reply and (data["ok"], data["ready"]) == (False, ["app1"])
    assert not ctx.sent  # the Bailiff never hears of it


class Wire(case.LocalParties):
    """The Bailiff's mesh parties, in process: McClusky's handlers answer, and replies cross the wire as JSON."""

    def __init__(self, inputs, mc):
        super().__init__(inputs)
        self.mc = mc

    async def _ask(self, handler, msg, reply_type):
        ctx = Ctx()
        await handler(ctx, BAILIFF, msg)
        (to, reply), = ctx.sent
        assert to == BAILIFF
        return reply_type.parse_raw(reply.json())

    async def testify(self, case_id, app):
        t = await self._ask(self.mc.on_call, CallMedium(case_id=case_id, app=app), models.Testimony)
        return t.claims, t.dropped

    async def remark(self, speaker, case_id, app, r, answer=""):
        if speaker == "hoot":
            return await super().remark(speaker, case_id, app, r, answer)
        req = RemarkRequest(case_id=case_id, app=app, ruling=Ruling(**r), answer=answer)
        return (await self._ask(self.mc.on_remark, req, Remark)).text


def test_a_chat_raise_runs_the_case_and_every_hop_reaches_the_user_in_order(runs):
    mc, chat = mcclusky.McClusky(BAILIFF, HOOT, runs), Ctx()
    asyncio.run(mc.chat(chat, USER, "raise app1"))
    opened = chat.sent[-1][1]
    inp, sink = case.load_inputs("app1", runs), case.ledger_sink("app1", runs)

    async def bailiff(type_, payload, caption):  # the Bailiff's on_event: ledger, then Progress to the front door
        sink(type_, payload, caption)
        text = captions.ruling_text(payload) if type_ == "ruling" else caption
        await mc.on_progress(chat, BAILIFF, Progress(case_id=payload["case_id"], app=payload["app"],
                                                     requester=opened.requester, event=type_, text=text))
    asyncio.run(mc.on_progress(chat, "agent1qimpostor", Progress(case_id="x", app="app1", requester=USER,
                                                                 event="open", text="forged")))

    r = asyncio.run(case.hear("app1", Wire(inp, mc), bailiff, requester=USER, runs=runs, inputs=inp))
    said = chats(chat)
    assert [machine(t).get("event") for t in said] == [None, *MESH_ORDER]  # the hello, then one line per hop
    assert "LOCKED 3 | STRUCK 1 | FABRICATED 1 | UNSWORN 0" in said[9] and "Funniest strike: c03" in said[9]
    assert r["remarks"]["mcclusky"] == f"{captions.objection(r)} (Stress meter: 1/10.)"
    assert said[-2].startswith(f"McClusky, Esq.: {captions.objection(r)}")


def test_claims_credibility_and_why_come_from_the_case_on_file(runs):
    mc, ctx = mcclusky.McClusky(BAILIFF, HOOT, runs), Ctx()
    assert asyncio.run(mc.chat(ctx, USER, "credibility")) == (captions.no_case(), {"cmd": "credibility", "ok": False})
    case.run_case("app1", runs=runs, case_id="app1-k")
    out, data = asyncio.run(mc.chat(ctx, USER, "show me the claims"))
    assert "5 claims" in out and "c03 [C, 60%, bond 90] STRUCK" in out and data["claims"] == 5
    out, data = asyncio.run(mc.chat(ctx, USER, "what's my credibility?"))
    assert "1000 -> 963 (-37)" in out and "Stress 1/10" in out
    assert data == {"cmd": "credibility", "app": "app1", "case_id": "app1-k", "credibility": 963, "stress": 1,
                    "fainted": False}
    out, data = asyncio.run(mc.chat(ctx, USER, "why c3"))
    assert out.startswith('c03: "1 / 8 rounds to 0.13"') and "Court: STRUCK" in out and data["status"] == "STRUCK"
    assert "I swore no c09 on app1: my testimony runs 5 claims" in asyncio.run(mc.chat(ctx, USER, "why claim 9"))[0]
    assert not ctx.sent  # commands answer through the chat protocol's reply, nothing else goes out


def test_free_talk_is_told_only_the_case_on_file_and_peers_get_no_chat(runs, monkeypatch):
    case.run_case("app1", runs=runs, case_id="app1-f")
    prompts = []
    monkeypatch.setattr(mcclusky.base, "persona", lambda role, prompt, fallback="": prompts.append(prompt) or "Hoo-ey!")
    mc, ctx = mcclusky.McClusky(BAILIFF, HOOT, runs), Ctx()
    assert asyncio.run(mc.chat(ctx, USER, "Why should anyone trust you?")) == ("Hoo-ey!", {"cmd": "talk"})
    p = prompts[0]
    assert "1000 -> 963, stress 1/10" in p and "c03 STRUCK, 60%, bond 90: 1 / 8 rounds to 0.13" in p
    assert "trial now: app1." in p and p.endswith('"Why should anyone trust you?"')
    assert asyncio.run(mc.chat(ctx, USER, "What is Seance?")) == ("Hoo-ey!", {"cmd": "talk"})  # a question, not a raise
    assert asyncio.run(mc.chat(ctx, HOOT, "Hoo! 90 points, counselor.")) is None and not ctx.sent and len(prompts) == 2


def test_stress_meter_and_the_faint_under_300(runs):
    assert [mcclusky.stress(c) for c in (1200, 1000, 963, 650, 300, 0)] == [0, 0, 1, 5, 10, 10]
    struck = [{"id": "c03", "text": "1 / 8 rounds to 0.13", "expect": "0.13", "original": "0.12", "bond": 90,
               "confidence": 0.6}]
    r = Ruling(case_id="app1-r", app="app1", counts={"LOCKED": 3, "STRUCK": 1, "FABRICATED": 1, "UNSWORN": 0},
               claims=5, attacks=75, catches=3, fidelity=96, credibility_end=963, struck=struck)
    mc, ctx = mcclusky.McClusky(BAILIFF, HOOT, runs), Ctx()
    for ruling in (r, r.copy(update={"credibility_end": 280})):
        asyncio.run(mc.on_remark(ctx, BAILIFF, RemarkRequest(case_id="app1-r", app="app1", ruling=ruling, answer="Hoo")))
    asyncio.run(mc.on_remark(ctx, "agent1qimpostor", RemarkRequest(case_id="x", app="app1", ruling=r)))
    (_, calm), (_, faint) = ctx.sent
    assert calm == Remark(case_id="app1-r", speaker="mcclusky", text=f"{captions.objection(r.dict())} (Stress meter: 1/10.)")
    assert "faints at credibility 280, stress 10/10" in faint.text and "fainted at credibility 280" in mcclusky.meter(280)


def test_readme_lists_every_command_with_its_example():
    text = (pathlib.Path(mcclusky.__file__).parent / "readme" / "mcclusky.md").read_text(encoding="utf-8")
    assert text.startswith("![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)")
    assert "![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)" in text
    for aliases, example, _ in commands.COMMANDS["mcclusky"].values():
        assert f"`{example}`" in text and all(f"`{a}`" in text for a in aliases), example
