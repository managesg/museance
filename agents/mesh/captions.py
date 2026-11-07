"""Deterministic words for the stage and the chat. No model in here: the Bailiff uses it.

caption(event, payload, **extra): the one-line caption stored with every mesh.<event> ledger event (extra numbers
live only in the caption, never as new payload keys). The rest renders replies from runs/<app>/ruling.json.
Every line a human reads is at most 20 words (base.clip enforces it on the way out); parts of a chat message are
blank-line separated because ASI:One renders markdown.
"""
from __future__ import annotations

from agents.mesh import commands

DEADPAN = "No opinion. No model."
NAMES = {"mcclusky": "McClusky, Esq.", "hoot": "Dr. Hoot", "bailiff": "The Bailiff", "clerk": "The Clerk"}
ICON = {"bailiff": "🔨", "hoot": "🦉", "mcclusky": "🐧"}
STATUSES = ("LOCKED", "STRUCK", "FABRICATED", "UNSWORN")


def short(s, n: int = 60) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 3] + "..."


def n_(k: int, word: str) -> str:
    return f"{k} {word}" if k == 1 else f"{k} {word}s"


def who(addr: str) -> str:
    return addr if not addr.startswith("agent1") else addr[:12] + "…"


def shown(text: str, n: int = 24) -> str:
    """An observed text for people: court ERROR strings in words, list items joined by ' / '."""
    t = str(text)
    if t.startswith("ERROR:observe"):
        return "no such element"
    if t.startswith("ERROR:step"):
        return "a step failed"
    if t.startswith("ERROR:load"):
        return "did not load"
    return short(" / ".join(x.strip() for x in t.splitlines() if x.strip()) or "", n)


# --- mesh event captions (R2) ----------------------------------------------------------------------------
def caption(event: str, p: dict, **x) -> str:
    """One line, always. p: the event payload; x: numbers that only the caption carries."""
    if event == "open":
        return f"🔨 Case {p['case_id']} opened on {p['app']} for {who(p['requested_by'])}."
    if event == "sealed":
        return f"🦉→🔨 Sealed {p['count']} attacks before anyone testified, seal {p['seal'][:8]}."
    if event == "sworn":
        return f"🐧→🔨 Swore {p['count']} claims with {p['total_bond']} credibility on the bond."
    if event == "revealed":
        bad = p["count"] - p["matched"]
        return f"🦉→🔨 Revealed {p['count']} attacks; {p['matched']} match their seals" + (
            f", {bad} thrown out." if bad else ".")
    if event == "ruling":
        if x.get("error"):
            return f"🔨 Error: case adjourned, {short(x['error'], 90)}"
        fab = f", {p['fabricated']} fabricated" if p["fabricated"] else ""
        return (f"🔨 Original: {p['locked']} locked, {p['struck']} struck, {p['unsworn']} unsworn{fab}. "
                f"Revival: {x['differ']} of {x['judged']} differ, fidelity {p['fidelity']}.")
    if event == "remark":
        to = "🐧" if p["from"] == "hoot" else "🦉"
        return f"{ICON[p['from']]}→{to} {p['text']}"
    if event == "cross":
        v = p["verdict"]
        said = "flaky, set aside" if v == "flaky" else "both builds agree" if v == "match" else "the builds differ"
        return (f"🔨 Cross by {who(p['who'])}: {x['steps']} → original \"{shown(x['original'], 16)}\", "
                f"revival \"{shown(x['revival'], 16)}\": {said}.")
    raise KeyError(event)


# --- what the court did --------------------------------------------------------------------------------------
def test_lines(verdicts: list, claims: list, attacks: list, locks: list, selectors: dict) -> list[str]:
    """2-3 real verdicts in people's words, strikes and mismatches first."""
    status = {x["claim_id"]: x["status"] for x in locks}
    items = {("claim", c["id"]): c for c in claims} | {("attack", a["id"]): a for a in attacks}
    bond = lambda v: items[(v["kind"], v["ref"])].get("bond", 0)  # noqa: E731

    def steps(v):
        it = items[(v["kind"], v["ref"])]
        full = it["test"]["steps"] if v["kind"] == "claim" else it["steps"]
        return commands.human_steps(selectors, v.get("shrunk_steps") or full, limit=6)

    struck = sorted((v for v in verdicts if v["kind"] == "claim" and status.get(v["ref"]) == "STRUCK"),
                    key=lambda v: -bond(v))
    differ = [v for v in verdicts if not v["match"] and not v["flaky"] and v not in struck]
    fine = sorted((v for v in verdicts if v["match"] and (v["kind"] == "attack" or status.get(v["ref"]) == "LOCKED")),
                  key=lambda v: (v["kind"] != "claim", -bond(v)))
    out = []
    for v in struck:
        expect = items[("claim", v["ref"])]["test"]["expect"]
        out.append(_fit(f"❌ {v['ref']} struck:", steps(v), f"→ original \"{shown(v['original'])}\", McClusky swore "
                                                          f"\"{shown(expect)}\"."))
    for v in differ:
        out.append(_fit(f"❌ {v['ref']}:", steps(v), f"→ original \"{shown(v['original'])}\", revival "
                                                    f"\"{shown(v['revival'])}\"."))
    for v in fine:
        out.append(_fit(f"✅ {v['ref']}:", steps(v), f"→ both builds show \"{shown(v['original'])}\"."))
    return out[:3]


