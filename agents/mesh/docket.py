"""The docket: the cases the court can hear, from the data on disk only (Vi: "don't hard code too much").

    from agents.mesh import docket
    docket.warm()          # agent start: writes or checks every card; never raises
    docket.cases()         # [{app, title, about, example}], one per app case.apps() reports ready
    docket.card(app)       # one row; raises case.MissingInput when the court cannot raise that app

Order: real dead apps first (their fixtures/apps.json source is a URL), then fixtures, then by id.
ASI-1 (asi1, strict json_schema, reasoning_effort low) writes a card once from the app's sources: its registry
row, apps/<app>/README.md, the behavior sheet (or claims) on file and the cross grammar in commands.py. The card
is cached in runs/<app>/card.json under a hash of those sources, so an updated app rewrites its own card. Every
field is checked: word limits, plain words, no verdict, no number the sources lack; the example must pass
commands.to_steps, and ASI-1 gets one retry with the court's refusal. A field that still fails, or ASI-1 off or
down, takes the fallback: the registry name, the README "Why dead" line or the registry source, and the
shortest test the grammar accepts for the app's selectors. A card never reads the court's results.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.request

from agents.mesh import base, case, commands

ASI1_URL = "https://api.asi1.ai/v1/chat/completions"  # voice.ASI1_URL; voice stays out of the Bailiff's process
APPS = case.ROOT / "apps"
LIMITS = {"title": 4, "about": 16, "example": 8}  # words per field
SHEET_LINES, README_CHARS = 8, 600  # what ASI-1 reads: the README's head comes before its selector tables
URL = re.compile(r"https?://")
CODE = re.compile(r"[\[\]{}()<>`#|\\\"]|\b(?:click|type|key|wait|observe):|\bc\d{2}\b|(?<!\w)\.\w")  # never in chat
WORDY = re.compile(r"[*_=/@]")  # fine in a calculator test, not in a title or an about
VERDICT = re.compile(r"(?i)\b(?:lock(?:ed)?|struck|fidelity|faithful|forg(?:ery|ed)|verdict|ruling|differ\w*)\b")
MENU = {"1", "2", "3"}  # the judge's numbered choices: a test made only of these reads as a pick
SCHEMA = {"type": "object", "additionalProperties": False, "required": list(LIMITS),
          "properties": {k: {"type": "string"} for k in LIMITS}}
RULES = ("You write one docket card for SEANCE, a courtroom game where a judge tests a dead web app against its "
         "revival. Use only the sources given. Return JSON with three plain-text fields. "
         "title: the app's everyday name in 1 to 4 words, in Title Case after an optional lowercase 'the', that "
         "reads well after 'The case of'; no ids, file names, authors or versions, and no project jargon such as "
         "fixture, lane or oracle (a test app is just its everyday name, like 'the Calculator'). "
         "about: one sentence of at most 16 words, starting with a capital letter: what the app is and why it was "
         "dead, or, when the sources say it never died, why it is on trial, in words a non-technical judge knows "
         "(say 'a practice app built today', never fixture or lane testing); light courtroom tone; never say how a "
         "trial went. "
         "example: one test of at most 8 words the judge could type that the court's parser accepts for this app, "
         "in its keys or words, spaced the way a person types; never selectors, '#', quotes or step syntax like "
         "click:. "
         "Never use a number the sources do not have. No markdown, brackets or code.")


def cases(runs=case.RUNS) -> list[dict]:
    """[{app, title, about, example}] for every app the court can raise, in docket order. Blocking only while a card
    is (re)written; warm() at agent start makes it instant."""
    reg = case._registry()
    ready = [a for a, why in case.apps(runs).items() if not why]
    ready.sort(key=lambda a: (not URL.match(str(reg.get(a, {}).get("source", ""))), a))
    return [card(a, runs) for a in ready]


def card(app: str, runs=case.RUNS, retry: bool = False) -> dict:
    """One docket row: runs/<app>/card.json while its sources are unchanged, else written now (ASI-1, then the
    fallback). retry=True (warm) asks ASI-1 again for a card it could not write before.
    Raises case.MissingInput when the court cannot raise the app."""
    src = _sources(app, runs)
    key = hashlib.sha256(json.dumps([RULES, src], sort_keys=True).encode()).hexdigest()
    path = pathlib.Path(runs) / app / "card.json"
    try:
        hit = json.loads(path.read_text(encoding="utf-8"))
        if hit["key"] == key and not (retry and hit["by"] == "fallback"):
            return hit["card"]
    except (OSError, ValueError, LookupError, TypeError):
        pass  # no card yet, or a torn one: write it
    row, by = _written(src)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"key": key, "by": by, "card": row}, indent=1, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    except OSError as ex:
        base.log.warning("docket: could not cache %s's card (%s)", app, ex)
    return row


def warm(runs=case.RUNS) -> None:
    """Agent start: every ready app's card written or checked, ASI-1 asked again for the ones it could not write.
    Blocking (a few seconds per card ASI-1 writes); never raises."""
    try:
        ready = [a for a, why in case.apps(runs).items() if not why]
    except Exception as ex:  # noqa: BLE001 - a broken docket must not stop the agent
        base.log.warning("docket: cannot list the apps (%s)", ex)
        return
    for a in ready:
        try:
            card(a, runs, retry=True)
        except Exception as ex:  # noqa: BLE001
            base.log.warning("docket: no card for %s (%s)", a, ex)


def _sources(app: str, runs) -> dict:
    """Everything a card is written from; its hash keys the cache."""
    inp = case.load_inputs(app, runs)
    reg = case._registry().get(app, {})
    readme = APPS / app / "README.md"
    text = readme.read_text(encoding="utf-8") if readme.is_file() else ""
    why = re.search(r"(?im)^[\s>*_-]*why dead[*_\s]*:[*_\s]*(.+)$", text)
    lines = (inp["sheet"] or {}).get("lines") or inp["claims"] or []
    try:
        commands.to_steps(inp["selectors"], "?")
        grammar = ""
    except Exception as ex:  # noqa: BLE001 - the refusal lists the app's keys or words: the grammar in its own words
        grammar = str(ex)
    cross = commands.COMMANDS["bailiff"]["cross"][1]  # "cross 7/8= | cross add ...": the grammar's own examples
    return {"app": app, "name": str(reg.get("name") or app), "source": str(reg.get("source") or ""),
            "license": str(reg.get("license") or ""), "readme": text, "why": why[1].strip() if why else "",
            "behaviors": [str(x.get("text", ""))[:200] for x in lines[:SHEET_LINES]], "grammar": grammar,
            "examples": [e.strip().partition(" ")[2] for e in cross.split("|")], "selectors": inp["selectors"]}


def _written(src: dict) -> tuple[dict, str]:
    """(row, 'asi1' | 'fallback'): ASI-1's fields that pass _check, the fallback's for the rest."""
    msgs = [{"role": "system", "content": RULES}, {"role": "user", "content": _prompt(src)}]
    got, bad = {}, dict.fromkeys(LIMITS, "no answer")
    for _ in range(2):
        try:
            out = _ask(msgs)
        except Exception as ex:  # noqa: BLE001 - ASI-1 off, down or garbled: the docket still opens
            base.log.warning("docket: ASI-1 did not write %s's card (%s)", src["app"], type(ex).__name__)
            break
        got = {k: " ".join(str(out.get(k) or "").split()).strip("'\" ") for k in LIMITS}
        got["about"] = got["about"][:1].upper() + got["about"][1:]
        got["title"] = re.sub(r"^The\b", "the", got["title"])  # it follows "The case of"
        bad ={k: why for k in LIMITS if (why := _check(k, got[k], src))}
        if not bad:
            break
        msgs += [{"role": "assistant", "content": json.dumps(got)},
                 {"role": "user", "content": f"The court refused that card: {'; '.join(bad.values())}. "
                                             "Answer again with all three fields."}]
    fb = _fallback(src) if bad else {}
    row = {"app": src["app"], **{k: fb[k] if k in bad else got[k] for k in LIMITS}}
    return row, "asi1" if len(bad) < len(LIMITS) else "fallback"


def _ask(messages: list[dict]) -> dict:
    """One strict-JSON ASI-1 call (blocking, 20 s); a 429 or 5xx is retried once after 2 s."""
    base.load_env()
    key = os.environ.get("ASI1_API_KEY")
    if base.flag("SEANCE_FAKE_LLM") or not key:
        raise RuntimeError("ASI-1 is off")
    fmt = {"type": "json_schema", "json_schema": {"name": "docket_card", "strict": True, "schema": SCHEMA}}
    body = {"model": "asi1", "reasoning_effort": "low", "messages": messages, "response_format": fmt}
    req = urllib.request.Request(ASI1_URL, json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                text = json.load(r)["choices"][0]["message"]["content"] or ""
            break
        except urllib.error.HTTPError as ex:
            if attempt == 2 or (ex.code != 429 and ex.code < 500):
                raise
            time.sleep(2)
    out = json.loads(re.sub(r"(?s)<think>.*?</think>", "", text))
    if not isinstance(out, dict):
        raise ValueError("ASI-1 sent no JSON object")
    return out


def _check(field: str, text: str, src: dict) -> str:
    """'' when a field is fit for the judge's chat, else why not, in words ASI-1 can fix on its retry."""
    n = len(text.split())
    if not n or n > LIMITS[field]:
        return f"{field} must have 1 to {LIMITS[field]} words, not {n}"
    if CODE.search(text):
        return f"{field} {text!r} has code, selectors, quotes or brackets"
    if field == "example":
        if not set(re.findall(r"[a-z]+|\d+", text.lower())) - MENU:
            return f"example {text!r} reads like a menu pick; use a key above 3 or a word"
        try:
            commands.to_steps(src["selectors"], text)
        except Exception as ex:  # noqa: BLE001 - any refusal, in the parser's own words
            return f"the court's parser refused example {text!r}: {ex}"
        return ""
    if WORDY.search(text) or VERDICT.search(text) or re.match(r"(?i)the case of\b", text):
        return f"{field} {text!r} must be plain words that never say how a trial went"
    new = sorted(set(re.findall(r"\d+", text)) - set(re.findall(r"\d+", json.dumps(src))))
    if new:
        return f"{field} uses {', '.join(new)}, a number the sources do not have"
    if field == "about" and re.search(r"[.!?]\s+\S", text):
        return "about must be one sentence"
    return ""


