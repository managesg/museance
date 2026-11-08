import io
import json
import re
import shutil

import pytest

from agents.mesh import case, commands, docket

LISTY = {"input": "#new", "add": "#go", "observe": ["#open", "body"]}  # the todo grammar, no item buttons
CALCY = {"digits": ["#d4", "#d5"], "zero": "#d0", "operators": {"add": "#plus"}, "equals": "#eq", "observe": "#out"}
LIST = {"title": "the Old List", "about": "A to-do list whose host shut down in 2019.", "example": "add eggs"}
CALC = {"title": "the Adding Machine", "about": "A tiny adding machine written for these tests.", "example": "4 + 5 ="}


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A court that knows only what add() puts on disk; starts with a real dead app (oldlist, URL source, README)
    and a fixture (acalc). No ASI-1 key: conftest drops it."""
    reg = {}
    for name in ("REG", "DIG", "PILES", "CASES"):
        monkeypatch.setattr(case, name, tmp_path / name.lower())
    monkeypatch.setattr(case, "_registry", lambda: reg)
    monkeypatch.setattr(docket, "APPS", tmp_path / "apps")
    runs = tmp_path / "runs"

    def add(app, selectors, source, name, readme="", sheet=("It does things.",)):
        reg[app] = {"id": app, "name": name, "source": source, "license": "MIT"}
        case.REG.mkdir(exist_ok=True)
        (case.REG / f"{app}-selectors.json").write_text(json.dumps(selectors))
        for kind in ("original", "revival"):
            (runs / app / kind).mkdir(parents=True)
            (runs / app / kind / "index.html").write_text("<p>app</p>")
        (runs / app / "evidence.json").write_text("[]")
        (runs / app / "sheet.json").write_text(json.dumps({"app": app, "lines": [{"text": t} for t in sheet]}))
        if readme:
            (docket.APPS / app).mkdir(parents=True)
            (docket.APPS / app / "README.md").write_text(readme)

    add("oldlist", LISTY, "https://example.org/oldlist@abc1", "oldlist (someone)", sheet=("Add puts a task first.",),
        readme="# oldlist\n- Why dead: the host shut down in 2019 (`curl https://example.org` -> 404); "
               "no commits since 2018.\n")
    add("acalc", CALCY, "fixtures/acalc (written for these tests, not a real dead app)", "fixture-acalc",
        sheet=("Pressing 4 + 5 = shows 9.",))
    return runs, add


def asi1(monkeypatch, answers):
    """Fake ASI-1, no network: answers[app] lists its replies (a card dict, or an exception to raise) in call order."""
    monkeypatch.setenv("ASI1_API_KEY", "test-key-not-real")
    bodies = []

    def urlopen(req, timeout):
        body = json.loads(req.data)
        bodies.append(body)
        reply = answers[re.search(r"App id: (\S+)", body["messages"][1]["content"])[1]].pop(0)
        if isinstance(reply, Exception):
            raise reply
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": json.dumps(reply)}}]}).encode())
    monkeypatch.setattr(docket.urllib.request, "urlopen", urlopen)
    return bodies


def fit(rows):
    """Every row is chat-ready, and the court's parser takes its example."""
    for r in rows:
        assert set(r) == {"app", "title", "about", "example"}
        assert len(r["title"].split()) <= 4 and len(r["about"].split()) <= 16 and len(r["example"].split()) <= 8
        commands.to_steps(json.loads((case.REG / f"{r['app']}-selectors.json").read_text()), r["example"])


def test_asi1_writes_each_card_once_and_a_changed_source_rewrites_it(world, monkeypatch):
    runs, _ = world
    bodies = asi1(monkeypatch, {"oldlist": [LIST, {**LIST, "title": "the Older List"}], "acalc": [CALC]})
    rows = docket.cases(runs)
    assert rows == [{"app": "oldlist", **LIST}, {"app": "acalc", **CALC}]
    fit(rows)
    b = bodies[0]
    assert (b["model"], b["reasoning_effort"]) == ("asi1", "low") and b["response_format"]["json_schema"]["strict"]
    assert "the host shut down in 2019" in b["messages"][1]["content"]  # the README reached ASI-1
    assert "say add <text>" in b["messages"][1]["content"]  # so did the grammar, in the parser's own words
    assert json.loads((runs / "acalc" / "card.json").read_text())["by"] == "asi1"
    assert docket.cases(runs) == rows and docket.card("acalc", runs) == rows[1] and len(bodies) == 2  # cache hits
    (docket.APPS / "oldlist" / "README.md").write_text("# oldlist\n- Why dead: archived in 2019.\n")
    assert docket.cases(runs) == [{"app": "oldlist", **LIST, "title": "the Older List"}, rows[1]]
    assert len(bodies) == 3  # only the app whose sources changed


def test_fallback_without_asi1_then_warm_asks_again(world, monkeypatch):
    runs, _ = world
    rows = docket.cases(runs)  # no key: no call at all
    assert rows == [
        {"app": "oldlist", "title": "Oldlist", "about": "The host shut down in 2019; no commits since 2018.",
         "example": "add Buy milk"},  # the grammar's own example; its "complete" part needs buttons oldlist lacks
        {"app": "acalc", "title": "Acalc", "about": "Written for these tests, not a real dead app.",
         "example": "4 + 5 ="}]  # the grammar's 7/8= needs keys acalc lacks: a sum on its own keys
    fit(rows)
    answers = {"oldlist": [OSError("down")], "acalc": [OSError("down")]}
    bodies = asi1(monkeypatch, answers)
    assert docket.cases(runs) == rows and not bodies  # a fallback card is cached too: no call per lobby
    docket.warm(runs)
    assert len(bodies) == 2 and docket.cases(runs) == rows  # still down: still the fallback
    answers.update(oldlist=[LIST], acalc=[CALC])
    docket.warm(runs)
    assert docket.cases(runs) == [{"app": "oldlist", **LIST}, {"app": "acalc", **CALC}] and len(bodies) == 4
    docket.warm(runs)
    assert len(bodies) == 4  # ASI-1's cards are kept
    monkeypatch.setattr(case, "apps", lambda runs: 1 / 0)
    assert docket.warm(runs) is None  # never raises


def test_example_must_pass_the_parser_with_one_retry(world, monkeypatch):
    runs, _ = world
    bodies = asi1(monkeypatch, {
        "oldlist": [{**LIST, "example": "click:#go"}, {**LIST, "example": "1"}],  # never fixed: fallback example
        "acalc": [{**CALC, "example": "7 - 8 =", "about": "Born in 1999."}, CALC]})  # fixed on the retry
    rows = docket.cases(runs)
    assert rows == [{"app": "oldlist", **LIST, "example": "add Buy milk"}, {"app": "acalc", **CALC}]
    fit(rows)
    told = bodies[3]["messages"][-1]["content"]  # acalc's retry carries the court's refusal
    assert "no key for - 7 8 on this app" in told and "1999" in told
    assert "has code" in bodies[1]["messages"][-1]["content"]
    assert len(bodies) == 4


def test_docket_order_real_dead_apps_first_then_fixtures_then_id(world):
    runs, add = world
    add("blist", LISTY, "http://example.org/blist", "blist")
    add("zfix", CALCY, "fixtures/zfix", "fixture-zfix")
    add("unready", CALCY, "https://example.org/unready", "unready")
    shutil.rmtree(runs / "unready" / "revival")
    rows = docket.cases(runs)
    assert [r["app"] for r in rows] == ["blist", "oldlist", "acalc", "zfix"]
    fit(rows)
    with pytest.raises(case.MissingInput):
        docket.card("unready", runs)
