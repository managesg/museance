import io
import json
import os
import urllib.error

import pytest

from agents.mesh import brain, commands

LIVE_KEY = os.environ.get("ASI1_API_KEY")  # read before conftest's no_dotenv strips it
KEYPAD = {"digits": ["#k7", "#k8", "#k1"], "zero": "#k0", "decimal": "#kdot",
          "operators": {"add": "#kadd", "multiply": "#kmul", "divide": "#kdiv"},
          "equals": "#keq", "clear": "#kc", "observe": "#display"}
WORDS = {"input": "#item", "add": "#add", "lists": {"todo": "#todo", "completed": "#completed"},
         "items": ["#todo li", "#completed li"],
         "item_buttons": {"complete_open": "#todo li .complete", "remove_open": "#todo li .remove",
                          "complete_done": "#completed li .complete", "remove_done": "#completed li .remove"},
         "observe": ["#todo", "#completed", "#item", "body"]}
MENU = ["1) Hear them argue", "2) Test it yourself", "3) Deliver your ruling"]
CASES = [{"app": "calc", "title": "the Calculator"}, {"app": "todo", "title": "Todo"}]
FACTS = {"app": "calc", "title": "the Calculator", "claims": 11, "locked": 11, "struck": 0, "attacks": 20,
         "fidelity": 77, "differences": [{"did": "divide equals", "original": "Error", "revival": "0"}] * 2,
         "credibility": [1000, 1244], "argument": [{"who": "hoot", "line": "Struck! c07: eleven claims, hoo."}],
         "ledger": {"intact": True}}


def reply(obj):
    content = obj if isinstance(obj, str) else json.dumps(obj)
    return io.BytesIO(json.dumps({"choices": [{"message": {"content": content}}]}).encode())


@pytest.fixture
def asi(monkeypatch):
    """A fake ASI-1: queue replies (objects, strings or exceptions); every request lands in calls."""
    monkeypatch.setenv("ASI1_API_KEY", "test-key-not-real")
    monkeypatch.setattr(brain, "PAUSE", 0)
    queue, calls = [], []

    def urlopen(req, timeout):
        calls.append({"timeout": timeout, "body": json.loads(req.data), "auth": req.headers["Authorization"]})
        nxt = queue.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return reply(nxt)
    monkeypatch.setattr(brain.urllib.request, "urlopen", urlopen)
    return queue, calls


def turn(**kw):
    return dict.fromkeys(brain.KEYS) | kw


def test_understand_asks_for_a_strict_schema_and_returns_every_key(asi):
    queue, calls = asi
    queue.append(turn(action="open_case", app="todo", topic="todo revival"))
    r = brain.understand("lobby", "is the todo app back?", ["1) Todo", "2) Calc", "3) How"], None, CASES,
                         [("judge", "hi"), ("bailiff", "All rise!")])
    assert r == turn(action="open_case", app="todo", topic="todo revival")
    body = calls[0]["body"]
    assert (body["model"], body["reasoning_effort"]) == ("asi1", "low") and calls[0]["timeout"] <= brain.TIMEOUT
    fmt = body["response_format"]["json_schema"]
    assert fmt["strict"] is True and set(fmt["schema"]["required"]) == set(brain.KEYS)
    assert fmt["schema"]["properties"]["app"]["enum"] == ["calc", "todo", None]
    assert fmt["schema"]["properties"]["action"]["enum"] == list(brain.ACTIONS)
    prompt = body["messages"][1]["content"]
    assert '"is the todo app back?"' in prompt and "- bailiff: All rise!" in prompt


@pytest.mark.parametrize("bad", [
    turn(action="open_case", app="2048"),       # not on the docket
    turn(action="choose", choice=4),            # outside a 3-choice menu
    turn(action="choose", choice=True),
    turn(action="dance"),
    "not json at all",
    {"choices": "the wrong shape"},
])
def test_invalid_output_is_unclear(asi, bad):
    asi[0].append(bad)
    assert brain.understand("verdict", "do the thing", MENU, FACTS, CASES) == turn(action="unclear")


