import asyncio
import io
import json
import logging
import re
import urllib.error

from agents.mesh import captions, case, hoot, voice
from agents.mesh.models import RemarkRequest

KEY = "test-key-not-real"
RULING = {"app": "todo", "counts": {"LOCKED": 15, "STRUCK": 1, "FABRICATED": 0, "UNSWORN": 0}, "claims": 16,
          "differ": 0, "judged": 36, "fidelity": 100, "credibility_start": 1000, "credibility_end": 930,
          "struck": [{"id": "c07", "text": "An empty task can be created (reported as a bug): clicking #add with an "
                      "empty input shows an item with no text in the list.", "expect": "", "bond": 198,
                      "confidence": 0.8906, "original": "ERROR:observe #todo li: TimeoutError"}]}


def asi1(monkeypatch, *replies):
    """urlopen answers with these replies in turn (an exception is raised); returns the request bodies sent."""
    sent, queue = [], list(replies)

    def urlopen(req, timeout):
        sent.append({"url": req.full_url, "timeout": timeout, **json.loads(req.data)})
        reply = queue.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": reply}}]}).encode())
    monkeypatch.setattr(voice.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(voice, "PAUSE", 0)
    monkeypatch.setenv("ASI1_API_KEY", KEY)
    return sent


def test_persona_fake_offline_and_cleanup(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="seance")
    sent = asi1(monkeypatch, '<think>plan</think> "Objection!\n[seance] {"x":1}\n 3 strikes."')
    monkeypatch.setenv("SEANCE_FAKE_LLM", "1")
    assert voice.persona("mcclusky", "Facts: 3 strikes.", "canned") == "canned" and not sent
    monkeypatch.delenv("SEANCE_FAKE_LLM")
    monkeypatch.delenv("ASI1_API_KEY")
    assert voice.persona("hoot", "x", "offline line") == "offline line" and not sent
    assert "no ASI1_API_KEY" in caplog.text
    monkeypatch.setenv("ASI1_API_KEY", KEY)
    assert voice.persona("mcclusky", "Facts: 3 strikes.", "fallback") == "Objection! 3 strikes."
    body = sent[0]
    assert (body["url"], body["timeout"], body["model"], body["reasoning_effort"]) == (voice.ASI1_URL, 20, "asi1", "low")
    assert "at most 22 words" in body["messages"][0]["content"]
    assert voice.clean('“Hoo, no.”') == "Hoo, no." and voice.clean('"Hoo," he said, "no."') == '"Hoo," he said, "no."'


def test_one_stricter_retry_then_the_scripted_line_with_a_warning(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="seance")
    facts = "Facts: 7 of 31 behaviors differ, fidelity 77."
    busy = urllib.error.HTTPError(voice.ASI1_URL, 429, "Too Many Requests", {}, None)
    sent = asi1(monkeypatch, busy, "Hoo, 7 of 31 differ.")
    assert voice.persona("hoot", facts, "scripted") == "Hoo, 7 of 31 differ." and not caplog.text
    assert voice.STRICT.format("HTTP 429") in sent[1]["messages"][0]["content"]
    assert "refused" not in sent[0]["messages"][0]["content"]
    asi1(monkeypatch, " ".join(["hoo"] * 40), "Hoo, 8 of 31 differ.")  # too long, then a number not in the facts
    assert voice.persona("hoot", facts, "scripted") == "scripted"
    assert "too long, 40 words; retry: numbers not in the facts: 8" in caplog.text
    sent = asi1(monkeypatch, TimeoutError("timed out"), "<think>nothing to say</think>")
    assert voice.persona("mcclusky", facts) == voice.OFFLINE["mcclusky"] and len(sent) == 2
    assert "TimeoutError; retry: an empty reply" in caplog.text and KEY not in caplog.text


def test_fit_keeps_30_words_and_cuts_only_at_a_sentence_or_clause_end():
    ok = " ".join(["word"] * 30)
    assert voice.fit(ok) == ok
    long = ("Hoo, counselor, you swore an empty task could exist, yet nothing appeared, so your 198 points vanish "
            "like your dignity, and frankly the owl union demands a recount of every feather.")
    assert voice.fit(long) == ("Hoo, counselor, you swore an empty task could exist, yet nothing appeared, so your "
                               "198 points vanish like your dignity.")
    assert voice.fit(" ".join(["word"] * 40)) == ""
    assert voice.fit("Five words, then nothing " + " ".join(["more"] * 30)) == ""  # the cut would keep 2 words
    assert voice.fit("My credibility went from 1,000 to 930 " + " ".join(["and"] * 30)) == ""  # never mid-number


def test_numbers_in_digits_and_words():
    assert voice.numbers("1,000 points, 0.870 and 77% of eleven; app1, c07 and no one") == {"1000", "0.87", "77", "11"}


def test_the_voices_get_plain_facts_and_the_scripted_lines_show_no_ids(monkeypatch):
    sent = asi1(monkeypatch, "Hoo! You said an empty task can be made, and nothing appeared.",
                "Feathers, Dr. Hoot: 15 of my 16 claims held up.", "Hoo. 1 false claim is 1 too many.")
    assert voice.hoot_line(RULING) == "Hoo! You said an empty task can be made, and nothing appeared."
    prompt = sent[0]["messages"][1]["content"]
    assert "an empty task can be created" in prompt and "showed nothing" in prompt and "16 claims" in prompt
    assert not re.search(r"c07|ERROR|#|no such element|locked|struck|fidelity|credibility", prompt)  # plain facts
    answer = voice.mcclusky_line(RULING, "Hoo! taunt")
    assert answer == "Feathers, Dr. Hoot: 15 of my 16 claims held up."
    assert 'Dr. Hoot just said: "Hoo! taunt"' in sent[1]["messages"][1]["content"]
    assert voice.hoot_line(RULING, answer) == "Hoo. 1 false claim is 1 too many."
    assert f'just said: "{answer}"' in sent[2]["messages"][1]["content"]
    assert captions.taunt(RULING) == ("Caught you, counselor! You said an empty task can be created, but the real "
                                      "app showed nothing.")
    for r in (RULING, {**RULING, "struck": [], "differ": 7, "fidelity": 77}, {**RULING, "struck": []}):
        for line in (captions.taunt(r), captions.rebuttal(r), captions.objection(r)):
            assert len(line.split()) < 20 and not re.search(r"\bc\d\d\b|ERROR|no such element|#", line), line
            assert voice.numbers(line) <= voice.numbers(voice.facts(r)), line


class Ctx:
    logger = logging.getLogger("test")

    def __init__(self):
        self.sent = []

    async def send(self, to, msg):
        self.sent.append((to, msg))


def test_hoot_taunts_and_rebuts_in_his_own_voice(monkeypatch):
    heard = []
    monkeypatch.setattr(voice, "hoot_line", lambda r, answer="": heard.append(answer) or "an ASI-1 line")
    owl, ctx = hoot.Hoot(bailiff="agent1qbailiff"), Ctx()
    for answer in ("", "McClusky's answer"):
        req = RemarkRequest(case_id="t", app="todo", ruling=RULING, answer=answer)
        asyncio.run(owl.on_remark(ctx, "agent1qbailiff", req))
    assert heard == ["", "McClusky's answer"] and [m.text for _, m in ctx.sent] == ["an ASI-1 line"] * 2


def test_hear_keeps_remarks_up_to_30_words_and_logs_every_scripted_one(runs, caplog):
    caplog.set_level(logging.WARNING, logger="seance")

    class Wordy(case.LocalParties):
        async def remark(self, speaker, case_id, app, r, answer=""):
            return " ".join(["hoo"] * 31 if speaker == "hoot" else ["objection"] * 30)

    class Mute(case.LocalParties):
        async def remark(self, *_):
            raise case.CaseError("Dr. Hoot did not answer")

    inp = case.load_inputs("app1", runs)
    r = asyncio.run(case.hear("app1", Wordy(inp, runs), runs=runs, case_id="app1-w", inputs=inp))
    assert r["remarks"] == {"hoot": captions.taunt(r), "mcclusky": " ".join(["objection"] * 30)}
    assert "hoot's remark (31 words)" in caplog.text
    r = asyncio.run(case.hear("app1", Mute(inp, runs), runs=runs, case_id="app1-m", inputs=inp))
    assert r["remarks"] == {"hoot": captions.taunt(r), "mcclusky": captions.objection(r)}
    assert "mcclusky's remark (CaseError: Dr. Hoot did not answer)" in caplog.text
    assert all(len(ln.split()) <= 20 for ln in r["record"])  # the scripted lines keep every caption one line
