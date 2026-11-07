import io
import json

from agents.mesh import voice


def test_persona_fake_offline_and_cleanup(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append((req.full_url, timeout, json.loads(req.data)))
        body = {"choices": [{"message": {"content": '<think>plan</think> "Objection!\n[seance] {"x":1}\n 3 strikes."'}}]}
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr(voice.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("SEANCE_FAKE_LLM", "1")
    assert voice.persona("mcclusky", "x", "canned") == "canned" and not calls
    monkeypatch.delenv("SEANCE_FAKE_LLM")
    assert voice.persona("hoot", "x", "offline line") == "offline line" and not calls  # no ASI1_API_KEY
    monkeypatch.setenv("ASI1_API_KEY", "test-key-not-real")
    assert voice.persona("mcclusky", "x", "fallback") == "Objection! 3 strikes."
    url, timeout, body = calls[0]
    assert url == voice.ASI1_URL and timeout == 25 and (body["model"], body["reasoning_effort"]) == ("asi1", "low")

    def down(req, timeout):
        raise OSError("no network")
    monkeypatch.setattr(voice.urllib.request, "urlopen", down)
    assert voice.persona("hoot", "x") == voice.OFFLINE["hoot"]


def test_fit_never_cuts_mid_sentence():
    assert voice.fit("Short and sweet.") == "Short and sweet."
    long = "Fidelity stays 100 with 0 of 34 differing. My credibility still leads, 1000 to 922, and it is climbing fast on appeal, Your Honor."
    assert voice.fit(long) == "Fidelity stays 100 with 0 of 34 differing."
    assert voice.fit(" ".join(["word"] * 30)) == ""
