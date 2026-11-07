"""One predictable command language for humans, ASI:One and other agents. Deterministic, no model.

parse(role, text) -> Command(name, arg). Strips leading @mentions, is case-insensitive, ignores punctuation and
filler words, and takes a claim as "claim c03", "c3" or "3". Unknown input: "help" for the Bailiff, "talk"
(arg = the raw text) for McClusky and Hoot.
to_steps(selectors, text) -> (steps, observe) for "cross": contract steps (click:#k7, ...) or an expression in
the app's own vocabulary (calculator keys like "7+8=", todo words like "add Buy milk, complete"). Only
selectors from the app's selectors JSON ever come out, at most MAX_STEPS of them.
names(selectors) / human_steps(selectors, steps): the reverse, for people (#kdiv -> divide, #add -> add).
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import NamedTuple

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from agents.mesh.base import strip_mentions  # noqa: E402
from court.steps import StepError, parse as parse_step, split_type  # noqa: E402

MAX_STEPS = 30
MAX_WAIT_MS = 2000  # a cross must not park the bench
MAX_TEXT = 500

# role -> command -> (aliases, example, what it does). Help cards and READMEs render from this table.
COMMANDS = {
    "bailiff": {
        "raise": (("raise", "open", "start"), "raise todo", "open a case on an app"),
        "apps": (("apps", "docket"), "apps", "the apps the court can raise"),
        "status": (("status", "state"), "status | status c03", "the verdict, or one claim"),
        "transcript": (("transcript", "record", "ledger", "log"), "transcript", "the record of the last case"),
        "cross": (("cross", "cross-examine", "press"), "cross 7/8= | cross add Buy milk, complete",
                  "your own attack on both builds"),
        "case": (("case", "ruling", "verdict"), "case", "the last case in numbers"),
        "help": (("help", "commands", "menu"), "help", "this card"),
    },
    "mcclusky": {
        "raise": (("raise", "open", "start"), "raise todo", "put a revived app on trial"),
        "claims": (("claims", "testimony"), "claims", "my sworn claims"),
        "credibility": (("credibility", "cred", "score"), "credibility", "my credibility, before and after"),
        "why": (("why", "explain"), "why c03", "why I swore a claim"),
        "help": (("help", "commands", "menu"), "help", "this card"),
    },
    "hoot": {
        "attacks": (("attacks", "attack"), "attacks", "how many attacks I sealed"),
        "seal": (("seal", "seals", "hashes"), "seal", "the seal hashes"),
        "reveal": (("reveal",), "reveal", "the attacks, only after a ruling"),
        "help": (("help", "commands", "menu"), "help", "this card"),
    },
}
FALLBACK = {"bailiff": "help", "mcclusky": "talk", "hoot": "talk"}
FILLER = set("""please pls can could would will you u hey the a an app my your me us now for of on to about
show tell what whats is are do does let lets i want like see give claim number bailiff mcclusky hoot dr esq
mr court""".split())
CLAIM = re.compile(r"c?0*(\d{1,3})")


class Command(NamedTuple):
    name: str
    arg: str


class CrossError(ValueError):
    """A cross the court refuses; the message is safe to show in chat."""


def claim_id(token: str) -> str:
    """'c3', 'c03', '3' -> 'c03' (agents/medium.py numbers claims c01, c02, ...)."""
    return f"c{int(CLAIM.fullmatch(token)[1]):02d}"


def parse(role: str, text: str) -> Command:
    raw = strip_mentions(text)
    cmds = COMMANDS[role]
    alias = {a: name for name, (aliases, _, _) in cmds.items() for a in aliases}
    words = [w for w in re.findall(r"[a-z0-9_-]+", raw.lower()) if w not in FILLER]
    if not words:
        return Command("help", "")
    hit = next((i for i, w in enumerate(words[:3]) if w in alias), None)  # commands come first; talk runs long
    if hit is None:
        if len(words) == 1 and CLAIM.fullmatch(words[0]) and role != "hoot":
            return Command("status" if role == "bailiff" else "why", claim_id(words[0]))
        return Command(FALLBACK[role], raw if FALLBACK[role] == "talk" else "")
    name, rest = alias[words[hit]], words[hit + 1:]
    if name == "cross":  # keep case and punctuation: "type:#item:Buy milk"
        m = re.search(rf"(?i)(?<![\w-]){re.escape(words[hit])}(?![\w-])[\s:]*", raw)
        return Command("cross", raw[m.end():].strip() if m else "")
    if name in ("status", "why"):
        cid = next((claim_id(w) for w in rest if CLAIM.fullmatch(w)), "")
        return Command("talk", raw) if name == "why" and not cid else Command(name, cid)
    return Command(name, rest[0] if rest else "")


# --- cross: expression -> steps ---------------------------------------------------------------
STEP_START = re.compile(r"(?:^|[\s,;])(?:click|type|key|wait):")
OBSERVE = re.compile(r"(?i)(?:^|[\s,;])observe[:\s]+(\S.*?)\s*$")
OPS = {"+": "add", "x": "multiply", "*": "multiply", "×": "multiply", "/": "divide", "÷": "divide",
       "-": "subtract", "−": "subtract"}


def _default_observe(s: dict) -> str:
    obs = s.get("observe")
    if isinstance(obs, str):
        return obs
    if obs:
        return "body" if "body" in obs else obs[0]
    raise CrossError("this app has no observe selector in its selectors file")


def _contract(text: str) -> list[str]:
    parts = re.split(r"[\s,;]+(?=(?:click|type|key|wait):)", text.strip())
    return [p.strip().rstrip(",;").strip() for p in parts if p.strip(",; ")]


def _calc(s: dict, text: str) -> list[str]:
    keys = {}
    for sel in [*s.get("digits", []), s.get("zero")]:
        m = re.search(r"(\d)$", sel or "")
        if m:  # a digit key is a digits/zero selector ending in that digit (#k7 -> 7)
            keys.setdefault(m[1], sel)
    for ch, name in (*OPS.items(), (".", "decimal"), ("=", "equals"), ("c", "clear")):
        sel = s.get("operators", {}).get(name) or (s.get(name) if name in ("decimal", "equals", "clear") else None)
        if sel:
            keys.setdefault(ch, sel)
    expr = re.sub(r"\s+", "", text.lower()).replace("clear", "c").replace("equals", "=")
    bad = sorted({ch for ch in expr if ch not in keys})
    if bad:
        shown = " ".join(sorted(k.upper() if k == "c" else k for k in keys))
        raise CrossError(f"no key for {' '.join(bad)} on this app; its keys are {shown}")
    return [f"click:{keys[ch]}" for ch in expr]


def _todo(s: dict, text: str) -> list[str]:
    inp, add, b = s["input"], s["add"], s.get("item_buttons", {})
    steps = []
    for part in re.split(r"\s*(?:[,;\n]|\bthen\b)\s*", text.strip()):
        if not part:
            continue
        word, _, rest = part.partition(" ")
        w, rest = word.lower(), rest.strip()
        if w in ("add", "new"):
            steps += [f"type:{inp}:{rest}", f"click:{add}"] if rest else [f"click:{add}"]
        elif w == "enter":
            steps += [f"type:{inp}:{rest}", "key:Enter"] if rest else ["key:Enter"]
        elif w in ("complete", "done", "check"):
            steps.append(f"click:{b['complete_open']}")
        elif w in ("uncomplete", "undo", "uncheck", "reopen"):
            steps.append(f"click:{b['complete_done']}")
        elif w in ("remove", "delete"):
            steps.append(f"click:{b['remove_done' if rest.lower() in ('done', 'completed') else 'remove_open']}")
        else:
            raise CrossError(f"unknown word {word!r}; say add <text>, enter <text>, complete, uncomplete, "
                             "remove, remove done (comma-separated), or contract steps like click:#add")
    return steps


def to_steps(selectors: dict, text: str) -> tuple[list[str], str]:
    """Cross expression -> (contract steps, observe selector). Raises CrossError with a chat-safe reason."""
    known = selectors_in(selectors)
    text = (text or "").strip()
    observe = _default_observe(selectors)
    m = OBSERVE.search(text)
    if m:
        want = m[1].strip()
        observe = want if want in known else {k.lstrip("#"): k for k in known}.get(want.lower().lstrip("#"), "")
        if not observe:
            raise CrossError(f"cannot observe {want!r}; this app shows {', '.join(sorted(known))}")
        text = text[:m.start()].strip(" ,;")
    if not text:
        raise CrossError("cross what? e.g. cross 7+8=  or  cross add Buy milk, complete  or  cross click:#k7")
    if STEP_START.search(" " + text):
        steps = _contract(text)
    elif "digits" in selectors:
        steps = _calc(selectors, text)
    elif "input" in selectors:
        steps = _todo(selectors, text)
    else:
        raise CrossError("this app only takes contract steps, e.g. click:<selector>")
    if not steps:
        raise CrossError("that cross has no steps")
    if len(steps) > MAX_STEPS:
        raise CrossError(f"{len(steps)} steps; the court allows {MAX_STEPS}")
    for st in steps:
        try:
            kind, args = parse_step(st)
        except StepError as ex:
            raise CrossError(str(ex)) from None
        if kind in ("click", "type") and args[0] not in known:
            raise CrossError(f"{args[0]!r} is not one of this app's selectors")
        if kind == "type" and len(args[1]) > MAX_TEXT:
            raise CrossError(f"typed text is {len(args[1])} characters; the court allows {MAX_TEXT}")
        if kind == "key" and not re.fullmatch(r"[A-Za-z0-9+]{1,24}", args[0]):
            raise CrossError(f"unknown key {args[0]!r}")
        if kind == "wait" and int(args[0]) > MAX_WAIT_MS:
            raise CrossError(f"wait:{args[0]} is too long; the court waits at most {MAX_WAIT_MS} ms")
    return steps, observe


# --- selectors -> words, for people ------------------------------------------------------------------
def selectors_in(sel) -> set[str]:
    """All selector strings in a selectors JSON, any nesting (agents/medium.py's rule; not imported: the Bailiff
    must not load model code)."""
    if isinstance(sel, str):
        return {sel}
    vals = sel.values() if isinstance(sel, dict) else sel
    return set().union(*(selectors_in(v) for v in vals)) if vals else set()


def names(selectors: dict) -> dict[str, str]:
    """selector -> its key name in the selectors file: #kdiv -> divide, #add -> add, #k7 -> 7, body -> page."""
    out = {"body": "page"}

    def walk(key, v):
        if isinstance(v, str):
            out.setdefault(v, key.replace("_", " "))
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(k, x)
        elif isinstance(v, list):
            for x in v:
                walk(key, x)
    for sel in [*selectors.get("digits", []), selectors.get("zero")]:
        if sel and (m := re.search(r"(\d)$", sel)):
            out[sel] = m[1]
    for k, v in selectors.items():
        walk(k, v)
    return out


