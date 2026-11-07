"""Shared plumbing for the three agents (and the Clerk CLI): env, ports, seeds, the agent factory, the chat
protocol, the [seance] machine line, a per-sender rate limiter and the ASI-1 persona voice.

uAgents is imported only inside make_agent, chat_protocol and send_text, so the --no-mesh path never needs it.
Env flags: SEANCE_MAILBOX=1 (Agentverse mailbox; default local-only), SEANCE_FAKE_LLM=1 (no model calls),
SEANCE_FAKE_BENCH=1 (no browser, see case.FakeBench).
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import pathlib
import re
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
MESH = ROOT / "agents" / "mesh"
for _p in (ROOT, ROOT / "agents"):  # same trick as agents/medium.py, so `python agents/mesh/x.py` works too
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import llm  # noqa: E402 - P2's .env reader, the same module object agents/medium.py uses

from agents.mesh.captions import DEADPAN, OFFLINE  # noqa: E402

log = logging.getLogger("seance")

ROLES = ("mcclusky", "hoot", "bailiff", "clerk")
PORTS = {"mcclusky": 8771, "hoot": 8772, "bailiff": 8773, "clerk": 8774}
SEED_ENV = {r: f"{r.upper()}_SEED" for r in ROLES}
CLERK_SEED = "seance clerk cli public identity 0001"  # the Clerk holds nothing worth stealing; a public seed is fine
NAMES = {"mcclusky": "Seance · McClusky, Esq.", "hoot": "Seance · Dr. Hoot", "bailiff": "Seance · The Bailiff",
         "clerk": "Seance · The Clerk"}
DESCRIPTIONS = {
    "mcclusky": "Counsel for dead web apps. Say 'raise todo': he swears claims about the app with a bond on each, "
                "then argues with Dr. Hoot. ASI-1 brain.",
    "hoot": "Owl skeptic. Seals edge-case attacks on a revived app before anyone testifies, then gloats about "
            "every STRUCK claim, with numbers.",
    "bailiff": "Clerk of the Seance fidelity court. Runs the case, checks every seal, writes the hash-chained "
               "ledger. No opinion, no model.",
    "clerk": "Command-line client that starts Seance cases.",
}
AVATAR = "https://raw.githubusercontent.com/vihuynh72/aie-code/main/agents/mesh/avatars/{}.png"  # live once on main
ASI1_URL = "https://api.asi1.ai/v1/chat/completions"
PERSONAS = {
    "mcclusky": "You are McClusky, Esq., a flamboyant, slightly shady defense lawyer in SEANCE, a court that tests "
                "resurrected web apps. You represent the dead app and swore claims about how it behaved, with "
                "credibility points on the line. Your rival is Dr. Hoot, a smug owl skeptic. The Bailiff has no "
                "opinion and no model. Reply in one or two short sentences, in character, plain text, no markdown. "
                "Use only numbers you are given; never invent numbers.",
    "hoot": "You are Dr. Hoot, a smug, pedantic owl and professional skeptic in SEANCE, a court that tests "
            "resurrected web apps. You seal edge-case attacks before anyone testifies and you love catching "
            "McClusky, Esq. overselling his claims. Reply in one or two short sentences, in character, plain text, "
            "no markdown. Use only numbers you are given; never invent numbers.",
}
SECRET_NAME = re.compile(r"(KEY|SEED|TOKEN|SECRET|PASSWORD|URI)$")


def load_env() -> None:
    """.env -> os.environ (setdefault). Values are never printed or logged."""
    llm._load_env()


def flag(name: str) -> bool:
    return os.environ.get(name) == "1"


def redact(text: str) -> str:
    """Scrub any secret env value (*_KEY, *_SEED, *_TOKEN, ...) from outgoing text."""
    for k, v in os.environ.items():
        if len(v) >= 8 and SECRET_NAME.search(k) and v in text:
            text = text.replace(v, "[redacted]")
    return text


def machine_line(agent: str, **data) -> str:
    return "[seance] " + json.dumps({"agent": agent, **data}, ensure_ascii=False, separators=(",", ":"), default=str)


def with_machine_line(text: str, agent: str, **data) -> str:
    """Reply text + exactly one machine line (any [seance] line already in the text is dropped)."""
    body = "\n".join(ln for ln in str(text).splitlines() if not ln.lstrip().startswith("[seance]")).strip()
    return redact(f"{body}\n{machine_line(agent, **data)}")


class RateLimit:
    """At most one action per key every `seconds` (the cross guardrail: one per sender every 10 s)."""

    def __init__(self, seconds: float = 10.0, clock=time.monotonic):
        self.seconds, self.clock, self.last = seconds, clock, {}

    def wait(self, key: str) -> float:
        """0.0 and the slot is taken; otherwise the seconds left (nothing recorded)."""
        now = self.clock()
        left = self.last[key] + self.seconds - now if key in self.last else 0.0
        if left > 0:
            return left
        self.last[key] = now
        return 0.0


def persona(role: str, prompt: str, fallback: str = "") -> str:
    """One short in-character reply from ASI-1. Blocking (urllib, 25 s): call it with asyncio.to_thread from a
    handler. Returns `fallback` (default: the role's offline line) with SEANCE_FAKE_LLM=1, without
    ASI1_API_KEY, offline, or on any error."""
    fallback = fallback or OFFLINE[role]
    if flag("SEANCE_FAKE_LLM"):
        return fallback
    load_env()
    key = os.environ.get("ASI1_API_KEY")
    if not key:
        return fallback
    body = {"model": "asi1", "reasoning_effort": "low",
            "messages": [{"role": "system", "content": PERSONAS[role]}, {"role": "user", "content": prompt}]}
    req = urllib.request.Request(ASI1_URL, json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            text = json.load(r)["choices"][0]["message"]["content"] or ""
    except Exception as ex:  # noqa: BLE001 - the show goes on with the fallback line
        log.warning("ASI-1 persona call failed (%s); using the fallback line", type(ex).__name__)
        return fallback
    text = re.sub(r"(?s)<think>.*?</think>", "", text)
    text = " ".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("[seance]"))
    text = " ".join(text.split()).strip("\"' ")
    return redact(text[:400]) or fallback


# --- identities and the agent factory ---------------------------------------------------------------
def seed(role: str) -> str:
    load_env()
    value = os.environ.get(SEED_ENV[role]) or (CLERK_SEED if role == "clerk" else "")
    if not value:
        raise RuntimeError(f"{SEED_ENV[role]} is not set; add it to .env")
    return value


def address(role: str) -> str:
    from uagents_core.identity import Identity
    return Identity.from_seed(seed(role), 0).address


def local_url(role: str) -> str:
    return f"http://127.0.0.1:{PORTS[role]}/submit"


def peer_rules() -> dict[str, str]:
    """address -> local /submit URL for every role whose seed this process can see."""
    rules = {}
    for r in ROLES:
        try:
            rules[address(r)] = local_url(r)
        except RuntimeError:
            pass
    return rules


def agent_kwargs(role: str) -> dict:
    """Agent(...) arguments for one role, except resolve and loop (make_agent adds those)."""
    load_env()  # SEANCE_MAILBOX may live only in .env
    mailbox = role != "clerk" and flag("SEANCE_MAILBOX")
    readme = MESH / "readme" / f"{role}.md"
    kw = {"name": NAMES[role], "seed": seed(role), "port": PORTS[role], "description": DESCRIPTIONS[role],
          "readme_path": str(readme) if readme.is_file() else None,
          "avatar_url": AVATAR.format(role) if role != "clerk" else None,
          "report_events": False, "handle_messages_concurrently": True,  # a long case must not block chat acks
          "mark_inactive_on_shutdown": mailbox}
    if mailbox:
        kw["mailbox"] = True  # never together with endpoint=: uagents 0.26.1 then silently drops the mailbox
    # local-only: no endpoint either, so nothing is registered on the Almanac; peers reach us by peer_rules()
    return kw


def make_agent(role: str):
    """One agent per process, on its fixed port. Build it inside main(): judge() starts worker processes with
    spawn, which re-imports the main module."""
    from uagents import Agent
    from uagents.resolver import GlobalResolver, Resolver, RulesBasedResolver

    class LocalFirstResolver(Resolver):
        """Our agents by local rules; anyone else (ASI:One users) through the Almanac."""

        def __init__(self, rules):
            self._rules, self._global = RulesBasedResolver(rules), GlobalResolver()

        async def resolve(self, destination):
            address_, endpoints = await self._rules.resolve(destination)
            if endpoints:
                return address_, endpoints
            try:
                return await self._global.resolve(destination)
            except Exception:  # noqa: BLE001 - offline the Almanac lookup raises; ctx.send then reports FAILED
                return None, []

    class SeanceAgent(Agent):
        # shortcut: overrides private uagents 0.26.1 Agent._update_agent_status / _use_mailbox; re-check on upgrade
        async def _update_agent_status(self, active: bool):
            if not self._use_mailbox:
                return  # local-only agents are not on the Almanac; marking them (in)active is wrong
            try:  # offline this retries ~33 s and blocks startup handlers and Ctrl+C
                await asyncio.wait_for(super()._update_agent_status(active), 3)
            except asyncio.TimeoutError:
                self._logger.warning(f"Almanac status update (active={active}) gave up after 3 s")

    loop = asyncio.new_event_loop()  # explicit: Agent() has no current loop on Python 3.14+
    asyncio.set_event_loop(loop)
    return SeanceAgent(**agent_kwargs(role), resolve=LocalFirstResolver(peer_rules()), loop=loop)


# --- chat ------------------------------------------------------------------------------------------------
_ORDER: dict[str, asyncio.Lock] = {}


async def send_text(ctx, to: str, agent: str, text: str, **data):
    """One ChatMessage with exactly one machine line. Messages to one address leave in call order, even with
    handle_messages_concurrently (asyncio.Lock is FIFO)."""
    from uagents_core.contrib.protocols.chat import ChatMessage, TextContent
    async with _ORDER.setdefault(to, asyncio.Lock()):
        return await ctx.send(to, ChatMessage(content=[TextContent(text=with_machine_line(text, agent, **data))]))


def chat_protocol(role: str, handler):
    """Agent Chat Protocol (ASI:One, the Clerk, other agents). Acks every ChatMessage first, then calls
    handler(ctx, sender, text) -> reply: str, (str, dict of machine-line fields), an awaitable of either,
    or None for no reply. Include it with agent.include(proto, publish_manifest=flag("SEANCE_MAILBOX")): the
    manifest tells Agentverse and ASI:One about the protocol, and a local-only agent stays off the network."""
    from uagents import Protocol
    from uagents_core.contrib.protocols.chat import ChatAcknowledgement, ChatMessage, chat_protocol_spec

    proto = Protocol(spec=chat_protocol_spec)

    @proto.on_message(ChatMessage)
    async def _on_chat(ctx, sender: str, msg: ChatMessage):
        await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))
        text = msg.text().strip()
        if not text and any(c.type == "end-session" for c in msg.content):
            return
        try:
            out = handler(ctx, sender, text)
            if inspect.isawaitable(out):
                out = await out
        except Exception as ex:  # noqa: BLE001 - a chat user gets a line, not silence
            ctx.logger.exception("chat handler failed")
            out = (f"The court tripped over its robes ({type(ex).__name__}). Try: help. {DEADPAN}",
                   {"ok": False, "error": type(ex).__name__})
        if out:
            reply, data = (out, {}) if isinstance(out, str) else out
            await send_text(ctx, sender, role, reply, **data)

    @proto.on_message(ChatAcknowledgement)
    async def _on_ack(ctx, sender: str, msg: ChatAcknowledgement):
        pass

    return proto
