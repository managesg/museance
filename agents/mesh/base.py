"""Shared plumbing for the three agents and the Clerk: env, ports, seeds, the agent factory and the chat protocol
(mention strip, loop guard, 20-word lines, exactly one [seance] machine line last).

No model code in here: the Bailiff imports this module. The ASI-1 voice lives in voice.py.
uAgents is imported only inside make_agent, chat_protocol and send_text, so --no-mesh never needs it.
Env: SEANCE_MAILBOX=1 (Agentverse mailbox; default local-only), SEANCE_FAKE_LLM=1 (no model calls),
SEANCE_FAKE_BENCH=1 (no browser, see case.FakeBench), SEANCE_PORT_BASE (tests use 8880),
SEANCE_SEED_SUFFIX (throwaway seeds; pytest gets them anyway).
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

ROOT = pathlib.Path(__file__).resolve().parents[2]
MESH = ROOT / "agents" / "mesh"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

log = logging.getLogger("seance")

ROLES = ("bailiff", "mcclusky", "hoot", "clerk")
PORT_BASE = int(os.environ.get("SEANCE_PORT_BASE") or 8780)  # 8781 bailiff, 8782 mcclusky, 8783 hoot, 8784 clerk
PORTS = {r: PORT_BASE + i for i, r in enumerate(ROLES, 1)}
NEVER = {8770, 8771, 8796, 8797, 8798, 8799}  # macOS sharingd, and the live probe agents
if NEVER & set(PORTS.values()):
    raise RuntimeError(f"SEANCE_PORT_BASE={PORT_BASE} hits a reserved port")
SEED_ENV = {r: f"{r.upper()}_SEED" for r in ROLES}
REAL = {"bailiff": "agent1qw47zhtg9gj55676vy8myruj297339kqdjkj34e2n2xkt2mqewjn2ngyuw0",
        "mcclusky": "agent1q2ehsgka4ljzsvxhz0kf9055ka4y23zpyz9x7euqeycyp2dwmgqzuhp7qhd",
        "hoot": "agent1qf84m8mamqfjn49qutwucdtez4clrwavq4nzqlnw37hramsnk8hwzlthq5v"}
CLERK_SEED = "seance clerk cli public identity 0001"  # the Clerk holds nothing worth stealing
NAMES = {"bailiff": "Seance · The Bailiff", "mcclusky": "Seance · McClusky, Esq.", "hoot": "Seance · Dr. Hoot",
         "clerk": "Seance · The Clerk"}
HANDLES = {"bailiff": "thebailiff", "mcclusky": "mcclusky", "hoot": "drhoot"}
DESCRIPTIONS = {
    "mcclusky": "Penguin lawyer for dead web apps. Say 'raise todo': he swears how the dead app behaved, bets "
                "credibility on every claim, and a model-free court rules.",
    "hoot": "Owl skeptic. Seals edge-case attacks on a revived app before anyone testifies, then gloats about "
            "every strike, with numbers.",
    "bailiff": "Clerk of the Seance fidelity court. Runs the case, checks every seal, writes the hash-chained "
               "ledger. No opinion, no model.",
    "clerk": "Command-line client that starts Seance cases.",
}
AVATAR = "https://raw.githubusercontent.com/vihuynh72/aie-code/main/agents/mesh/avatars/{}.png"
SECRET_NAME = re.compile(r"(KEY|SEED|TOKEN|SECRET|PASSWORD|URI)$")
MENTIONS = re.compile(r"^(?:\s*@\S+)+")
WORDS = 20


def load_env() -> None:
    """.env -> os.environ (setdefault), the same rule as agents/llm.py. Values are never printed or logged."""
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip() and not k.startswith("#") and v.strip():
                os.environ.setdefault(k.strip(), v.strip())


def flag(name: str) -> bool:
    return os.environ.get(name) == "1"


def redact(text: str) -> str:
    """Scrub any secret env value (*_KEY, *_SEED, *_TOKEN, ...) from outgoing text."""
    for k, v in os.environ.items():
        if len(v) >= 8 and SECRET_NAME.search(k) and v in text:
            text = text.replace(v, "[redacted]")
    return text


def strip_mentions(text: str) -> str:
    """ASI:One puts '@agent1q...' tokens in front of the user's words; drop every leading one."""
    return MENTIONS.sub("", text or "").strip()


def clip(line: str, n: int = WORDS) -> str:
    """At most n words on a line a human reads."""
    words = line.split()
    return line if len(words) <= n else " ".join(words[:n]).rstrip(",;:") + "…"


def machine_line(agent: str, **data) -> str:
    return "[seance] " + json.dumps({"agent": agent, **data}, ensure_ascii=False, separators=(",", ":"), default=str)


def human_text(text: str) -> str:
    """What a person sees in chat: plain lines of at most 20 words, never a machine line (Vi's rule)."""
    return redact("\n".join(clip(ln) for ln in str(text).splitlines() if not ln.lstrip().startswith("[seance]")).strip())