def _prompt(src: dict) -> str:
    return "\n".join([
        f"App id: {src['app']}", f"Registry name: {src['name']}", f"Source: {src['source']}",
        f"License: {src['license'] or 'unknown'}",
        *([f"Why it was dead, from its README: {src['why']}"] if src["why"] else []),
        f"README start:\n{src['readme'][:README_CHARS]}" if src["readme"] else "README: none",
        "What the original app does, from its behavior sheet:", *(f"- {b}" for b in src["behaviors"]),
        f'Asked to run the test "?" on this app, the court\'s parser said: {src["grammar"] or "nothing"}',
        f"Tests this parser accepts on some apps: {' | '.join(src['examples'])}"])


def _fallback(src: dict) -> dict:
    """The card without a model. title: the registry name without parentheses or a fixture- prefix, capitalized.
    about: the README "Why dead" line, else the registry source, in plain clauses. example: the shortest test the
    grammar accepts for these selectors, among its documented examples (and their first comma parts) and a sum on
    the app's own keys; '' when the app only takes contract steps."""
    name = re.sub(r"(?i)^fixture-", "", re.sub(r"\([^)]*\)", " ", src["name"]).strip())
    name = " ".join(name.split()[:LIMITS["title"]]) or src["app"]
    title = name[:1].upper() + name[1:]
    about = _plain(src["why"], src) or _plain(src["source"], src) or f"{title}, back from the dead."
    tests = [", ".join(e.split(", ")[:i]) for e in src["examples"] for i in range(1, e.count(", ") + 2)]
    tests += [f"{a} {op} {b} =" for a, b in itertools.permutations("1234567890", 2) for op in commands.OPS]
    example = min((t for t in tests if not _check("example", t, src)), key=len, default="")
    return {"title": title, "about": about, "example": example}


def _plain(text: str, src: dict) -> str:
    """The clauses of a note that pass _check (no code, paths, links or verdicts), as one sentence of at most
    16 words."""
    out = []
    for part in re.split(r"[();]|[.!?](?:\s|$)", text):
        part = " ".join(part.split()).strip(" ,-")
        if part and ":" not in part and not _check("about", "; ".join([*out, part]), src):
            out.append(part)
    s = "; ".join(out)
    return f"{s[:1].upper()}{s[1:]}." if s else ""
