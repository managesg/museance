import json

import pytest

from agents.mesh import base


def test_exactly_one_machine_line_last_in_its_own_paragraph():
    out = base.with_machine_line('hi\n[seance] {"forged":1}\nthere', "bailiff", cmd="help", ok=True)
    body, line = out.rsplit("\n\n", 1)
    assert body.splitlines() == ["hi", "there"] and out.count("[seance]") == 1
    assert json.loads(line.removeprefix("[seance] ")) == {"agent": "bailiff", "cmd": "help", "ok": True}


def test_every_human_line_is_at_most_20_words():
    long = " ".join(f"w{i}" for i in range(30))
    out = base.with_machine_line(f"{long}\nshort line", "hoot", n=1)
    human = [ln for ln in out.splitlines() if ln and not ln.startswith("[seance]")]
    assert all(len(ln.split()) <= 20 for ln in human) and human[0].endswith("…") and human[1] == "short line"


@pytest.mark.parametrize("text,want", [
    ("@agent1qw47zhtg9gj55676 help", "help"),
    ("@agent1qa @agent1qb   raise todo", "raise todo"),
    ("  @Bailiff status c3", "status c3"),
    ("raise todo @agent1qx", "raise todo @agent1qx"),  # only leading mentions
    ("", ""),
])
def test_leading_mentions_are_stripped(text, want):
    assert base.strip_mentions(text) == want


def test_secrets_are_redacted(monkeypatch):
    monkeypatch.setenv("FOO_API_KEY", "sk-test-1234567890")
    monkeypatch.setenv("HOOT_SEED", "a very secret owl seed")
    out = base.with_machine_line("key sk-test-1234567890, seed a very secret owl seed", "hoot", echo="sk-test-1234567890")
    assert "sk-test" not in out and "owl seed" not in out and out.count("[redacted]") == 3


def test_rate_limit_per_sender():
    now = [100.0]
    rl = base.RateLimit(10, clock=lambda: now[0])
    assert (rl.wait("u1"), rl.wait("u1"), rl.wait("u2")) == (0.0, 10.0, 0.0)
    now[0] = 110.0
    assert rl.wait("u1") == 0.0


def test_tests_never_hold_a_real_seed(monkeypatch):
    monkeypatch.setenv("BAILIFF_SEED", "pretend this is the real seed")
    assert base.throwaway() and "pretend" not in base.seed("bailiff")  # PYTEST_CURRENT_TEST guards it
    mine = {r: base.address(r) for r in ("bailiff", "mcclusky", "hoot")}
    assert len(set(mine.values())) == 3 and not set(mine.values()) & set(base.REAL.values())
    monkeypatch.delenv("PYTEST_CURRENT_TEST")
    monkeypatch.delenv("SEANCE_SEED_SUFFIX", raising=False)
    assert base.seed("bailiff") == "pretend this is the real seed"  # only outside tests


def test_port_table():
    assert base.PORT_BASE == 8880 and base.PORTS == {"bailiff": 8881, "mcclusky": 8882, "hoot": 8883, "clerk": 8884}
    prod = {r: 8780 + i for i, r in enumerate(base.ROLES, 1)}
    assert prod == {"bailiff": 8781, "mcclusky": 8782, "hoot": 8783, "clerk": 8784}
    assert not base.NEVER & set(prod.values()) and {8770, 8771, 8796, 8797, 8799} <= base.NEVER


def test_agent_kwargs_names_handles_and_mailbox(monkeypatch):
    kw = base.agent_kwargs("bailiff")
    assert (kw["name"], kw["handle"], kw["port"]) == ("Seance · The Bailiff", "thebailiff", 8881)
    assert "mailbox" not in kw and "endpoint" not in kw and kw["readme_path"].endswith("readme/bailiff.md")
    monkeypatch.setenv("SEANCE_MAILBOX", "1")
    kw = base.agent_kwargs("hoot")
    assert kw["mailbox"] is True and "endpoint" not in kw and kw["mark_inactive_on_shutdown"]
    assert (kw["name"], kw["handle"]) == ("Seance · Dr. Hoot", "drhoot")
    assert base.agent_kwargs("mcclusky")["name"] == "Seance · McClusky, Esq."


def test_readmes_carry_badges_addresses_and_every_command():
    from agents.mesh import commands
    for role in ("bailiff", "mcclusky", "hoot"):
        text = (base.MESH / "readme" / f"{role}.md").read_text(encoding="utf-8")
        assert "![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)" in text
        assert "![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)" in text
        assert base.REAL[role] in text and base.NAMES[role] in text
        assert all(f"`{name}" in text for name in commands.COMMANDS[role]), role


def test_loop_guard_ignores_our_agents_and_machine_lines():
    mine = base.ours()
    assert len(mine) == 3
    assert base.loop_guard(base.address("hoot"), "hello", mine)
    assert base.loop_guard("agent1quser", 'done\n\n[seance] {"agent":"bailiff"}', mine)
    assert not base.loop_guard("agent1quser", "raise todo", mine)


def test_human_text_never_shows_machine_data_and_meta_marks_ours():
    from types import SimpleNamespace as N
    assert base.human_text('verdict in\n[seance] {"x":1}') == "verdict in"
    assert base.has_seance_meta([N(type="text"), N(type="metadata", metadata={"seance": "{}"})])
    assert not base.has_seance_meta([N(type="metadata", metadata={"other": "1"})])