def _fit(head: str, steps: str, tail: str, n: int = 19) -> str:
    """head + steps + tail in at most n words (the list bullet is the 20th): the steps give way first."""
    room = max(2, n - len(head.split()) - len(tail.split()))
    words = steps.split()
    return " ".join([head, " ".join(words[:room]).rstrip(",") + ("…" if len(words) > room else ""), tail])


def totals_line(r: dict) -> str:
    return (f"Totals: {r['claims']} claims, {r['attacks']} attacks, {r['runs_per_build']} runs per build, "
            f"{r['seconds']['court']} s in court, {r['seconds']['total']} s in all.")


def thinking_lines(r: dict, sheet: dict, claims: list, locks: list) -> list[str]:
    """2-3 lines, every one derived from the case files: the seal, then what the data flags."""
    s, status = r["seal"], {x["claim_id"]: x["status"] for x in locks}
    if s["matched"] == s["count"] and not s["p4_problems"]:
        src = f"P4's git seal ({s['p4_count']} sealed, {s['count']} run)" if s["p4_count"] else "Hoot's commits"
        out = [f"🦉 Seal checked: all {s['count']} attacks match {src}."]
    else:
        out = [f"🦉 Seal problem: {s['count'] - s['matched']} attacks thrown out; P4's seal flags "
               f"{len(s['p4_problems'])} differences."]
    more = []
    if r["flaky"]:
        more.append(f"⚠️ {n_(r['flaky'], 'test')} answered differently on two runs; set aside, never counted as "
                    f"strikes.")
    conflicts = [ln["id"] for ln in sheet.get("lines", []) if ln.get("conflicts")]
    if conflicts:
        more.append(f"📄 The behavior sheet flags conflicting evidence on {n_(len(conflicts), 'line')}: "
                    f"{', '.join(conflicts[:4])}.")
    fab = [c["id"] for c in claims if c.get("label") == "FABRICATED"]
    if fab:
        more.append(f"📄 {n_(len(fab), 'claim')} cite{'s' if len(fab) == 1 else ''} no evidence, so FABRICATED: "
                    f"{', '.join(fab[:4])}.")
    if claims:
        low = min(claims, key=lambda c: (c["bond"], c["id"]))
        more.append(f"🐧 Smallest bet: {low['id']}, {low['bond']} credibility at {low['confidence']:.0%}; "
                    f"it was {status.get(low['id'], 'not ruled').lower()}.")
    return out + more[:2]


def final_reply(r: dict, attached: bool = False) -> str:
    """McClusky's one, self-contained answer to 'raise <app>' (ASI:One shows only the last message).
    The machine line is added on the way out (base.with_machine_line)."""
    head = f"⚖️ The case: is the revived {r['app']} the same app as the dead original?"
    record = "\n".join(f"{i}. {ln}" for i, ln in enumerate(r.get("record", [])[:7], 1))
    ledger = ledger_line(r["ledger"])
    if r.get("error"):
        parts = [head, f"🔨 The case was adjourned: {short(r['error'], 100)}"]
        return "\n\n".join(parts + ([f"📜 Record\n\n{record}"] if record else []) + [ledger])
    tests = "\n".join(f"- {ln}" for ln in [*r["tests"], totals_line(r)])
    thinking = "\n".join(f"- {ln}" for ln in r["thinking"])
    parts = [head, f"🐧 {r['voice']}", f"🔍 What the court actually did\n\n{tests}", f"💭 Thinking\n\n{thinking}",
             f"📜 Record\n\n{record}"]
    if r.get("shots") and not attached:
        parts.append(f"📸 Screenshots saved in runs/{r['app']}/shots.")
    return "\n\n".join([*parts, ledger])