def human_steps(selectors: dict, steps: list[str], limit: int = 8) -> str:
    """Contract steps in the app's own words: 'click:#k7','click:#kdiv' -> '7 divide'. Repeats fold into ×n."""
    nm, words = names(selectors), []
    for st in steps:
        kind, _, rest = st.partition(":")
        if kind == "click":
            words.append(nm.get(rest, rest))
        elif kind == "type":
            sel, txt = split_type(rest) or (rest, "")
            shown = txt if len(txt) <= 14 else txt[:11] + "..."
            words.append(f'type "{shown}"' if txt.strip() else f'type "{txt}"' if txt else "type nothing")
        elif kind == "key":
            words.append(rest)
        else:
            words.append(f"wait {rest} ms")
    sep = " " if "digits" in selectors else ", "
    parts = fold(words, sep) or ["nothing"]
    more = ["…"] if len(parts) > limit else []
    return sep.join(parts[:limit] + more)


def fold(words: list[str], sep: str) -> list[str]:
    """Repeats as ×n: [7, 7, 7] -> ['7 ×3']; a repeated block of 2 or 3 -> ['(type "A", add) ×2']."""
    out, i = [], 0
    while i < len(words):
        best = (1, 1)  # (block size, times)
        for size in (1, 2, 3):
            block, times = words[i:i + size], 1
            while len(block) == size and words[i + times * size:i + (times + 1) * size] == block:
                times += 1
            if times > 1 and size * times > best[0] * best[1]:
                best = (size, times)
        size, times = best
        block = sep.join(words[i:i + size])
        out.append(block if times == 1 else f"{block} ×{times}" if size == 1 else f"({block}) ×{times}")
        i += size * times
    return out
