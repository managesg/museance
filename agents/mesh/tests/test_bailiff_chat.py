"""The Bailiff's courtroom wiring: the docket from disk, brain.understand as the ears, honest case reuse, and the
judge's words reaching the court only through the parser. The runs fixture turns both fakes on (no browser, no
canned party voices); ASI-1 is faked here."""
import asyncio
import json
import re

import pytest
from uagents_core.contrib.protocols.chat import ChatMessage

from agents.mesh import bailiff, base, brain, courtroom
from test_agents import CLOCK, USER, Mesh


class Chat(Mesh):
    session = "judge-session-1"


def openings(ctx):
    return sum(bailiff.OPENING in m.text() for _, m in ctx.sent if isinstance(m, ChatMessage))


def test_a_judge_session_through_the_bailiff(runs, monkeypatch):
    heard = []
    said = {"is the calculator legit?": {"action": "open_case", "app": "app1"},
            "what does 1 divided by 8 give?": {"action": "test", "steps": "1/8="},
            "it's a forgery": {"action": "rule", "ruling": "forgery"}}

    def understand(stage, text, menu, facts, cases, history, grammar):
        heard.append({"stage": stage, "menu": menu, "app": (facts or {}).get("app"), "history": len(history),
                      "docket": [c["app"] for c in cases], "grammar": grammar})
        return {**dict.fromkeys(brain.KEYS), "action": "unclear", **said.get(text, {})}
    monkeypatch.setattr(brain, "understand", understand)
    court, ctx = bailiff.Bailiff(runs, CLOCK), Chat(runs)
    say = lambda t: asyncio.run(court.court_chat(ctx, USER, t))  # noqa: E731

    lobby, data = say("@thebailiff hello")
    cases = json.loads((runs / "app1" / "card.json").read_text())["card"]  # the docket wrote it from the files
    assert f"2) The case of {cases['title']}" in lobby and data == {"cmd": "court", "stage": "lobby"}
    verdict, data = say("is the calculator legit?")
    assert verdict.startswith(f"⚖️ The case of {cases['title']}: ") and data["stage"] == "verdict"
    assert openings(ctx) == 1  # one line before a live case
    crossed, data = say("what does 1 divided by 8 give?")
    assert crossed.startswith("🔍 Tried on both apps: 1 divide 8 equals") and data["stage"] == "cross_result"
    ruled, data = say("it's a forgery")
    assert ruled.startswith("⚖️ Your Honor rules: Forgery.") and data["stage"] == "closed"
    assert [h["stage"] for h in heard] == ["lobby", "lobby", "verdict", "cross_result"]
    assert heard[1]["docket"] == ["todo", "app1"] and heard[1]["app"] is None and heard[1]["grammar"] == ""
    assert heard[2]["app"] == "app1" and heard[2]["grammar"].startswith("A keypad") and heard[2]["history"] == 4
    assert heard[2]["menu"] == courtroom.VERDICT
    for reply in (lobby, verdict, crossed, ruled):
        assert all(len(ln.split()) <= 20 for ln in reply.splitlines()) and not set("[]{}") & set(reply)
    assert say("2")[1]["stage"] == "closed" and len(heard) == 4  # digits keep the fast path: the ears never hear


def test_a_recent_case_is_reused_honestly_and_rerun_on_request(runs, monkeypatch):
    court, ctx = bailiff.Bailiff(runs, CLOCK), Mesh(runs)
    case_now = lambda **kw: asyncio.run(court.case_summary(ctx, USER, "app1", **kw))  # noqa: E731
    first = case_now()
    assert "ran_minutes_ago" not in first and openings(ctx) == 1
    again = case_now()
    assert again == {**first, "ran_minutes_ago": 0} and openings(ctx) == 1  # same evidence, said honestly
    assert "ran_minutes_ago" not in case_now(fresh=True) and openings(ctx) == 2
    monkeypatch.setenv("SEANCE_FRESH_S", "0")
    case_now()
    assert openings(ctx) == 3
    monkeypatch.delenv("SEANCE_FRESH_S")
    path = runs / "app1" / "ruling.json"
    path.write_text(json.dumps({**json.loads(path.read_text()), "error": "McClusky did not answer"}))
    assert "ran_minutes_ago" not in case_now() and openings(ctx) == 4  # an adjourned case is never reused


def test_the_judges_words_reach_the_court_only_through_the_parser(runs, monkeypatch):
    court, asked = bailiff.Bailiff(runs, CLOCK), []
    monkeypatch.setenv("ASI1_API_KEY", "test-key-not-real")
    monkeypatch.delenv("SEANCE_FAKE_LLM")
    monkeypatch.setattr(brain, "_ask", lambda msgs, schema, name: asked.append(name) or {"steps": "1/8=", "why": ""})
    assert court.judge_cross(USER, "app1", "one divided by eight, please")["did"] == "1 divide 8 equals"
    assert asked == ["court_test"]
    court.rate = base.RateLimit(0)
    assert court.judge_cross(USER, "app1", "1/8=")["did"] == "1 divide 8 equals" and asked == ["court_test"]
    monkeypatch.setattr(brain, "_ask", lambda *a: {"steps": "", "why": "There is no square root key here."})
    with pytest.raises(ValueError, match=r"^There is no square root key here, Your Honor\.$"):
        court.judge_cross(USER, "app1", "the square root of 2")
    assert court.parses("app1", "7/8=") and not court.parses("app1", "add milk") and not court.parses("pong", "1")
    assert re.match(r"A keypad: .*digits 0 1", brain.grammar_for(court.selectors("app1")))