def has_seance_meta(content) -> bool:
    """Another Seance agent's chat reply carries our hidden metadata (loop guard)."""
    return any(getattr(c, "type", "") == "metadata" and "seance" in (getattr(c, "metadata", None) or {}) for c in content)


def with_machine_line(text: str, agent: str, **data) -> str:
    """Reply text, every human line at most 20 words, then exactly one machine line in its own paragraph
    (ASI:One renders markdown, so single newlines inside a paragraph collapse)."""
    body = "\n".join(clip(ln) for ln in str(text).splitlines() if not ln.lstrip().startswith("[seance]")).strip()
    return redact(f"{body}\n\n{machine_line(agent, **data)}")


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


# --- identities and the agent factory ---------------------------------------------------------------
def throwaway() -> str:
    """Tests and the processes they start never hold a real seed (they inherit PYTEST_CURRENT_TEST)."""
    return os.environ.get("SEANCE_SEED_SUFFIX") or ("pytest" if os.environ.get("PYTEST_CURRENT_TEST") else "")


def seed(role: str) -> str:
    if suffix := throwaway():
        return f"seance throwaway seed {role} {suffix}"
    if role == "clerk":
        return CLERK_SEED
    load_env()
    value = os.environ.get(SEED_ENV[role])
    if not value:
        raise RuntimeError(f"{SEED_ENV[role]} is not set; add it to .env")
    return value


def address(role: str) -> str:
    from uagents_core.identity import Identity
    return Identity.from_seed(seed(role), 0).address


def ours() -> set[str]:
    """Our three agents' addresses: their chat is never answered (loop guard)."""
    out = set()
    for r in ("bailiff", "mcclusky", "hoot"):
        try:
            out.add(address(r))
        except RuntimeError:
            pass
    return out


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
          "avatar_url": AVATAR.format(role) if role != "clerk" else None, "handle": HANDLES.get(role),
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
        """Our agents by local rules; anyone else (ASI:One users) through the Almanac; nothing when that fails."""

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
        # shortcut: overrides private uagents 0.26.1 Agent._update_agent_status; re-check on upgrade
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


async def send_text(ctx, to: str, agent: str, text: str, resources=(), **data):
    """One ChatMessage: plain human text, the machine data in hidden MetadataContent (ASI:One does not render it),
    then any ResourceContent (screenshots). Messages to one address leave in call order."""
    from uagents_core.contrib.protocols.chat import ChatMessage, MetadataContent, TextContent
    async with _ORDER.setdefault(to, asyncio.Lock()):
        meta = redact(machine_line(agent, **data).removeprefix("[seance] "))
        content = [TextContent(text=human_text(text)), MetadataContent(type="metadata", metadata={"seance": meta}),
                   *resources]
        return await ctx.send(to, ChatMessage(content=content))


def loop_guard(sender: str, raw: str, mine: set[str]) -> bool:
    """True: never answer. Our own agents talk in models, and a machine line means another agent's reply."""
    return sender in mine or "[seance] {" in raw


def reply_parts(out) -> tuple[str, dict, list]:
    """A handler's answer: str, (str, dict) or (str, dict, resources)."""
    if isinstance(out, str):
        return out, {}, []
    return out[0], out[1], list(out[2]) if len(out) > 2 else []


def chat_protocol(role: str, handler):
    """Agent Chat Protocol (ASI:One, the Clerk, other agents). Acks every ChatMessage, ignores our own agents'
    chat and anything carrying a machine line (loop guard), strips leading @mentions, then calls
    handler(ctx, sender, text) -> str | (str, dict) | (str, dict, resources) | None, or an awaitable of one.
    The reply goes to the sender from inside this handler (ASI:One threads by ctx.session). A handler may send
    progress lines first with send_text: ASI:One shows only the last message, so the reply must stand alone."""
    from uagents import Protocol
    from uagents_core.contrib.protocols.chat import ChatAcknowledgement, ChatMessage, chat_protocol_spec

    proto = Protocol(spec=chat_protocol_spec)
    mine: set[str] = set()

    @proto.on_message(ChatMessage)
    async def _on_chat(ctx, sender: str, msg: ChatMessage):
        await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))
        raw = msg.text()
        mine.update(mine or ours())
        if loop_guard(sender, raw, mine) or has_seance_meta(msg.content):
            ctx.logger.info(f"loop guard: no reply to {sender[:20]}")
            return
        text = strip_mentions(raw)
        if not text and any(c.type == "end-session" for c in msg.content):
            return
        try:
            out = handler(ctx, sender, text)
            if inspect.isawaitable(out):
                out = await out
        except Exception as ex:  # noqa: BLE001 - a chat user gets a line, not silence
            ctx.logger.exception("chat handler failed")
            out = (f"The court tripped over its robes ({type(ex).__name__}). Try: help.",
                   {"ok": False, "error": type(ex).__name__})
        if out:
            reply, data, res = reply_parts(out)
            await send_text(ctx, sender, role, reply, resources=res, **data)

    @proto.on_message(ChatAcknowledgement)
    async def _on_ack(ctx, sender: str, msg: ChatAcknowledgement):
        pass

    return proto
