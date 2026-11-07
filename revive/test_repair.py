"""Offline tests for the repair loop; the builder is a fake, no model is called."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from revive.check_revival import check_revival
from revive.repair import make_prompt, repair, run

ROOT = Path(__file__).resolve().parent.parent
OLD = """<html><body><div id="display">0</div><button id="k1"></button><button id="k8"></button>
<button id="kdiv"></button><button id="keq"></button>
<script>
var cur = '0', acc = 0, op = null;
function show() { document.getElementById('display').textContent = cur; }
document.getElementById('k1').onclick = function () { cur = cur === '0' ? '1' : cur + '1'; show(); };
document.getElementById('k8').onclick = function () { cur = cur === '0' ? '8' : cur + '8'; show(); };
document.getElementById('kdiv').onclick = function () { acc = +cur; op = '/'; cur = '0'; };
document.getElementById('keq').onclick = function () { cur = String(Math.round(acc / +cur * 100) / 100); show(); };
</script></body></html>
"""
GOOD_PATCH = OLD.replace("Math.round", "Math.floor")
BAD_PATCH = GOOD_PATCH.replace("textContent = cur;", "textContent = op === null ? '?' : cur;")  # fixes 1/8, breaks the goods
CLAIM = {"id": "c03", "app": "appx", "text": "1 / 8 rounds to 0.13",
         "test": {"steps": ["click:#k1", "click:#kdiv", "click:#k8", "click:#keq"], "observe": "#display", "expect": "0.13"}}
VERDICT = {"ref": "c03", "kind": "claim", "original": "0.12", "revival": "0.13", "claim_true": False, "match": False,
           "flaky": False, "shrunk_steps": ["click:#k1", "click:#kdiv", "click:#k8", "click:#keq"]}


@pytest.fixture
def env(tmp_path):
    checks = tmp_path / "checks.json"
    checks.write_text(json.dumps({"good": [
        {"id": "g1", "steps": ["click:#k1"], "observe": "#display", "expect": "1"},
        {"id": "g2", "steps": ["click:#k1", "click:#k8"], "observe": "#display", "expect": "18"}],
        "traps": [{"id": "t1", "steps": ["click:#k1", "click:#kdiv", "click:#k8", "click:#keq"],
                   "observe": "#display", "expect": "0.12"}]}))
    html = tmp_path / "revival.html"
    html.write_text(OLD, encoding="utf-8")
    prompts = []

    def go(reply):
        def ask(prompt):
            prompts.append(prompt)
            if isinstance(reply, Exception):
                raise reply
            return reply
        return run(CLAIM, VERDICT, html, "fake", log_path=tmp_path / "runs/appx/repairs.jsonl", checks=checks, ask=ask)

    return tmp_path, html, go, prompts


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def log(tmp_path):
    return [json.loads(x) for x in (tmp_path / "runs/appx/repairs.jsonl").read_text().splitlines()]


def test_patched(env):
    tmp_path, html, go, prompts = env
    event = go(f"Here:\n```html\n{GOOD_PATCH}```")
    assert event == {"type": "repair", "claim_id": "c03", "from_sha256": sha(OLD), "to_sha256": sha(GOOD_PATCH),
                     "decision": "patched", "reason": event["reason"]}
    assert (tmp_path / "revival.v2.html").read_text() == GOOD_PATCH
    assert html.read_text() == OLD
    assert log(tmp_path) == [event]
    # the builder is told the original's output and the steps, not the claim text
    assert '"0.12"' in prompts[0] and "click:#kdiv" in prompts[0] and "rounds to 0.13" not in prompts[0]


def test_rollback_when_regression_drops(env):
    tmp_path, html, go, _ = env
    event = go(BAD_PATCH)
    assert event["decision"] == "rollback" and "2 -> 1" in event["reason"]
    assert event["to_sha256"] == event["from_sha256"] == sha(OLD)
    assert not (tmp_path / "revival.v2.html").exists()
    assert html.read_text() == OLD
    assert log(tmp_path) == [event]


@pytest.mark.parametrize("reply, why", [
    (OLD, "changed nothing"),
    (RuntimeError("codex exited 1"), "no usable HTML"),
    ("I could not fix it.", "no usable HTML"),
    (OLD.replace('id="k8"', 'id="kx"'), "dropped element IDs"),
    (OLD.replace("* 100) / 100", "* 100) / 100 + 1"), "did not reproduce"),
])
def test_unsworn(env, reply, why):
    tmp_path, html, go, _ = env
    event = go(reply)
    assert event["decision"] == "unsworn" and why in event["reason"]
    assert event["to_sha256"] == event["from_sha256"]
    assert not (tmp_path / "revival.v2.html").exists()
    assert len(log(tmp_path)) == 1


def test_log_appends(env):
    tmp_path, _, go, _ = env
    go(OLD)
    go(GOOD_PATCH)
    assert [e["decision"] for e in log(tmp_path)] == ["unsworn", "patched"]


def test_nothing_to_repair():
    for change in ({"match": True}, {"flaky": True}):
        with pytest.raises(ValueError, match="Nothing to repair"):
            repair(CLAIM, {**VERDICT, **change}, OLD, lambda p: OLD, lambda h: 0)


def test_pure_core_uses_injected_functions():
    scores = {OLD: 5, GOOD_PATCH: 5}
    keep, event = repair(CLAIM, VERDICT, OLD, lambda p: GOOD_PATCH, scores.get, lambda h, t: (True, "0.12"))
    assert keep == GOOD_PATCH and event["decision"] == "patched"
    scores[GOOD_PATCH] = 4
    keep, event = repair(CLAIM, VERDICT, OLD, lambda p: GOOD_PATCH, scores.get, lambda h, t: (True, "0.12"))
    assert keep == OLD and event["decision"] == "rollback"


def test_prompt_has_no_extra_verdict_data():
    prompt = make_prompt(CLAIM, {**VERDICT, "secret": "ORIGINAL-SOURCE"}, OLD)
    assert "ORIGINAL-SOURCE" not in prompt and OLD in prompt


def test_check_revival_json(tmp_path, capsys):
    html = tmp_path / "r.html"
    html.write_text(OLD, encoding="utf-8")
    checks = tmp_path / "c.json"
    checks.write_text(json.dumps({"good": [{"id": "g", "steps": ["click:#k1"], "observe": "#display", "expect": "1"}],
                                  "traps": [{"id": "t", "steps": [], "observe": "#display", "expect": "nope"}]}))
    assert check_revival(html, checks, as_json=True) == 1
    assert json.loads(capsys.readouterr().out) == [{"id": "g", "kind": "good", "passed": True},
                                                   {"id": "t", "kind": "trap", "passed": False}]
    r = subprocess.run([sys.executable, str(ROOT / "revive/check_revival.py"), "--json", "--checks", str(checks), str(html)],
                       capture_output=True, text=True)
    assert json.loads(r.stdout)[1]["kind"] == "trap"


def test_case_file_cli_regression_result(tmp_path):
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps([{"id": "g", "kind": "good", "passed": False}, {"id": "t", "kind": "trap", "passed": False}]))
    cmd = [sys.executable, str(ROOT / "eval/case_file.py"), str(ROOT / "fixtures/claims.json"),
           str(ROOT / "fixtures/verdicts.json"), "app1"]
    with_reg = subprocess.run(cmd + ["--regression-result", str(reg)], capture_output=True, text=True, check=True).stdout
    assert "  false_strikes: 1\n  false_strikes_of: 1\n  traps_caught: 1\n  traps_of: 1\n" in with_reg
    assert "  false_strikes: null\n" in subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
