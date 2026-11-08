"""The ASI-1 voices of McClusky and Dr. Hoot. Never imported by the Bailiff (no model in the court).

persona(role, prompt, fallback) -> one in-character line from ASI-1 (asi1, reasoning_effort low, TIMEOUT s), asked
for at most ASK words. A longer line is cut at its last sentence or clause end within MAX words, and every number in
it must appear in the prompt. Otherwise one stricter retry, then the deterministic fallback with a warning in the log
(the fallback comes at once with SEANCE_FAKE_LLM=1 or without ASI1_API_KEY).
hoot_line(r) taunts after a ruling, hoot_line(r, answer) rebuts McClusky, mcclusky_line(r, answer) answers Hoot: each
is told only facts(r), the ruling in plain words, and falls back to captions.taunt, rebuttal or objection.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

from agents.mesh import base, captions

ASI1_URL = "https://api.asi1.ai/v1/chat/completions"
TIMEOUT, PAUSE = 20, 1.5  # s per try, s before retrying a 429/5xx: two tries fit the Bailiff's 60 s REMARK_S
ASK, MAX, KEEP = 22, 30, 6  # words asked for, accepted, and kept at least when a long line is cut
OFFLINE = {
    "mcclusky": "Objection, Your Honor: my brain is in recess. Try: raise, claims, credibility, why.",
    "hoot": "Hoo. My banter is offline, my commands are not: attacks, seal, reveal.",
}
RULES = (f"Reply in one or two short sentences, at most {ASK} words in all, in character, plain text: no markdown, "
         "no lists, no code. A non-technical judge must understand you: talk about what the app actually did, in "
         "everyday words, and never say locked, struck, sworn, unsworn, oath, fidelity, credibility, claim ids or "
         "selectors. Use at most one number, only numbers that appear in the facts, written as digits; never invent "
         "or compute a number.")  # Vi could not follow the jargon version
PERSONAS = {
    "mcclusky": "You are McClusky, Esq., a flamboyant, slightly shady penguin defense lawyer in SEANCE, a court that "
                "tests resurrected web apps. You swore claims about how the dead app behaved, with credibility on the "
                "line. Your rival is Dr. Hoot, a smug owl skeptic. " + RULES,
    "hoot": "You are Dr. Hoot, a smug, pedantic owl skeptic in SEANCE, a court that tests resurrected web apps. You "
            "seal edge-case attacks before anyone testifies and love catching McClusky, Esq. overselling. " + RULES,
}
STRICT = "Your last reply was refused ({}). Now ONE sentence of at most 15 words, and only numbers from the facts."
NUM = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*(?!\w)")  # 7, 0.87, 1,000; not the 1 in app1 or the 07 in c07
NUMBER_WORDS = dict(zip(("zero two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
                         "sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety "
                         "hundred thousand").split(), (0, *range(2, 21), 30, 40, 50, 60, 70, 80, 90, 100, 1000)))
QUOTES = "\"“”"


def persona(role: str, prompt: str, fallback: str = "") -> str:
    """Blocking (urllib, at most two tries of TIMEOUT s): call it with asyncio.to_thread from a handler."""
    fallback = fallback or OFFLINE[role]
    if base.flag("SEANCE_FAKE_LLM"):
        return _scripted(role, "SEANCE_FAKE_LLM=1", fallback)
    base.load_env()
    key = os.environ.get("ASI1_API_KEY")
    if not key:
        return _scripted(role, "no ASI1_API_KEY", fallback)
    given, why = numbers(prompt), []
    for _ in range(2):
        system = PERSONAS[role] + (" " + STRICT.format(why[-1]) if why else "")
        try:
            text = clean(_ask(key, system, prompt))
        except Exception as ex:  # noqa: BLE001 - one retry, then the show goes on with the scripted line
            http = isinstance(ex, urllib.error.HTTPError)
            why.append(f"HTTP {ex.code}" if http else type(ex).__name__)
            if http and (ex.code == 429 or ex.code >= 500) and len(why) == 1:
                time.sleep(PAUSE)
            continue
        line = fit(text)
        extra = sorted(numbers(line) - given)
        if line and not extra:
            return line
        why.append("an empty reply" if not text else f"too long, {len(text.split())} words" if not line
                   else f"numbers not in the facts: {', '.join(extra)}")
    return _scripted(role, "; retry: ".join(why), fallback)


def _scripted(role: str, why: str, line: str) -> str:
    base.log.warning("%s: no ASI-1 line (%s); using the scripted one", role, why)
    return line


def _ask(key: str, system: str, prompt: str) -> str:
    body = {"model": "asi1", "reasoning_effort": "low",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
    req = urllib.request.Request(ASI1_URL, json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)["choices"][0]["message"]["content"] or ""


def clean(text: str) -> str:
    """One plain line: no think block, machine line, markdown stars or wrapping quotes; secrets redacted."""
    text = re.sub(r"(?s)<think>.*?</think>", "", text)
    text = " ".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("[seance]"))
    text = " ".join(text.replace("*", "").split())
    if len(text) > 1 and text[0] in QUOTES and text[-1] in QUOTES and not any(q in text[1:-1] for q in QUOTES):
        text = text[1:-1].strip()  # only a wrapping pair: '"Hoo," he said, "no."' keeps its quotes
    return base.redact(text)


def fit(text: str, n: int = MAX, keep: int = KEEP) -> str:
    """The line if it has at most n words, else cut after its last sentence or clause end that keeps between keep
    and n words (a clause cut ends in a period); "" when there is none, since a blind cut could end mid-number."""
    words = text.split()
    if len(words) <= n:
        return text
    for i in range(n, keep - 1, -1):
        last = words[i - 1]
        if last[-1] in ".!?,;:":
            return " ".join(words[:i - 1] + [last if last[-1] in ".!?" else last[:-1] + "."])
    return ""


def numbers(text: str) -> set[str]:
    """The numbers in a text, in digits or words ('one' is left out: 'no one'), so '1,000' matches 1000."""
    out = {str(NUMBER_WORDS[w]) for w in re.findall(r"[a-z]+", text.lower()) if w in NUMBER_WORDS}
    for n in NUM.findall(text):
        n = n.replace(",", "")
        out.add(str(int(n)) if n.isdigit() else n.rstrip("0").rstrip("."))
    return out


def facts(r: dict) -> str:
    """The ruling in plain words, no claim ids or court strings: the only numbers a line may use."""
    c = r["counts"]
    text = (f"Facts: McClusky made {r['claims']} claims about how the dead app behaved; {c['LOCKED']} proved true "
            f"and {c['STRUCK']} proved false. The court then ran {r['judged']} checks on both apps: the revived copy "
            f"acted like the original in {r['judged'] - r['differ']} and differently in {r['differ']}.")
    s = captions.top_strike(r)
    if s:
        text += f" His false claim: that {captions.plain(s['text'], 16)}; the real original {captions.observed(s['original'])}."
    return text


def hoot_line(r: dict, answer: str = "") -> str:
    """Dr. Hoot after a ruling: his opening taunt, or his rebuttal to McClusky's answer."""
    if answer:
        return persona("hoot", f"{facts(r)} McClusky, Esq. just said: \"{answer}\". Rebut him with one fact.",
                       captions.rebuttal(r))
    return persona("hoot", f"{facts(r)} The court just ruled. Taunt McClusky, Esq. with the most damning fact.",
                   captions.taunt(r))


def mcclusky_line(r: dict, answer: str = "") -> str:
    """McClusky's answer to Dr. Hoot after a ruling."""
    said = f"Dr. Hoot just said: \"{answer}\". " if answer else ""
    return persona("mcclusky", f"{facts(r)} {said}Answer him, spinning the facts in your favor.",
                   captions.objection(r))