def ledger_line(led: dict) -> str:
    ok = "chain intact" if led.get("ok") else f"chain BROKEN ({short(led.get('check', ''), 60)})"
    return f"Ledger: {led.get('entries', 0)} entries, {ok}."


def verdict_summary(r: dict) -> str:
    c = r["counts"]
    return (f"Original: {c['LOCKED']} locked, {c['STRUCK']} struck, {c['UNSWORN']} unsworn, {c['FABRICATED']} "
            f"fabricated.\n\nRevival: {r['differ']} of {r['judged']} behaviors differ; fidelity {r['fidelity']}.")


def status_text(r: dict) -> str:
    if r.get("error"):
        return f"🔨 Case {r['case_id']} on {r['app']} was adjourned: {short(r['error'], 100)}\n\n{ledger_line(r['ledger'])}"
    return "\n\n".join([f"🔨 Case {r['case_id']} on {r['app']}, ruled.", verdict_summary(r),
                        f"McClusky's credibility: {r['credibility_start']} → {r['credibility_end']}.",
                        ledger_line(r["ledger"])])


def case_text(r: dict) -> str:
    if r.get("error"):
        return status_text(r)
    return "\n\n".join([f"🔨 Case {r['case_id']} on {r['app']}, raised by {who(r['requested_by'])}.",
                        verdict_summary(r), totals_line(r), f"Brier {r['brier']}; credibility "
                        f"{r['credibility_start']} → {r['credibility_end']}.", ledger_line(r["ledger"])])


def claim_status(r: dict, claim: dict | None, lock: dict | None, cid: str) -> str:
    if not claim or not lock:
        return f"No claim {cid} in case {r['case_id']}; it had {r['claims']} claims, c01 to c{r['claims']:02d}."
    return (f"{cid} {lock['status']}: {short(lock['reason'], 90)}.\n\nSworn at {claim['confidence']:.0%} for a bond "
            f"of {claim['bond']}: {short(claim['text'], 70)}")


def transcript(events: list, check: dict) -> str:
    """The human-readable record of the last case: mesh event captions in order, at most 12, then the ledger."""
    mesh = [e for e in events if e["type"].startswith("mesh.")]
    if not mesh:
        return f"No case on the record yet. Say: raise todo\n\n{ledger_line(check)}"
    lines = [e["payload"].get("caption", e["type"]) for e in mesh][-12:]
    return "📜 Record\n\n" + "\n".join(f"{i}. {ln}" for i, ln in enumerate(lines, 1)) + f"\n\n{ledger_line(check)}"


# --- chat templates ------------------------------------------------------------------------------------------
HEADS = {"bailiff": "🔨 The Bailiff. No opinion, no model. Commands:",
         "mcclusky": "🐧 McClusky, Esq., counsel for the dearly departed. Commands:",
         "hoot": "🦉 Dr. Hoot, skeptic, owl, never wrong. Commands:"}
TAILS = {"bailiff": "Anything else gets this card.", "mcclusky": "Anything else, and I argue with you for free.",
         "hoot": "Anything else is banter. Hoo."}


def help_card(role: str) -> str:
    rows = [f"- {ex}: {what}" for _, ex, what in commands.COMMANDS[role].values()]
    return f"{HEADS[role]}\n\n" + "\n".join(rows) + f"\n\n{TAILS[role]}"


def docket(apps: dict) -> str:
    """apps: case.apps() -> {app: '' when ready, else what is missing}."""
    if not apps:
        return "The docket is empty."
    return "Docket: " + ", ".join(f"{a} (ready)" if not why else f"{a} (not ready)" for a, why in apps.items()) + "."


def refusal(app: str, apps: dict) -> str:
    if app in apps:
        return f"{app} is on the docket but not ready: {short(apps[app], 80)}\n\n{docket(apps)}"
    return f"The court cannot raise {short(app, 30)!r}: no evidence on file. No hearsay.\n\n{docket(apps)}"


IN_SESSION = "The court is in session."


def busy(case_id: str, app: str) -> str:
    return f"{IN_SESSION} Case {case_id} on {app}; one ghost at a time."


def no_case(app: str = "") -> str:
    return f"No ruling on file{' for ' + app if app else ''}. Say: raise todo"


def cross_result(app: str, steps_h: str, v: dict) -> str:
    if v["flaky"]:
        verdict = "⚠️ flaky: a build answered two ways in two runs. Set aside."
    elif v["match"]:
        verdict = "✅ both builds agree, twice each."
    else:
        verdict = f"❌ the builds differ; smallest repro: {short(steps_h, 60)}."
    return (f"🔨 Cross on {app}: {short(steps_h, 70)}\n\nOriginal \"{shown(v['original'], 40)}\", revival "
            f"\"{shown(v['revival'], 40)}\".\n\n{verdict}")


