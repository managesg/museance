"""The ASI-1 voices of McClusky and Dr. Hoot. Never imported by the Bailiff (no model in the court).

persona(role, prompt, fallback) -> one short in-character line from ASI-1 (asi1, reasoning_effort low, 25 s),
or the deterministic fallback with SEANCE_FAKE_LLM=1, without ASI1_API_KEY, offline, or on any error.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request

from agents.mesh import base

ASI1_URL = "https://api.asi1.ai/v1/chat/completions"
OFFLINE = {
    "mcclusky": "Objection, Your Honor: my brain is in recess. Try: raise todo, claims, credibility, why c03.",
    "hoot": "Hoo. My banter is offline, my commands are not: attacks, seal, reveal.",
}
PERSONAS = {
    "mcclusky": "You are McClusky, Esq., a flamboyant, slightly shady penguin defense lawyer in SEANCE, a court that "
                "tests resurrected web apps. You swore claims about how the dead app behaved, with credibility on the "
                "line. Your rival is Dr. Hoot, a smug owl skeptic. Reply in ONE sentence of at most 18 words, in "
                "character, plain text, no markdown. Use only numbers you are given; never invent numbers.",
    "hoot": "You are Dr. Hoot, a smug, pedantic owl skeptic in SEANCE, a court that tests resurrected web apps. You "
            "seal edge-case attacks before anyone testifies and love catching McClusky, Esq. overselling. Reply in "
            "ONE sentence of at most 18 words, in character, plain text, no markdown. Use only numbers you are given.",
}


def persona(role: str, prompt: str, fallback: str = "") -> str:
    """Blocking (urllib, 25 s): call it with asyncio.to_thread from a handler."""
    fallback = fallback or OFFLINE[role]
    if base.flag("SEANCE_FAKE_LLM"):
        return fallback
    base.load_env()
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
        base.log.warning("ASI-1 persona call failed (%s); using the fallback line", type(ex).__name__)
        return fallback
    text = re.sub(r"(?s)<think>.*?</think>", "", text)
    text = " ".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("[seance]"))
    text = " ".join(text.replace("*", "").split()).strip("\"' ")
    return fit(base.redact(text[:300])) or fallback


def fit(text: str, n: int = 18) -> str:
    """The line if it has at most n words, else its sentences that fit; "" when not even one does (a cut line
    could end mid-number)."""
    words = text.split()
    if len(words) <= n:
        return text
    head = " ".join(words[:n])
    end = max(head.rfind(". "), head.rfind("! "), head.rfind("? "), *(i for i in [len(head) - 1] if head[-1] in ".!?"))
    return head[: end + 1] if end > 0 and len(head[: end + 1].split()) >= 5 else ""


def _facts(r: dict) -> str:
    c = r["counts"]
    return (f"Facts, the only numbers you may use: the court tested the dead app {r['app']} against its revival. "
            f"Claims about the original: {c['LOCKED']} locked, {c['STRUCK']} struck, {c['UNSWORN']} unsworn, of "
            f"{r['claims']}. Revival: {r['differ']} of {r['judged']} behaviors differ, fidelity {r['fidelity']}. ")


def hoot_line(r: dict, answer: str) -> str:
    """Dr. Hoot's rebuttal to McClusky in a live debate: ASI-1 in character, told only the ruling's numbers."""
    from agents.mesh import captions
    prompt = (_facts(r) + f"McClusky, Esq. just said: \"{answer}\". Rebut him in one sentence of at most 18 words "
              f"that cites one number.")
    return persona("hoot", prompt, captions.rebuttal(r))


def mcclusky_line(r: dict, answer: str = "") -> str:
    """McClusky's voice line after the ruling: ASI-1 in character, told only the ruling's numbers."""
    from agents.mesh import captions
    prompt = (_facts(r) + f"Your credibility: {r['credibility_start']} to {r['credibility_end']}. Dr. Hoot just said: "
              f"\"{answer}\". Answer him in one sentence of at most 18 words that cites the main numbers.")
    return persona("mcclusky", prompt, captions.objection(r))
