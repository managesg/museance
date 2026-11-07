"""One command for the Seance mesh: start the three agents, raise a case, list their addresses.

    agents/mesh/.venv/bin/python -m agents.mesh.run up [--mailbox]       # McClusky, Dr. Hoot, the Bailiff: 3 processes
    agents/mesh/.venv/bin/python -m agents.mesh.run raise todo            # the Clerk: a case through the Bailiff
    agents/mesh/.venv/bin/python -m agents.mesh.run raise todo --no-mesh  # the same case in this process, no uAgents
    agents/mesh/.venv/bin/python -m agents.mesh.run addresses             # names and addresses, never seeds

`raise` prints one "[event] caption" line per case event and ends with exactly one [seance] machine line holding
the ruling's numbers; it exits 0 only when the case closed. Run from the repo root: the agents read runs/ there.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import pathlib
import signal
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from agents.mesh import base, captions, case  # noqa: E402 - none of these import uAgents: --no-mesh runs without it

AGENTS = ("mcclusky", "hoot", "bailiff")
CASE_S = 900  # the Bailiff alone may wait 8 minutes on the parties (seal, testimony, reveal, remarks), then the court
KEEP = ("case_id", "app", "error", "counts", "claims", "attacks", "refused", "catches", "fidelity", "brier",
        "credibility_start", "credibility_end", "funniest", "chain")


def show(event: str, text: str):
    print(f"[{event}] {text}", flush=True)


def finish(r: dict, event: str) -> int:
    """The last line, for scripts: one machine line with the ruling's numbers. 0 only when the case closed."""
    print(base.machine_line("clerk", event=event, **{k: r[k] for k in KEEP if k in r}), flush=True)
    return 0 if event == "closed" and not r.get("error") else 1


def _missing(roles) -> list[str]:
    return [base.SEED_ENV[r] for r in roles if not os.environ.get(base.SEED_ENV[r])]


# --- up -------------------------------------------------------------------------------------------------------
def up(mailbox: bool) -> int:
    """McClusky, Dr. Hoot and the Bailiff, one process each, until Ctrl+C or until one of them stops."""
    def stop(*_):
        raise KeyboardInterrupt

    for sig in (signal.SIGTERM, signal.SIGHUP):  # `kill` or a closed terminal must not orphan the agents
        signal.signal(sig, stop)
    procs = [subprocess.Popen([sys.executable, "-m", f"agents.mesh.{r}", *(["--mailbox"] if mailbox else [])],
                              cwd=ROOT, start_new_session=True)  # own session: Ctrl+C reaches them once, from us
             for r in AGENTS]
    print(f"Seance mesh up, {'on the Agentverse mailbox' if mailbox else 'local-only'}: "
          + ", ".join(f"{captions.NAMES[r]} on :{base.PORTS[r]}" for r in AGENTS)
          + ". Raise a case: python -m agents.mesh.run raise todo. Ctrl+C stops all three.", flush=True)
    code = 0
    try:
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
        print("An agent stopped, so the mesh stops.", file=sys.stderr, flush=True)
        code = 1
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            if p.poll() is None:
                p.send_signal(signal.SIGINT)  # uvicorn's graceful stop; a mailbox agent then marks itself inactive
        end = time.monotonic() + 10
        for p in procs:
            try:
                p.wait(max(0.1, end - time.monotonic()))
            except subprocess.TimeoutExpired:  # e.g. the Bailiff mid-case, waiting out a party that is gone
                p.kill()
                p.wait()
    return code


# --- raise ----------------------------------------------------------------------------------------------------
async def _listening(port: int, seconds: float = 10):
    end = time.monotonic() + seconds
    while True:
        try:
            (await asyncio.open_connection("127.0.0.1", port))[1].close()
            return
        except OSError:
            if time.monotonic() > end:
                raise TimeoutError(f"port {port} never opened") from None
            await asyncio.sleep(0.05)


