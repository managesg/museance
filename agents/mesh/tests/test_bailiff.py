import ast
import asyncio
import json
import logging
import pathlib
import urllib.request
import uuid

import pytest
from uagents import Model
from uagents.asgi import RESERVED_ENDPOINTS
from uagents_core.contrib.protocols.chat import ChatMessage
from uagents_core.types import DeliveryStatus, MsgStatus

from agents.mesh import bailiff, base, captions, case, commands, models
from agents.mesh.models import (CallMedium, CallSkeptic, OpenCase, Progress, Remark, RemarkRequest, RequestReveal,
                                RevealAttacks, Ruling, SealedAttacks)
from court.ledger import read, verify

MESH = pathlib.Path(bailiff.__file__).parent
CLOCK = lambda: "2026-11-07T21:00:00+00:00"  # noqa: E731
SEEDS = {"MCCLUSKY_SEED": "unit test seed mcclusky 0001", "HOOT_SEED": "unit test seed hoot 0001",
         "BAILIFF_SEED": "unit test seed bailiff 0001"}
ORDER = ["open", "summon", "sealed", "summon", "testimony", "summon", "reveal", "court", "ruling", "remark", "remark",
         "closed"]
APP1 = {"LOCKED": 3, "STRUCK": 1, "FABRICATED": 1, "UNSWORN": 0}
USER, OTHER, CLERK = "agent1quser", "agent1qother", "agent1qclerk"


@pytest.fixture
def the_bailiff(runs, monkeypatch):
    """A Bailiff on app1 (both fakes on), with every way this process could reach a model wired to explode."""
    for k, v in SEEDS.items():
        monkeypatch.setenv(k, v)

    def boom(*a, **k):
        raise AssertionError("the Bailiff reached for a model")
    for mod, name in ((base, "persona"), (case, "objection"), (urllib.request, "urlopen")):
        monkeypatch.setattr(mod, name, boom)
    return bailiff.Bailiff(runs, clock=CLOCK)


def status(ok=True):
    return MsgStatus(status=DeliveryStatus.DELIVERED if ok else DeliveryStatus.FAILED,
                     detail="delivered" if ok else "Timeout waiting for response", destination="", endpoint="",
                     session=uuid.uuid4())


class Mesh:
    """A fake ctx. send records what leaves, as the other process reads it off the wire; send_and_receive answers
    the way Dr. Hoot and McClusky do, from the lanes' own code. tamper: Hoot edits an attack after the seal.
    mute: that party never answers. watch: a Bailiff whose snapshot is taken at every Progress."""
    logger = logging.getLogger("test")

    def __init__(self, runs, tamper=False, mute="", watch=None):
        self.inputs, self.tamper, self.mute, self.watch = case.load_inputs("app1", runs), tamper, mute, watch
        self.sent, self.attacks, self.snaps = [], [], {}

    async def send(self, to, msg):
        self.sent.append((to, type(msg).parse_raw(msg.json())))
        if self.watch and isinstance(msg, Progress):
            self.snaps[msg.event] = self.watch.snapshot()
        return status()

    async def send_and_receive(self, to, msg, response_type, sync=False, timeout=30):
        self.sent.append((to, msg))
        role = {base.address("hoot"): "hoot", base.address("mcclusky"): "mcclusky"}[to]
        if role == self.mute:
            return None, status(ok=False)
        ids = {"case_id": msg.case_id, "app": msg.app}
        if isinstance(msg, CallSkeptic):
            self.attacks = case.make_attacks(msg.app, self.inputs)
            reply = SealedAttacks(**ids, seal=case.seal_attacks(msg.app, self.attacks, self.inputs))
        elif isinstance(msg, CallMedium):
            claims, dropped = case.make_claims(msg.app, self.inputs)  # SEANCE_FAKE_LLM=1: fixtures/claims.json
            reply = models.Testimony(**ids, claims=claims, dropped=len(dropped))  # Test* names confuse pytest
        elif isinstance(msg, RequestReveal):
            attacks = [dict(a) for a in self.attacks]
            if self.tamper:
                attacks[0]["steps"] = attacks[0]["steps"] + ["click:#k7"]
            reply = RevealAttacks(**ids, attacks=attacks)
        else:
            reply = Remark(case_id=msg.case_id, speaker=role, text=f"{role}: {msg.ruling.counts['STRUCK']} struck")
        assert isinstance(reply, response_type)
        return response_type.parse_raw(reply.json()), status()

    def of(self, kind):
        return [(to, m) for to, m in self.sent if isinstance(m, kind)]


