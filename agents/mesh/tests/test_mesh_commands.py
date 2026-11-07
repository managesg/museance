import json
import pathlib

import pytest

from agents.mesh.commands import COMMANDS, CrossError, human_steps, names, parse, to_steps

ROOT = pathlib.Path(__file__).resolve().parents[3]
CALC = json.loads((ROOT / "eval/regression/app1-selectors.json").read_text())
TODO = json.loads((ROOT / "eval/regression/todo-selectors.json").read_text())


@pytest.mark.parametrize("role,text,want", [
    ("bailiff", "raise todo", ("raise", "todo")),
    ("bailiff", "Raise TODO!", ("raise", "todo")),
    ("mcclusky", "can you please raise the todo app?", ("raise", "todo")),
    ("bailiff", "raise", ("raise", "")),
    ("bailiff", "status claim c3", ("status", "c03")),
    ("bailiff", "STATUS C03.", ("status", "c03")),
    ("bailiff", "status", ("status", "")),
    ("bailiff", "c3", ("status", "c03")),
    ("mcclusky", "why claim 3?", ("why", "c03")),
    ("mcclusky", "c03", ("why", "c03")),
    ("mcclusky", "Why would anyone trust you?", ("talk", "Why would anyone trust you?")),
    ("mcclusky", "what's my credibility", ("credibility", "")),
    ("mcclusky", "show me the claims", ("claims", "")),
    ("bailiff", "cross 7+8=", ("cross", "7+8=")),
    ("bailiff", "Cross-examine: add Buy milk, complete", ("cross", "add Buy milk, complete")),
    ("bailiff", "cross type:#item:Buy Milk click:#add", ("cross", "type:#item:Buy Milk click:#add")),
    ("bailiff", "sing me a song", ("help", "")),
    ("bailiff", "", ("help", "")),
    ("bailiff", "?", ("help", "")),
    ("bailiff", "ledger please", ("transcript", "")),
    ("bailiff", "transcript", ("transcript", "")),
    ("bailiff", "@agent1qw47zhtg9gj55676vy8myruj297 help", ("help", "")),
    ("bailiff", "@agent1qa @agent1qb status c3", ("status", "c03")),
    ("mcclusky", "@agent1q2ehsgka raise todo", ("raise", "todo")),
    ("bailiff", "case", ("case", "")),
    ("bailiff", "apps", ("apps", "")),
    ("hoot", "reveal!", ("reveal", "")),
    ("hoot", "Show attacks", ("attacks", "")),
    ("hoot", "c3", ("talk", "c3")),
    ("hoot", "you are a bad owl", ("talk", "you are a bad owl")),
])
def test_parse_is_forgiving_and_deterministic(role, text, want):
    assert parse(role, text) == want


def test_every_listed_command_parses_to_itself():
    for role, cmds in COMMANDS.items():
        for name, (aliases, _, _) in cmds.items():
            assert all(parse(role, f"{a} c1").name == name for a in aliases), (role, name)  # bare "why" is talk


def test_calculator_expressions():
    assert to_steps(CALC, "7+8=") == (["click:#k7", "click:#kadd", "click:#k8", "click:#keq"], "#display")
    assert to_steps(CALC, "7 x 8 =")[0][1] == "click:#kmul"
    assert to_steps(CALC, "10 / 8 = C")[0] == ["click:#k1", "click:#k0", "click:#kdiv", "click:#k8", "click:#keq",
                                               "click:#kc"]
    assert to_steps(CALC, ".7")[0] == ["click:#kdot", "click:#k7"]


def test_todo_words():
    steps, observe = to_steps(TODO, "add Buy milk, enter Walk dog, complete, observe completed")
    assert steps == ["type:#item:Buy milk", "click:#add", "type:#item:Walk dog", "key:Enter",
                     "click:#todo li .complete"] and observe == "#completed"
    assert to_steps(TODO, "add A then remove") == (["type:#item:A", "click:#add", "click:#todo li .remove"], "body")
    assert to_steps(TODO, "add A, complete, remove done")[0][-1] == "click:#completed li .remove"


def test_contract_steps_pass_through():
    assert to_steps(TODO, "type:#item:a, b click:#add") == (["type:#item:a, b", "click:#add"], "body")
    assert to_steps(CALC, "click:#k7, click:#keq observe #display") == (["click:#k7", "click:#keq"], "#display")


@pytest.mark.parametrize("sel,text", [
    (CALC, "2+2="),                # no 2 key on this app
    (CALC, "7-1="),                # no minus either
    (CALC, "click:#evil"),         # not in the vocabulary
    (CALC, "type:#item:x"),        # another app's selector
    (CALC, "7" * 31),              # 31 steps
    (CALC, "wait:999999"),         # parks the bench
    (CALC, "key:Enter;rm"),        # junk key name
    (CALC, "7+8= observe #nope"),  # observe outside the vocabulary
    (CALC, ""),
    (TODO, "dance"),
])
def test_cross_refuses(sel, text):
    with pytest.raises(CrossError):
        to_steps(sel, text)


def test_selectors_read_back_as_their_key_names():
    assert names(CALC)["#kdiv"] == "divide" and names(CALC)["#k7"] == "7" and names(TODO)["#add"] == "add"
    assert human_steps(CALC, ["click:#k7", "click:#kdiv", "click:#k8", "click:#keq"]) == "7 divide 8 equals"
    assert human_steps(CALC, ["click:#k7"] * 20 + ["click:#keq"]) == "7 ×20 equals"
    assert human_steps(TODO, ["type:#item:Buy milk", "click:#add"] * 2 + ["click:#todo li .complete"]) == \
        '(type "Buy milk", add) ×2, complete open'
    assert human_steps(TODO, ["key:Enter"]) == "Enter"