def test_valid_fields_survive_and_the_rest_is_dropped(asi):
    queue, _ = asi
    queue += [turn(action="choose", choice=3, app="todo"), turn(action="rule", ruling="maybe"),
              turn(action="test", steps=" 7/8= "), turn(action="open_case", topic="[json] {x}"), turn(action="how")]
    assert brain.understand("verdict", "the last one", MENU, FACTS, CASES) == turn(action="choose", choice=3)
    assert brain.understand("verdict", "I rule", MENU, FACTS, CASES) == turn(action="rule")
    assert brain.understand("cross_prompt", "7 over 8", [], FACTS, CASES)["steps"] == "7/8="
    assert brain.understand("closed", "a new case", MENU, FACTS, CASES) == turn(action="open_case")
    assert brain.understand("lobby", "what is this", None, None, None, None) == turn(action="how")


def test_an_answer_with_a_number_not_in_the_facts_is_dropped(asi):
    queue, _ = asi
    queue += [turn(action="ask", answer="Fidelity is 77 out of 100, Your Honor. Hoot found 2 differences."),
              turn(action="ask", answer="Fidelity is 78, Your Honor.")]
    r = brain.understand("verdict", "what is fidelity", MENU, FACTS, CASES)
    assert r["answer"] == "Fidelity is 77 out of 100, Your Honor.\nHoot found 2 differences."
    assert brain.understand("verdict", "what is fidelity", MENU, FACTS, CASES) == turn(action="ask")


def test_the_brain_never_raises(asi, monkeypatch):
    queue, calls = asi
    queue += [TimeoutError("slow"), OSError("offline")]
    for _ in range(2):
        assert brain.understand("verdict", "hmm", MENU, FACTS, CASES)["action"] == "unclear"
    assert brain.understand("verdict", "   ", MENU, FACTS, CASES)["action"] == "unclear" and len(calls) == 2
    assert brain.understand("verdict", "hmm", None, {"app": object()}, [None, {"x": 1}], [1, 2, 3]) == turn(
        action="unclear")  # queue empty: the fake raises IndexError inside the call, still unclear
    monkeypatch.setenv("SEANCE_FAKE_LLM", "1")
    assert brain.understand("verdict", "let them fight", MENU, FACTS, CASES)["action"] == "unclear"
    assert brain.answer("what is fidelity", FACTS) == ""
    assert len(calls) == 3


def test_a_429_is_retried_once_then_given_up(asi):
    queue, calls = asi
    busy = urllib.error.HTTPError(brain.ASI1_URL, 429, "busy", {}, io.BytesIO())
    queue += [busy, turn(action="argue")]
    assert brain.understand("verdict", "let them fight", MENU, FACTS, CASES)["action"] == "argue" and len(calls) == 2
    queue += [busy, busy]
    assert brain.understand("verdict", "let them fight", MENU, FACTS, CASES)["action"] == "unclear"
    assert len(calls) == 4 and not queue
    queue += [urllib.error.HTTPError(brain.ASI1_URL, 401, "no", {}, io.BytesIO())]
    assert brain.understand("verdict", "let them fight", MENU, FACTS, CASES)["action"] == "unclear"
    assert len(calls) == 5 and calls[0]["auth"] == "Bearer test-key-not-real"


def test_steps_for_takes_parser_words_as_they_are_and_repairs_once(asi):
    queue, calls = asi
    assert brain.steps_for("7 / 8 =", KEYPAD) == "7 / 8 =" and not calls
    queue += [{"steps": "7-8=", "why": ""}, {"steps": "7/8=", "why": ""}]
    assert brain.steps_for("seven over eight", KEYPAD) == "7/8="
    fix = calls[1]["body"]["messages"]
    assert fix[-2]["role"] == "assistant" and "no key for -" in fix[-1]["content"]
    assert calls[0]["body"]["response_format"]["json_schema"]["strict"] is True
    queue += [{"steps": "9*9=", "why": ""}, {"steps": "9x9=", "why": ""}]
    with pytest.raises(ValueError) as ex:
        brain.steps_for("nine squared", KEYPAD)
    assert str(ex.value) == brain.CANT and len(calls) == 4