def test_a_case_raised_through_mcclusky(the_bailiff, runs):
    mesh, mc, hoot = Mesh(runs, watch=the_bailiff), base.address("mcclusky"), base.address("hoot")
    asyncio.run(the_bailiff.on_open(mesh, mc, OpenCase(app="app1", requester=USER)))
    progress = [m for _, m in mesh.of(Progress)]
    assert [p.event for p in progress] == ORDER
    assert {to for to, _ in mesh.of(Progress)} == {mc} and {p.requester for p in progress} == {USER}
    assert [to for to, _ in mesh.of(Ruling)] == [mc, hoot]  # the front door is McClusky: one copy each
    r = mesh.of(Ruling)[0][1]
    assert (r.counts, r.requester, r.refused, r.error, r.credibility_end) == (APP1, USER, 0, "", 963)
    assert progress[ORDER.index("ruling")].text == r.text and "Funniest strike: c03" in r.text
    assert progress[-1].data == {"event": "closed", "case_id": r.case_id, "app": "app1", "counts": APP1,
                                 "catches": r.catches, "attacks": 75, "credibility_start": 1000, "credibility_end": 963}
    (h, hoot_req), (m, mc_req) = mesh.of(RemarkRequest)
    assert (h, m, hoot_req.answer, mc_req.answer) == (hoot, mc, "", "hoot: 1 struck")
    assert mc_req.ruling.counts == APP1

    path = runs / "app1" / "ledger.jsonl"
    hops = [e for e in read(path) if e["type"].startswith("mesh.")]
    assert verify(path)[0] and [e["type"][5:] for e in hops] == ORDER
    for e in hops:
        assert e["payload"]["caption"] == captions.caption(e["type"][5:], {k: v for k, v in e["payload"].items()
                                                                           if k != "caption"})
    assert [e["payload"]["text"] for e in hops if e["type"] == "mesh.remark"] == ["hoot: 1 struck", "mcclusky: 1 struck"]

    court, ruled = mesh.snaps["court"], mesh.snaps["ruling"]  # in session: from memory, no locks until the ruling
    assert court["in_session"] and court["locks"] == [] and court["case_id"] == r.case_id
    assert [x["status"] for x in ruled["locks"]] == ["LOCKED", "LOCKED", "STRUCK", "LOCKED", "FABRICATED"]
    idle = bailiff.CaseView.parse_obj(the_bailiff.snapshot())
    assert the_bailiff.live is None and (idle.in_session, idle.event, idle.case_id) == (False, "closed", r.case_id)


def test_a_forged_attack_is_thrown_out_and_the_clerk_gets_the_ruling(the_bailiff, runs):
    mesh = Mesh(runs, tamper=True)
    asyncio.run(the_bailiff.on_open(mesh, CLERK, OpenCase(app="app1")))
    assert [to for to, _ in mesh.of(Ruling)] == [base.address("mcclusky"), base.address("hoot"), CLERK]
    r = mesh.of(Ruling)[0][1]
    assert (r.refused, r.attacks) == (1, 74)
    reveal = next(m for _, m in mesh.of(Progress) if m.event == "reveal")
    assert reveal.data["refused"] == 1 and "1 thrown out" in reveal.text
    on_file = next(e["payload"] for e in read(runs / "app1/ledger.jsonl") if e["type"] == "mesh.reveal")
    assert on_file["refused"] == [{"id": "a001", "why": "content changed after the seal"}]


