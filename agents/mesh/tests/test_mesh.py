"""The mesh for real: the Bailiff, McClusky and Dr. Hoot as three processes on the test port table (8881-8884),
offline (local resolver only, both fakes on, throwaway seeds, never the real .env, loopback only). The Clerk CLI
raises app1, a chat user raises it through McClusky and asks the Bailiff for the transcript. Plus
`run raise --no-mesh`, which needs no uAgents at all."""
import asyncio
import json
import socket
import subprocess
import sys
import time

import pytest

from agents.mesh import base, captions, case, run
from court.ledger import read, verify

ORDER = ["open", "sealed", "sworn", "revealed", "ruling", "remark", "remark"]
BOOT = """
import pathlib, sys
sys.path.insert(0, sys.argv[1])
import uagents.asgi
from agents.mesh import base, bailiff, hoot, mcclusky, run
uagents.asgi.HOST = "127.0.0.1"
base.load_env = lambda: None
role, args = sys.argv[2], sys.argv[3:]
if role == "run":
    sys.exit(run.main(args))
runs = pathlib.Path(args[0])
{"bailiff": lambda: bailiff.build(runs), "mcclusky": lambda: mcclusky.build(runs),
 "hoot": lambda: hoot.build(hoot.Hoot(runs, base.address("bailiff")))}[role]().run()
"""  # argv: repo root, then an agent role and runs/, or "run" and run.py's own arguments


def machine(text: str) -> dict:
    line = text.strip().splitlines()[-1]
    assert line.startswith("[seance] {"), line
    return json.loads(line.removeprefix("[seance] "))


def test_raise_no_mesh_prints_the_final_reply(runs, monkeypatch, capsys):
    monkeypatch.setattr(case, "RUNS", runs)
    assert run.main(["raise", "app1", "--no-mesh"]) == 0
    out, err = capsys.readouterr()
    assert err.splitlines() == list(case.PROGRESS.values())
    assert out.startswith("⚖️ The case: is the revived app1 the same app as the dead original?")
    m = machine(out)
    assert (m["agent"], m["cmd"], m["ok"], m["locked"], m["struck"], m["chain"]) == ("mcclusky", "raise", True, 3, 1, True)
    r = json.loads((runs / "app1" / "ruling.json").read_text())
    assert out == base.with_machine_line(captions.final_reply(r), "mcclusky", cmd="raise", **case.numbers(r)) + "\n"
    assert run.main(["raise", "pong", "--no-mesh"]) == 1
    assert "cannot raise 'pong'" in capsys.readouterr().out


def taken(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def chat(role: str, text: str, done=lambda replies: bool(replies), timeout: float = 120) -> list[str]:
    """Chat one line to an agent from a throwaway Clerk identity in this process; every reply, in order."""
    from uagents import Protocol
    from uagents_core.contrib.protocols.chat import (ChatAcknowledgement, ChatMessage, TextContent,
                                                     chat_protocol_spec)
    replies, heard = [], asyncio.Event()
    agent, proto = base.make_agent("clerk"), Protocol(spec=chat_protocol_spec)

    @proto.on_message(ChatMessage)
    async def _got(ctx, sender, msg):
        assert "[seance]" not in msg.text()  # humans never see machine data; it rides in MetadataContent
        meta = next((c.metadata["seance"] for c in msg.content if getattr(c, "type", "") == "metadata"), None)
        replies.append(msg.text() + (f"\n\n[seance] {meta}" if meta else ""))
        if done(replies):
            heard.set()

    @proto.on_message(ChatAcknowledgement)
    async def _ack(ctx, sender, msg):
        pass

    agent.include(proto)

    async def say(ctx):
        await ctx.send(base.address(role), ChatMessage(content=[TextContent(text=text)]))
        await heard.wait()
    try:
        run.visit(agent, say, timeout)
    finally:
        asyncio.set_event_loop(None)
    return replies


def test_three_agents_hear_a_case_over_the_mesh(runs, tmp_path, monkeypatch):
    ports = [base.PORTS[r] for r in (*run.AGENTS, "clerk")]
    assert ports == [8881, 8882, 8883, 8884]
    if busy := [p for p in ports if taken(p)]:
        pytest.skip(f"test ports {busy} are taken")
    import uagents.asgi
    monkeypatch.setattr(uagents.asgi, "HOST", "127.0.0.1")
    monkeypatch.setenv("SEANCE_MAILBOX", "0")
    monkeypatch.chdir(tmp_path)  # uagents keeps agent storage in the working directory
    logs = {r: tmp_path / f"{r}.log" for r in run.AGENTS}
    procs = [subprocess.Popen([sys.executable, "-c", BOOT, str(run.ROOT), r, str(runs)], stdout=logs[r].open("w"),
                              stderr=subprocess.STDOUT) for r in run.AGENTS]
    tails = lambda: "".join(f"\n--- {r}.log\n{p.read_text()[-3000:]}" for r, p in logs.items())  # noqa: E731
    try:
        end = time.monotonic() + 60
        while not all(taken(base.PORTS[r]) for r in run.AGENTS):
            assert time.monotonic() < end and all(p.poll() is None for p in procs), tails()
            time.sleep(0.2)
        clerk = subprocess.run([sys.executable, "-c", BOOT, str(run.ROOT), "run", "raise", "app1"],
                               capture_output=True, text=True, timeout=120)
        assert clerk.returncode == 0, clerk.stdout + clerk.stderr + tails()
        assert clerk.stdout.startswith("⚖️ The case: is the revived app1") and machine(clerk.stdout)["struck"] == 1
        path = runs / "app1" / "ledger.jsonl"
        assert verify(path)[0] and [e["type"][5:] for e in read(path) if e["type"].startswith("mesh.")] == ORDER

        # the ASI:One path: a chat user asks McClusky, who answers from inside his chat handler
        replies = chat("mcclusky", "@agent1q2ehsgka can you bring back the app1 app?",
                       done=lambda rs: any(t.startswith("⚖️") for t in rs))
        *progress, final = replies
        assert [p.split("\n\n")[0] for p in progress] == list(case.PROGRESS.values()), replies
        assert final.startswith("⚖️ The case: is the revived app1") and machine(final)["agent"] == "mcclusky"
        assert all(len(ln.split()) <= 20 for ln in final.splitlines() if not ln.startswith("[seance]"))

        (transcript,) = chat("bailiff", "transcript")
        assert "📜 Record" in transcript and "chain intact." in transcript and machine(transcript)["chain"] is True
        assert not [r for r, p in logs.items() if "manifest" in p.read_text().lower()]  # local-only: no Agentverse
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
