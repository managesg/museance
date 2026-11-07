"""The three agents at handler level, with fake contexts that record every send. The runs fixture turns both
fakes on; tests always run on throwaway seeds (base.seed)."""
import ast
import asyncio
import json
import logging
import pathlib
import subprocess
import sys
import uuid

from uagents_core.contrib.protocols.chat import ChatMessage
from uagents_core.types import DeliveryStatus, MsgStatus

from agents.mesh import bailiff, base, captions, case, hoot, mcclusky, models
from agents.mesh.models import (CallMedium, CallSkeptic, OpenCase, Progress, Remark, RemarkRequest, RequestReveal,
                                RevealAttacks, Ruling, SealedAttacks)
from court.ledger import read, verify

MESH = pathlib.Path(bailiff.__file__).parent
CLOCK = lambda: "2026-11-07T21:00:00+00:00"  # noqa: E731
ORDER = ["open", "sealed", "sworn", "revealed", "ruling", "remark", "remark"]
USER, CLERK = "agent1quser", "agent1qclerk"


def status(ok=True):
    return MsgStatus(status=DeliveryStatus.DELIVERED if ok else DeliveryStatus.FAILED,
                     detail="delivered" if ok else "Timeout waiting for response", destination="", endpoint="",
                     session=uuid.uuid4())


class Mesh:
    """A fake ctx: send records what leaves; send_and_receive answers the way Dr. Hoot and McClusky do, from the
    lanes' own code. mute: that party never answers."""
    logger = logging.getLogger("test")

    def __init__(self, runs, mute=""):
        self.runs, self.mute, self.sent, self.attacks = runs, mute, [], []
        self.inputs = case.load_inputs("app1", runs)

    async def send(self, to, msg):
        self.sent.append((to, type(msg).parse_raw(msg.json())))
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
            claims, dropped = case.make_claims(msg.app, self.inputs, self.runs)
            reply = models.Testimony(**ids, claims=claims, dropped=len(dropped))
        elif isinstance(msg, RequestReveal):
            reply = RevealAttacks(**ids, attacks=self.attacks)
        else:
            reply = Remark(case_id=msg.case_id, speaker=role, text=f"{role} has words")
        return response_type.parse_raw(reply.json()), status()

    def of(self, kind):
        return [(to, m) for to, m in self.sent if isinstance(m, kind)]


def texts(ctx, to=USER):
    return [m.text() for t, m in ctx.sent if t == to and isinstance(m, ChatMessage)]


def human_lines_fit(text: str) -> bool:
    return all(len(ln.split()) <= 20 for ln in text.splitlines() if not ln.startswith("[seance]"))


# --- the Bailiff ------------------------------------------------------------------------------------------
def test_a_case_raised_through_mcclusky(runs):
    court, ctx, mc, owl = bailiff.Bailiff(runs, CLOCK), Mesh(runs), base.address("mcclusky"), base.address("hoot")
    asyncio.run(court.on_open(ctx, mc, OpenCase(app="app1", requester=USER)))
    progress = [m for _, m in ctx.of(Progress)]
    assert [p.event for p in progress] == ORDER and {p.requester for p in progress} == {USER}
    assert [to for to, _ in ctx.of(Ruling)] == [mc, owl]
    r = ctx.of(Ruling)[0][1]
    assert r.text.startswith("⚖️ The case: is the revived app1") and r.data["ok"] and r.data["struck"] == 1
    assert "🐧 mcclusky has words" in r.text and r.requester == USER
    path = runs / "app1" / "ledger.jsonl"
    hops = [e for e in read(path) if e["type"].startswith("mesh.")]
    assert verify(path)[0] and [e["type"][5:] for e in hops] == ORDER
    assert [p.text for p in progress] == [e["payload"]["caption"] for e in hops]
    assert court.live is None and court.snapshot()["case_id"] == r.case_id


def test_a_silent_party_ends_the_case_with_an_error_ruling(runs):
    court, ctx = bailiff.Bailiff(runs, CLOCK), Mesh(runs, mute="mcclusky")
    asyncio.run(court.on_open(ctx, CLERK, OpenCase(app="app1")))
    assert [m.event for _, m in ctx.of(Progress)] == ["open", "sealed", "ruling"]
    r = ctx.of(Ruling)[0][1]
    assert "did not answer" in r.error and "adjourned" in r.text and not r.data["ok"]