def test_a_silent_party_adjourns_the_case(the_bailiff, runs):
    mesh = Mesh(runs, mute="mcclusky")
    asyncio.run(the_bailiff.on_open(mesh, CLERK, OpenCase(app="app1")))
    progress = [m for _, m in mesh.of(Progress)]
    assert [p.event for p in progress] == ["open", "summon", "sealed", "summon", "adjourned"]
    assert "McClusky, Esq. did not answer" in progress[-1].text
    assert len(mesh.of(Ruling)) == 3 and all("did not answer" in m.error for _, m in mesh.of(Ruling))
    assert the_bailiff.live is None and read(runs / "app1/ledger.jsonl")[-1]["type"] == "mesh.adjourned"


def test_one_case_at_a_time_and_only_apps_on_file(the_bailiff, runs):
    mesh = Mesh(runs)
    the_bailiff.live = {"app": "todo", "case_id": "todo-x1", "event": "court", "caption": "Court is in session: 9 claims",
                        "ruling": {}, "locks": [], "chain": ""}

    async def go():
        await the_bailiff.on_open(mesh, CLERK, OpenCase(app="app1"))
        return [await the_bailiff.chat(mesh, USER, t) for t in ("raise app1", "status c03", "case", "ledger", "cross 1/8=")]
    replies = asyncio.run(go())
    [(to, refused)] = mesh.sent
    assert (to, refused.event, refused.case_id) == (CLERK, "adjourned", "") and "case todo-x1" in refused.text
    assert all("case todo-x1" in text and "9 claims" in text and data["busy"] == "todo-x1" for text, data in replies)
    assert asyncio.run(the_bailiff.chat(mesh, USER, "help"))[0] == captions.help_card("bailiff")
    assert not (runs / "app1" / "ledger.jsonl").exists()  # a refusal never touches a ledger

    the_bailiff.live = None
    asyncio.run(the_bailiff.on_open(mesh, CLERK, OpenCase(app="pong")))
    nope = mesh.sent[-1][1]
    assert nope.event == "adjourned" and "cannot raise 'pong'" in nope.text
    assert "app1 (ready)" in nope.text and "todo (not ready" in nope.text


def test_a_chat_user_raises_a_case_and_cross_examines(the_bailiff, runs):
    mesh = Mesh(runs)
    the_bailiff.rate = base.RateLimit(10, clock=lambda: 100.0)  # every cross lands at the same instant

    async def go():
        say = the_bailiff.chat
        return {"before": await say(mesh, USER, "status"), "raise": await say(mesh, USER, "Raise APP1!"),
                "claim": await say(mesh, USER, "status claim 3"), "case": await say(mesh, USER, "case"),
                "ledger": await say(mesh, USER, "ledger"), "cross": await say(mesh, USER, "cross 1/8="),
                "again": await say(mesh, USER, "cross 1/8="), "no key": await say(mesh, OTHER, "cross 2+2="),
                "named": await say(mesh, OTHER, "cross app1 1/8="), "junk": await say(mesh, USER, "sing me a song")}
    r = asyncio.run(go())
    assert r["before"][0] == captions.no_case() and r["raise"] is None
    chat = [m.text() for to, m in mesh.of(ChatMessage) if to == USER]
    assert len(chat) == len(ORDER) and all(t.count("[seance]") == 1 and t.splitlines()[-1].startswith("[seance] {")
                                           for t in chat)
    assert "LOCKED 3 | STRUCK 1 | FABRICATED 1 | UNSWORN 0" in chat[8] and "Funniest strike: c03" in chat[8]
    assert json.loads(chat[-1].splitlines()[-1].removeprefix("[seance] "))["event"] == "closed"
    assert [to for to, _ in mesh.of(Ruling)] == [base.address("mcclusky"), base.address("hoot")]  # chat gets text
    assert r["claim"][0].startswith("c03 STRUCK") and r["claim"][1]["status"] == "STRUCK"
    assert r["case"][0].startswith("RULING, case app1-") and r["case"][1]["credibility_end"] == 963
    assert ", chain intact. Head " in r["ledger"][0] and r["ledger"][0].count(" events") == 1
    assert 'original says "0.12"' in r["cross"][0] and "MISMATCH" in r["cross"][0] and not r["cross"][1]["match"]
    assert "Wait 10 more" in r["again"][0] and "no key for 2" in r["no key"][0]
    assert r["named"][1]["match"] is False  # the refused cross took no slot
    assert r["junk"][0] == captions.help_card("bailiff")
    path = runs / "app1" / "ledger.jsonl"
    events = read(path)
    crosses = [e for e in events if e["type"] == "mesh.cross"]
    assert len(crosses) == 2 and crosses[0]["payload"]["caption"] == r["cross"][0] and verify(path)[0]
    assert not [e for e in events if e["type"] == "verdict" and e["payload"]["ref"] == "cross"]