def cross_refused(reason: str) -> str:
    return f"Objection sustained: {short(reason, 110)}"


def rate_limited(seconds: float) -> str:
    return f"One cross per witness every 10 seconds. Wait {max(1, round(seconds))} more."


def attacks_line(app: str, n: int, sealed_of: int, screens: dict) -> str:
    per = ", ".join(f"{k} {v}" for k, v in sorted(screens.items()))
    src = f", picked from {sealed_of} P4 sealed" if sealed_of else ""
    return f"🦉 {n} attacks on {app}{src}: {per}.\n\nThe steps stay in the envelope until the court rules. Hoo."


def seal_line(app: str, seal: dict, p4_problems: list | None) -> str:
    if p4_problems is None:
        match = "No P4 seal on file for this app."
    else:
        match = "It matches P4's seal in git." if not p4_problems else f"P4's seal flags {len(p4_problems)} problems."
    return (f"🦉 Seal for {app}: {len(seal['attacks'])} attacks, sha256 {seal['attacks_sha256'][:12]}.\n\n{match}")


def reveal_refused(n: int) -> str:
    return f"🦉 Hoo hoo, no. {n} attacks stay sealed until the court rules. Ask McClusky: raise <app>."


def reveal_list(app: str, rows: list, n: int) -> str:
    """rows: (attack id, human steps, original, revival) for the attacks that caught the revival."""
    lines = [f"- {i}: {s} → original \"{shown(o, 16)}\", revival \"{shown(rv, 16)}\"" for i, s, o, rv in rows[:5]]
    head = f"🦉 Revealed for {app}: {n} attacks, {len(rows)} caught the revival."
    return head + ("\n\n" + "\n".join(lines) if lines else "")


def claims_list(app: str, claims: list, locks: list) -> str:
    st = {x["claim_id"]: x["status"] for x in locks}
    rows = [f"- {c['id']} {st.get(c['id'], 'PENDING')}, {c['confidence']:.0%}, bond {c['bond']}: {short(c['text'], 50)}"
            for c in claims[:10]]
    more = [f"- …and {len(claims) - 10} more."] if len(claims) > 10 else []
    return f"🐧 My sworn testimony on {app}: {len(claims)} claims.\n\n" + "\n".join(rows + more)


def why_line(c: dict, lock: dict | None) -> str:
    court = f"Court: {lock['status']}, {short(lock['reason'], 70)}." if lock else "The court has not ruled on it yet."
    ev = ", ".join(c.get("evidence") or []) or "none, so FABRICATED"
    return (f"🐧 {c['id']}: {short(c['text'], 80)}\n\nTier {c['tier']}, {c['label']}, evidence {short(ev, 40)}; sworn "
            f"at {c['confidence']:.0%}, bond {c['bond']}.\n\n{court}")


# --- closing remarks (deterministic; McClusky's ASI-1 voice falls back to objection) ---------------------
def taunt(r: dict) -> str:
    """Dr. Hoot's closing remark, at most 18 words, with the case's numbers."""
    if r.get("struck"):
        s = max(r["struck"], key=lambda s: (s["confidence"], s["bond"], s["id"]))
        return (f"Struck! {s['id']}: you swore \"{shown(s['expect'], 14)}\", the original says "
                f"\"{shown(s['original'], 14)}\". {s['bond']} points, counselor.")
    if r.get("differ"):
        return f"Hoo. {r['differ']} behaviors differ in the revival; fidelity {r['fidelity']}. Not impressed."
    return f"Hoo. Zero strikes and fidelity {r['fidelity']}? I demand a recount, counselor."


def rebuttal(r: dict) -> str:
    """Dr. Hoot's answer to McClusky when ASI-1 is out: at most 18 words, every number from the ruling."""
    c = r["counts"]
    return f"Hoo. Pretty words, counselor. The record says {c['LOCKED']} locked, {c['STRUCK']} struck, {r['differ']} differ."


def objection(r: dict) -> str:
    """McClusky's line when ASI-1 is out: at most 18 words, every number from the ruling."""
    c = r["counts"]
    return (f"Objection! {c['LOCKED']} of {r['claims']} claims locked, fidelity {r['fidelity']}, credibility "
            f"{r['credibility_end']}. My client rests in peace.")