def test_chat_commands_after_a_case(runs):
    court, ctx = bailiff.Bailiff(runs, CLOCK), Mesh(runs)
    out = asyncio.run(court.chat(ctx, USER, "@agent1qw47zhtg9gj55676 raise app1"))  # a chat user raises it here
    assert out[0].startswith("⚖️ The case") and out[1]["ok"]
    assert len(texts(ctx)) == 4  # the status lines; the final reply is the handler's answer
    say = lambda t: asyncio.run(court.chat(ctx, USER, t))  # noqa: E731
    text, data = say("status")
    assert "Original: 3 locked, 1 struck" in text and data["cmd"] == "status" and human_lines_fit(text)
    assert say("status c3")[0].startswith("c03 STRUCK")
    text, data = say("transcript")
    lines = [ln for ln in text.splitlines() if ln[:1].isdigit()]
    assert len(lines) == 7 and lines[0].startswith("1. 🔨 Case") and text.endswith("chain intact.") and data["chain"]
    assert "Totals: 5 claims" in say("case")[0]
    assert say("apps")[0].startswith("Docket:") and say("dance")[0] == captions.help_card("bailiff")


def test_cross_is_refused_in_session_and_logged_after(runs):
    court, ctx = bailiff.Bailiff(runs, CLOCK), Mesh(runs)
    court.live = {"app": "app1", "case_id": "app1-x", "event": "open", "caption": "🔨 Case app1-x opened."}
    text, data = asyncio.run(court.chat(ctx, USER, "cross 1/8="))
    assert text.startswith("The court is in session.") and data["ok"] is False
    court.live = None
    case.run_case("app1", runs=runs, case_id="app1-y")
    text, data = asyncio.run(court.chat(ctx, USER, "cross app1 1/8="))
    assert "1 divide 8 equals" in text and data["verdict"] == "differ"
    last = read(runs / "app1" / "ledger.jsonl")[-1]
    assert last["type"] == "mesh.cross" and set(last["payload"]) == {"who", "steps", "verdict", "agent", "caption"}
    assert last["payload"]["who"] == USER and len(last["payload"]["caption"].split()) <= 20
    assert asyncio.run(court.chat(ctx, USER, "cross app1 1/8="))[0].startswith("One cross per witness")


def test_the_bailiff_imports_no_model_code():
    for name in ("bailiff.py", "base.py", "case.py", "captions.py", "commands.py"):
        tree = ast.parse((MESH / name).read_text(encoding="utf-8"))
        top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        mods = [a.name for n in top if isinstance(n, ast.Import) for a in n.names]
        mods += [f"{n.module}.{a.name}" for n in top if isinstance(n, ast.ImportFrom) for a in n.names]
        assert not [m for m in mods if any(w in m for w in ("llm", "medium", "voice", "reader", "urllib"))], name
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import agents.mesh.bailiff; "
            "print(sorted(m for m in sys.modules if m in ('llm', 'agents.llm', 'agents.medium', 'agents.mesh.voice',"
            " 'dig.reader')))")
    out = subprocess.run([sys.executable, "-c", code, str(MESH.parents[1])], capture_output=True, text=True, timeout=60)
    assert out.stdout.strip() == "[]", out.stdout + out.stderr


# --- McClusky ----------------------------------------------------------------------------------------------
class Ctx:
    """The slice of a uAgents context McClusky uses."""

    def __init__(self, delivered=True):
        self.sent, self.delivered, self.logger, self.session = [], delivered, logging.getLogger("test"), uuid.uuid4()

    async def send(self, to, msg):
        self.sent.append((to, msg))
        return status(self.delivered)


def test_raise_relays_four_status_lines_then_one_final_reply(runs):
    r = case.run_case("app1", runs=runs, case_id="app1-r")
    events = [e for e in read(runs / "app1" / "ledger.jsonl") if e["type"].startswith("mesh.")]
    b, mc, ctx = "agent1qbailiff", None, Ctx()
    mc = mcclusky.McClusky(b, "agent1qhoot", runs)

    async def play():
        task = asyncio.create_task(mc.chat(ctx, USER, "@agent1q2ehsgka can you bring back the app1 app?"))
        await asyncio.sleep(0.05)
        assert ctx.sent[-1] == (b, OpenCase(app="app1", requester=USER))
        for e in events:
            await mc.on_progress(ctx, b, Progress(case_id="app1-r", app="app1", requester=USER, event=e["type"][5:],
                                                  text=e["payload"]["caption"]))
        await mc.on_ruling(ctx, "agent1qimpostor", Ruling(case_id="x", app="app1", requester=USER, text="forged"))
        await mc.on_ruling(ctx, b, bailiff.ruling_message(r, USER))
        return await task
    text, data, pics = asyncio.run(play())
    assert [t.split("\n\n")[0] for t in texts(ctx)] == list(case.PROGRESS.values())
    assert text == captions.final_reply(r) and data["case_id"] == "app1-r" and pics == []  # no AGENTVERSE_API_KEY
    assert "📸" not in text or "runs/app1/shots" in text
    assert mc.waiting == {}