def visit(agent, script, timeout: float):
    """Run a short-lived Clerk agent (port 8774): once its own server listens, await script(ctx) for at most
    `timeout` s, then stop the agent. -> what the script returned, None on a timeout."""
    out = {}

    @agent.on_event("startup")
    async def _go(ctx):
        try:
            await _listening(base.PORTS["clerk"])  # an answer must not arrive before our server does
            out["result"] = await asyncio.wait_for(script(ctx), timeout)
        except TimeoutError as ex:
            ctx.logger.warning(f"gave up: {str(ex) or f'nothing more after {timeout} s'}")
        finally:
            # shortcut: private uagents 0.26.1 Agent._server; should_exit is uvicorn's graceful stop (the Ctrl+C
            # path), so run() returns and the port is free again. Re-check on upgrade.
            agent._server.server.should_exit = True

    agent.run()
    return out.get("result")


def clerk(app: str) -> int:
    """The Clerk: OpenCase to the Bailiff from a short-lived agent (port 8774, a public seed), then every Progress
    is printed; the machine line holds the Ruling the Bailiff sends its front door."""
    from uagents_core.types import DeliveryStatus

    from agents.mesh.models import OpenCase, Progress, Ruling

    bailiff, agent = base.address("bailiff"), base.make_agent("clerk")
    got, over = {"event": "", "ruling": {}}, asyncio.Event()

    @agent.on_message(Progress)
    async def _progress(ctx, sender: str, p: Progress):
        if sender == bailiff:
            show(p.event, p.text)
            if p.event in ("closed", "adjourned"):
                got["event"] = p.event
                over.set()

    @agent.on_message(Ruling)
    async def _ruling(ctx, sender: str, r: Ruling):
        if sender == bailiff:
            got["ruling"] = r.dict()

    async def open_case(ctx):
        sent = await ctx.send(bailiff, OpenCase(app=app))
        if sent.status == DeliveryStatus.FAILED:
            show("adjourned", f"The Bailiff did not answer at {base.local_url('bailiff')} ({sent.detail}). "
                              "Start the agents first: python -m agents.mesh.run up")
            return
        await over.wait()

    visit(agent, open_case, CASE_S)
    return finish(got["ruling"] or {"app": app, "error": "no ruling"}, got["event"] or "adjourned")


def raise_here(app: str) -> int:
    """--no-mesh: Dr. Hoot and McClusky in this process (case.run_case), which writes runs/<app>/ledger.jsonl."""
    sink = case.ledger_sink(app, case.RUNS)

    def on_event(event: str, payload: dict, caption: str):
        sink(event, payload, caption)
        show(event, captions.ruling_text(payload) if event == "ruling" else caption)

    try:
        r = case.run_case(app, on_event=on_event, runs=case.RUNS)
    except case.MissingInput:
        show("adjourned", captions.refusal(app, case.apps(case.RUNS)))
        return finish({"app": app, "error": "no ruling"}, "adjourned")
    return finish(r, "adjourned" if r.get("error") else "closed")


# --- addresses ------------------------------------------------------------------------------------------------
def addresses() -> int:
    missing = _missing(AGENTS)
    for r in AGENTS:
        env = base.SEED_ENV[r]
        print(f"{base.NAMES[r]:<24} {f'{env} is not set' if env in missing else base.address(r)}")
    return 1 if missing else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m agents.mesh.run", description="The Seance mesh from one command.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_up = sub.add_parser("up", help="start McClusky, Dr. Hoot and the Bailiff, one process each")
    p_up.add_argument("--mailbox", action="store_true", help="also on the Agentverse mailbox, for ASI:One "
                                                            "(same as SEANCE_MAILBOX=1)")
    p_raise = sub.add_parser("raise", help="raise a case on an app and print it as it happens")
    p_raise.add_argument("app")
    p_raise.add_argument("--no-mesh", action="store_true", help="run the case in this process, without uAgents")
    sub.add_parser("addresses", help="print the three agents' names and addresses")
    a = ap.parse_args(argv)
    base.load_env()
    if a.cmd == "addresses":
        return addresses()
    if a.cmd == "raise" and a.no_mesh:
        return raise_here(a.app)
    missing = _missing(AGENTS if a.cmd == "up" else ["bailiff"])
    if missing:
        print(f"{', '.join(missing)} not set: add them to .env (see .env.example).", file=sys.stderr)
        return 2
    return up(a.mailbox or base.flag("SEANCE_MAILBOX")) if a.cmd == "up" else clerk(a.app)


if __name__ == "__main__":
    sys.exit(main())
