"""The mesh for real: McClusky, Dr. Hoot and the Bailiff as three processes on the port table, offline (local
resolver only, both fakes on, throwaway seeds, never the real .env, loopback only). The Clerk CLI raises app1 and a
chat user asks the Bailiff for the status. Plus `run raise --no-mesh`, which needs no uAgents at all."""
import asyncio
import importlib.util
import json
import socket
import subprocess
import sys
import time

import pytest

from agents.mesh import base, case, run
from court.ledger import read, verify

SEEDS = {"MCCLUSKY_SEED": "mesh test seed mcclusky 0001", "HOOT_SEED": "mesh test seed hoot 0001",
         "BAILIFF_SEED": "mesh test seed bailiff 0001"}  # not test_bailiff's: agents built in-process stay registered
ORDER = ["open", "summon", "sealed", "summon", "testimony", "summon", "reveal", "court", "ruling", "remark", "remark",
         "closed"]
APP1 = {"LOCKED": 3, "STRUCK": 1, "FABRICATED": 1, "UNSWORN": 0}
BOOT = """
import pathlib, sys
sys.path.insert(0, sys.argv[1])
import uagents.asgi
from agents.mesh import base, bailiff, hoot, mcclusky, run
uagents.asgi.HOST = "127.0.0.1"
base.llm._load_env = lambda: None
role, args = sys.argv[2], sys.argv[3:]
if role == "run":
    sys.exit(run.main(args))
runs = pathlib.Path(args[0])
{"bailiff": lambda: bailiff.build(runs), "mcclusky": lambda: mcclusky.build(runs),
 "hoot": lambda: hoot.build(hoot.Hoot(runs, base.address("bailiff")))}[role]().run()
"""  # argv: repo root, then an agent role and runs/, or "run" and run.py's own arguments


def machine(line: str) -> dict:
    assert line.startswith("[seance] {"), line
    return json.loads(line.removeprefix("[seance] "))


def events(out: str) -> list[str]:
    return [ln[1:ln.index("]")] for ln in out.splitlines() if ln.startswith("[") and not ln.startswith("[seance]")]


def test_raise_no_mesh_runs_the_case_here(runs, monkeypatch, capsys):
    monkeypatch.setattr(case, "RUNS", runs)
    assert run.main(["raise", "app1", "--no-mesh"]) == 0
    out = capsys.readouterr().out
    assert events(out) == ORDER and "LOCKED 3 | STRUCK 1 | FABRICATED 1 | UNSWORN 0" in out
    m = machine(out.splitlines()[-1])
    assert (m["agent"], m["event"], m["counts"], m["credibility_end"]) == ("clerk", "closed", APP1, 963)
    path = runs / "app1" / "ledger.jsonl"
    assert verify(path)[0] and [e["type"][5:] for e in read(path) if e["type"].startswith("mesh.")] == ORDER
    assert run.main(["raise", "pong", "--no-mesh"]) == 1
    out = capsys.readouterr().out
    assert "cannot raise 'pong'" in out and machine(out.splitlines()[-1])["event"] == "adjourned"


def taken(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def chat(role: str, text: str) -> str:
    """One chat line to an agent from the Clerk's identity, in this process. -> the first reply's text."""
    from uagents_core.contrib.protocols.chat import ChatMessage, TextContent
    replies, heard = [], asyncio.Event()
    agent = base.make_agent("clerk")
    agent.include(base.chat_protocol("clerk", lambda ctx, sender, reply: replies.append(reply) or heard.set()))

    async def say(ctx):
        await ctx.send(base.address(role), ChatMessage(content=[TextContent(text=text)]))
        await heard.wait()
    try:
        run.visit(agent, say, 30)
    finally:
        asyncio.set_event_loop(None)
    return replies[0] if replies else ""


@pytest.mark.skipif(importlib.util.find_spec("uagents") is None, reason="uagents is not installed")
def test_three_agents_hear_a_case_over_the_mesh(runs, tmp_path, monkeypatch):
    if busy := [p for p in base.PORTS.values() if taken(p)]:
        pytest.skip(f"ports {busy} are taken (are the Seance agents up?)")
    import uagents.asgi
    monkeypatch.setattr(uagents.asgi, "HOST", "127.0.0.1")
    for k, v in {**SEEDS, "SEANCE_MAILBOX": "0"}.items():  # the subprocesses inherit these, and both fakes
        monkeypatch.setenv(k, v)
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
        assert events(clerk.stdout) == ORDER and "Funniest strike: c03" in clerk.stdout
        r = machine(clerk.stdout.splitlines()[-1])  # from the Ruling message the Bailiff sent the Clerk
        assert (r["event"], r["counts"], r["refused"], r["error"], r["credibility_end"]) == ("closed", APP1, 0, "", 963)

        path = runs / "app1" / "ledger.jsonl"
        types = [e["type"] for e in read(path)]
        assert verify(path) == (True, f"{len(types)} events, chain intact")
        assert [t[5:] for t in types if t.startswith("mesh.")] == ORDER
        court = types[types.index("mesh.court") + 1: types.index("mesh.ruling")]
        assert court == ["commit"] * 80 + ["verdict"] * 80 + ["lock"] * 5  # judge()'s own events, in place

        *body, line = chat("bailiff", "status").splitlines()
        status = machine(line)
        assert (status["agent"], status["cmd"], status["case_id"], status["counts"]) == ("bailiff", "status",
                                                                                          r["case_id"], APP1)
        assert body[0] == f"RULING, case {r['case_id']} (app1)"
        assert not [role for role, p in logs.items() if "manifest" in p.read_text().lower()]  # local-only: no Agentverse
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