def test_mcclusky_refuses_unknown_apps_and_never_answers_peers(runs):
    mc, ctx = mcclusky.McClusky("agent1qbailiff", "agent1qhoot", runs), Ctx()
    text, data = asyncio.run(mc.chat(ctx, USER, "raise pong"))
    assert "cannot raise 'pong'" in text and not data["ok"] and not ctx.sent
    assert asyncio.run(mc.chat(ctx, "agent1qhoot", "raise app1")) is None
    assert asyncio.run(mc.chat(ctx, USER, "help"))[0] == captions.help_card("mcclusky")
    text, _ = asyncio.run(mcclusky.McClusky("agent1qbailiff", "", runs).chat(Ctx(delivered=False), USER, "raise app1"))
    assert text.startswith("The Bailiff did not answer")


def test_mcclusky_testifies_and_remarks_for_the_bailiff_only(runs):
    mc, ctx = mcclusky.McClusky("agent1qbailiff", "agent1qhoot", runs), Ctx()
    asyncio.run(mc.on_call(ctx, "agent1qimpostor", CallMedium(case_id="t", app="app1")))
    asyncio.run(mc.on_call(ctx, "agent1qbailiff", CallMedium(case_id="t", app="app1")))
    (to, t), = ctx.sent
    assert to == "agent1qbailiff" and [c["id"] for c in t.claims] == ["c01", "c02", "c03", "c04", "c05"]
    r = case.run_case("app1", runs=runs, case_id="app1-v")
    asyncio.run(mc.on_remark(ctx, "agent1qbailiff", RemarkRequest(case_id="app1-v", app="app1", ruling=r)))
    assert ctx.sent[-1][1].text == captions.objection(r)  # SEANCE_FAKE_LLM=1: the deterministic line


# --- Dr. Hoot -------------------------------------------------------------------------------------------------
def test_hoot_seals_and_reveals_for_the_bailiff_only(runs):
    owl, ctx = hoot.Hoot(runs, "agent1qbailiff"), Ctx()
    asyncio.run(owl.on_call(ctx, "agent1qimpostor", CallSkeptic(case_id="h", app="app1")))
    asyncio.run(owl.on_call(ctx, "agent1qbailiff", CallSkeptic(case_id="h", app="app1")))
    asyncio.run(owl.on_reveal(ctx, "agent1qbailiff", RequestReveal(case_id="h", app="app1")))
    (_, refused), (_, sealed), (_, revealed) = ctx.sent
    assert refused.error == hoot.STRANGER and len(sealed.seal["attacks"]) == 20 and len(revealed.attacks) == 20
    assert case.verify_reveal(sealed.seal, revealed.attacks)[1] == []


def test_hoot_chat_reveal_only_after_a_ruling(runs):
    owl, ctx = hoot.Hoot(runs, "agent1qbailiff"), Ctx()
    say = lambda t: asyncio.run(owl.chat(ctx, USER, t))  # noqa: E731
    assert say("reveal app1")[0].startswith("🦉 Hoo hoo, no.")
    assert "20 attacks on app1, picked from 75 P4 sealed" in say("attacks app1")[0]
    assert "matches P4's seal" in say("seal app1")[0]
    case.run_case("app1", runs=runs, case_id="app1-h")
    text, data = say("reveal app1")
    assert text.startswith("🦉 Revealed for app1: 20 attacks") and data["caught"] >= 1 and human_lines_fit(text)
    assert say("you are a bad owl")[1]["cmd"] == "talk"


def test_screenshots_ride_along_only_with_an_agentverse_key(tmp_path, monkeypatch):
    import uagents_core.storage
    shots = [{"ref": "c11", "original": str(tmp_path / "o.png"), "revival": str(tmp_path / "r.png")}]
    for f in ("o.png", "r.png"):
        (tmp_path / f).write_bytes(b"\x89PNG fake")
    calls = []

    class Store:
        def __init__(self, api_token, storage_url):
            self.storage_url = storage_url
            calls.append(("init", api_token == "test-agentverse-key"))

        def create_asset(self, name, content, mime_type):
            calls.append(("asset", name, mime_type))
            return f"id-{len(calls)}"

        def set_permissions(self, asset_id, agent_address):
            calls.append(("perm", asset_id, agent_address))

    monkeypatch.setattr(uagents_core.storage, "ExternalStorage", Store)
    assert mcclusky.attach(USER, shots) == []  # no key: skipped silently
    monkeypatch.setenv("AGENTVERSE_API_KEY", "test-agentverse-key")
    pics = mcclusky.attach(USER, shots)
    assert [p.resource.metadata for p in pics] == [{"mime_type": "image/png", "role": "image"}] * 2
    assert pics[0].resource.uri.startswith("agent-storage://") and pics[0].resource.uri.endswith("/id-2")
    assert calls[0] == ("init", True) and ("perm", "id-2", USER) in calls and calls[1][1:] == ("c11.original.png",
                                                                                              "image/png")
    monkeypatch.setattr(Store, "create_asset", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("401")))
    assert mcclusky.attach(USER, shots) == []  # any failure: skipped, the text line stays