def test_steps_for_says_why_in_plain_words(asi, monkeypatch):
    queue, calls = asi
    queue += [{"steps": "", "why": "There is no minus key on this keypad."},
              {"steps": "", "why": "The court allows only 30 steps."},  # 30: not the judge's, not the keys'
              {"steps": "", "why": "Use click:#k7 instead."}]
    for want in ("There is no minus key on this keypad, Your Honor.", brain.CANT, brain.CANT):
        with pytest.raises(ValueError) as ex:
            brain.steps_for("8 minus 1", KEYPAD)
        assert str(ex.value) == want
    assert len(calls) == 3
    with pytest.raises(ValueError):
        brain.steps_for("", KEYPAD)
    monkeypatch.delenv("ASI1_API_KEY")
    with pytest.raises(ValueError) as ex:
        brain.steps_for("eight minus one", KEYPAD)
    assert str(ex.value) == brain.CANT and len(calls) == 3


def test_answer_numbers_must_be_facts(asi):
    queue, _ = asi
    queue += [{"answer": "Eleven claims held, Your Honor. Credibility went from 1000 to 1,244."},
              {"answer": "Twelve claims held, Your Honor."},
              {"answer": "Claim c07 was struck."},
              {"answer": "Fine. " + "very " * 25 + "long. Ignored too."},
              {"answer": "Noted. Two words. Three, dropped unread."}]
    assert brain.answer("how did he do", FACTS, "verdict") == \
        "Eleven claims held, Your Honor.\nCredibility went from 1000 to 1,244."
    assert brain.answer("how did he do", FACTS) == ""  # 12 is no fact
    assert brain.answer("which claim", FACTS) == ""  # claim ids never reach the chat
    assert brain.answer("go on", FACTS) == "Fine."  # a long sentence is dropped, never cut
    assert brain.answer("count", FACTS) == "Noted.\nTwo words."  # 3 is no fact, but its sentence is not said
    assert "c07" not in json.dumps(brain._brief(FACTS)) and brain._brief(FACTS)["differences_count"] == 2


def test_answer_without_facts_takes_no_numbers(asi):
    queue, _ = asi
    queue += [{"answer": "A court for apps that came back, Your Honor."}, {"answer": "It tests 20 things."}]
    assert brain.answer("what is this place", None, "lobby") == "A court for apps that came back, Your Honor."
    assert brain.answer("what is this place", None, "lobby") == ""


def test_numbers_reads_digits_and_words():
    assert brain._numbers("1,244 points, 7.10 and eleven, 07") == {"1244", "7.1", "11", "7"}
    assert brain._facts_numbers({"a": True, "b": [3, "x 12"], "c": 0.5}) == {"3", "12", "0.5"}


def test_grammar_comes_from_the_parser():
    pad = brain.grammar_for(KEYPAD)
    assert "digits 0 1 7 8" in pad and "divide / ÷" in pad and "equals =" in pad and "9" not in pad
    words = brain.grammar_for(WORDS)
    assert 'add <text> -> type "<text>", add' in words and "add -> add;" in words and "remove done" in words
    for phrase in ("add <text>", "add", "complete", "uncomplete", "remove done"):
        commands.to_steps(WORDS, phrase)  # every phrase it offers parses
    bare = brain.grammar_for({"observe": "body", "start": "#go"})
    assert "click:<selector>" in bare and "#go (start)" in bare
    assert brain.grammar_for({}) == ""


@pytest.mark.skipif(not LIVE_KEY, reason="live ASI-1: run with ASI1_API_KEY set")
def test_live_asi1_understands_a_judge(monkeypatch):
    monkeypatch.setenv("ASI1_API_KEY", LIVE_KEY)
    r = brain.understand("cross_prompt", "what is 7 divided by 8", [], FACTS, CASES, (), brain.grammar_for(KEYPAD))
    assert r["action"] == "test" and commands.to_steps(KEYPAD, r["steps"]) == commands.to_steps(KEYPAD, "7/8=")


def test_steps_lose_double_quotes():
    from agents.mesh import brain
    assert brain._unquote('add "buy eggs", complete') == "add buy eggs, complete"
    assert brain._unquote("add “milk”") == "add milk"