def test_build_wires_chat_opencase_and_read_only_rest(the_bailiff, runs, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # uagents keeps agent storage in the working directory
    agent = bailiff.build(runs, clock=CLOCK)
    try:
        assert not asyncio.all_tasks(agent._loop)  # local-only: no manifest post to Agentverse is queued
        assert Model.build_schema_digest(ChatMessage) in agent._signed_message_handlers
        assert Model.build_schema_digest(OpenCase) in agent._protocol.signed_message_handlers
        ours = sorted(k for k in agent._rest_handlers if k[1] not in RESERVED_ENDPOINTS)  # the rest are uagents' own
        assert ours == [("GET", "/case"), ("GET", "/locks")]  # read-only: the venue Wi-Fi can reach them
        asyncio.run(the_bailiff.on_open(Mesh(runs), CLERK, OpenCase(app="app1")))
        rest = {path: asyncio.run(agent._rest_handlers[(m, path)](None)) for m, path in ours}
        view, locks = bailiff.CaseView.parse_obj(rest["/case"]), bailiff.LocksView.parse_obj(rest["/locks"])
        assert (view.app, view.event, view.in_session, view.ruling["counts"]) == ("app1", "closed", False, APP1)
        assert locks.case_id == view.case_id and [x["claim_id"] for x in locks.locks] == ["c01", "c02", "c03", "c04", "c05"]
    finally:  # anything left on the never-run loop is cancelled before it can reach the network
        tasks = asyncio.all_tasks(agent._loop)
        for t in tasks:
            t.cancel()
        if tasks:
            agent._loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        agent._loop.close()


def test_the_bailiff_has_no_model():
    tree = ast.parse((MESH / "bailiff.py").read_text(encoding="utf-8"))
    nodes = list(ast.walk(tree))
    modules = [a.name for n in nodes if isinstance(n, ast.Import) for a in n.names]
    modules += [n.module or "" for n in nodes if isinstance(n, ast.ImportFrom)]
    names = {n.id for n in nodes if isinstance(n, ast.Name)} | {n.attr for n in nodes if isinstance(n, ast.Attribute)}
    names |= {a.name for n in nodes if isinstance(n, ast.ImportFrom) for a in n.names}
    assert not [m for m in modules for part in m.split(".") if part in ("llm", "openai", "medium") or part.startswith("asi")]
    assert not names & {"llm", "openai", "persona", "PERSONAS", "ASI1_URL", "objection", "objection_prompt",
                        "make_claims", "LocalParties", "run_case"}


def test_readme_has_badges_every_command_and_an_address_slot():
    text = (MESH / "readme" / "bailiff.md").read_text(encoding="utf-8")
    assert "![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)" in text
    assert "![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)" in text and "<BAILIFF_ADDRESS>" in text
    examples = [ex.strip() for _, example, _ in commands.COMMANDS["bailiff"].values() for ex in example.split("|")]
    assert all(f"`{ex}`" in text for ex in examples), examples
