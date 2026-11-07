"""Deterministic words for the stage and the chat: one caption per mesh event, plus reply templates.

caption(event, payload) is the one-line subtitle stored with every mesh.<event> ledger event and sent as
Progress.text. Every joke carries a real number from the case. No model in here: the Bailiff has none.
"""
from __future__ import annotations

from agents.mesh.commands import COMMANDS

DEADPAN = "The Bailiff has no opinion. The Bailiff has no model."
NAMES = {"mcclusky": "McClusky, Esq.", "hoot": "Dr. Hoot", "bailiff": "The Bailiff", "clerk": "The Clerk"}
OFFLINE = {  # base.persona's default line when ASI-1 is out
    "mcclusky": "Objection, Your Honor: my brain is in recess. My 3 commands still work: claims, credibility, why c03.",
    "hoot": "Hoo. My banter is offline, but my 3 commands are not: attacks, seal, reveal.",
}
STATUSES = ("LOCKED", "STRUCK", "FABRICATED", "UNSWORN")


def short(s, n: int = 60) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 3] + "..."


def _counts(c: dict) -> str:
    return ", ".join(f"{c.get(k, 0)} {k}" for k in STATUSES)


def _delta(r: dict) -> str:
    return f"{r['credibility_start']} -> {r['credibility_end']} ({r['credibility_end'] - r['credibility_start']:+d})"


def _summon(p: dict) -> str:
    if p["who"] == "hoot" and p["for"] == "seal":
        return "The Bailiff summons Dr. Hoot to seal his attacks before anyone testifies. Envelopes only, Doctor."
    if p["who"] == "mcclusky":
        return "The Bailiff calls McClusky, Esq. to the stand. Credibility on entry: 1000."
    return f"The Bailiff asks Dr. Hoot to open his {p.get('attacks', 0)} envelopes."


def _sealed(p: dict) -> str:
    match = (f"they match the seal P4 committed at {p['p4_sealed_utc']}" if p.get("p4_match")
             else "they do NOT match the seal P4 committed to git")
    return f"Dr. Hoot seals {p['attacks']} attacks (sha256 {p['attacks_sha256'][:8]}); {match}. No peeking, counselor."


def _testimony(p: dict) -> str:
    s = (f"McClusky, Esq. swears to {p['claims']} claims, {p['fabricated']} of them FABRICATED, and bets "
         f"{p['bond']} credibility on them.")
    if p.get("dropped"):
        s += f" {p['dropped']} cards broke the contract and went in the shredder."
    if p.get("refused"):
        s += f" {len(p['refused'])} refused: their commit does not match their content."
    return s


def _reveal(p: dict) -> str:
    n = p["accepted"] + len(p["refused"])
    s = f"Dr. Hoot opens {n} envelopes: {p['accepted']} attacks match their seals"
    s += f", {len(p['refused'])} thrown out." if p["refused"] else ". Not one forgery."
    if p.get("p4_problems"):
        s += f" P4's git seal flags {len(p['p4_problems'])} problems."
    return s


def _court(p: dict) -> str:
    n = p["claims"] + p["attacks"]
    return (f"Court is in session: {p['claims']} claims and {p['attacks']} attacks, each run twice on the original "
            f"and twice on the revival. {4 * n} page loads, zero models.")


def _ruling(p: dict) -> str:
    return f"Ruling: {_counts(p['counts'])}. Fidelity {p['fidelity']}. McClusky's credibility {_delta(p)}."


def _closed(p: dict) -> str:
    return (f"Case {p['case_id']} closed. Scoreboard: Dr. Hoot {p['catches']} catches in {p['attacks']} attacks; "
            f"McClusky, Esq. {p['credibility_end']} credibility ({p['credibility_end'] - p['credibility_start']:+d}). "
            f"{DEADPAN}")


CAPTIONS = {
    "open": lambda p: (f"All rise. Case {p['case_id']}: {p['app']} versus its own revival, on {p['evidence']} "
                       f"pieces of evidence and a {p['lines']}-line behavior sheet. {DEADPAN}"),
    "summon": _summon,
    "sealed": _sealed,
    "testimony": _testimony,
    "reveal": _reveal,
    "court": _court,
    "ruling": _ruling,
    "remark": lambda p: f"{NAMES[p['speaker']]}: {p['text']}",
    "closed": _closed,
    "adjourned": lambda p: f"Case {p['case_id']} adjourned: {p['reason']}. {DEADPAN}",
}


def caption(event: str, payload: dict) -> str:
    """One line, always: the stage UI shows it as a subtitle."""
    return " ".join(CAPTIONS[event](payload).split())


# --- the ruling, in chat -------------------------------------------------------------------------------
def funniest(s: dict) -> str:
    """One STRUCK claim as a line (case.ruling picks the most overconfident)."""
    return (f'{s["id"]}: McClusky swore "{short(s["text"])}" at {s["confidence"]:.0%}; the original says '
            f'"{short(s["original"], 40)}". {s["bond"]} credibility, gone.')


def ruling_text(r: dict) -> str:
    lines = [f"RULING, case {r['case_id']} ({r['app']})",
             " | ".join(f"{k} {r['counts'].get(k, 0)}" for k in STATUSES),
             f"Fidelity {r['fidelity']} | Credibility {_delta(r)} | Brier {r['brier']}",
             f"Scoreboard: Dr. Hoot {r['catches']} catches in {r['attacks']} attacks | "
             f"McClusky, Esq. {r['credibility_end']} credibility"]
    if r.get("funniest"):
        lines.append(f"Funniest strike: {r['funniest']}")
    if r.get("chain"):
        lines.append(f"Ledger: {r['chain']}")
    return "\n".join(lines)


def taunt(r: dict) -> str:
    """Dr. Hoot's closing remark: deterministic, one line per STRUCK claim (max 3), with the numbers."""
    struck = sorted(r["struck"], key=lambda s: (-s["confidence"], -s["bond"], s["id"]))
    if not struck:
        return (f"Zero strikes? {r['counts'].get('LOCKED', 0)} LOCKED of {r['claims']}? Hoo. My {r['catches']} "
                f"catches say the revival still drifts. Fidelity {r['fidelity']}, counselor.")
    parts = [f"Struck! {s['id']}: you swore \"{short(s['expect'], 30)}\", the original says "
             f"\"{short(s['original'], 30)}\". That is {s['bond']} points, counselor." for s in struck[:3]]
    if len(struck) > 3:
        parts.append(f"And {len(struck) - 3} more.")
    parts.append(f"Scoreboard: {r['catches']} catches for me, {r['credibility_end']} credibility for you.")
    return " ".join(parts)


def objection(r: dict) -> str:
    """McClusky's closing remark when ASI-1 is out (or SEANCE_FAKE_LLM=1)."""
    n, k = r["claims"], r["counts"].get("STRUCK", 0)
    if not k:
        return (f"The defense rests: {r['counts'].get('LOCKED', 0)} LOCKED, 0 STRUCK. Dr. Hoot, your "
                f"{r['catches']} catches were against the revival, not against me.")
    return (f"Objection! {n - k} of my {n} claims still stand, {round(100 * (n - k) / n)}% of the testimony; my "
            f"client has had worse days, mostly the day it died. Credibility {r['credibility_end']}, and climbing "
            f"on appeal.")


def objection_prompt(r: dict, answer: str) -> str:
    """What McClusky's ASI-1 voice is told after the ruling (facts only, so every number is real)."""
    return (f"Facts, use only these numbers: case {r['case_id']} on the app {r['app']}. Court ruling: "
            f"{_counts(r['counts'])} out of {r['claims']} claims. Your credibility went {_delta(r)}. Fidelity "
            f"{r['fidelity']}. Dr. Hoot made {r['catches']} catches in {r['attacks']} attacks. "
            f"Your worst strike: {r.get('funniest') or 'none'}. Dr. Hoot just said: \"{answer}\". "
            f"Object to the court in one or two short sentences, citing at least one of these numbers.")


# --- reply templates -------------------------------------------------------------------------------------
def help_card(role: str) -> str:
    head = {"bailiff": "The Bailiff. Commands:",
            "mcclusky": "McClusky, Esq., counsel for the dearly departed. Commands:",
            "hoot": "Dr. Hoot, skeptic, owl, never wrong. Commands:"}[role]
    rows = [f"  {ex:<44} {what}" for _, ex, what in COMMANDS[role].values()]
    tail = {"bailiff": DEADPAN, "mcclusky": "Anything else, and I will argue with you for free.",
            "hoot": "Anything else is banter. Hoo."}[role]
    return "\n".join([head, *rows, tail])


def docket(apps: dict) -> str:
    """apps: case.apps() -> {app: '' when ready, else what is missing}."""
    if not apps:
        return "The docket is empty."
    return "Docket: " + "; ".join(f"{a} (ready)" if not why else f"{a} (not ready: {why})" for a, why in apps.items())


def refusal(app: str, apps: dict) -> str:
    if app in apps:
        return f"{app} is on the docket but not ready: {apps[app]}. {docket(apps)}"
    return (f"The court cannot raise {app!r}: 0 pieces of evidence on file, and the Bailiff does not hold seances "
            f"on hearsay. {docket(apps)}")


def busy(case_id: str, app: str) -> str:
    return f"Court is in session: case {case_id} ({app}). One ghost at a time. {DEADPAN}"


def no_case(app: str = "") -> str:
    where = f" for {app}" if app else ""
    return f"No ruling on file{where}. 0 cases, 0 opinions. Say: raise todo"


def status(last: dict, claim: str = "") -> str:
    """last: case.last_case(); claim: 'c03' for one claim, '' for the case."""
    r = last.get("ruling")
    if not r:
        return no_case(last.get("app", ""))
    if not claim:
        return ruling_text(r)
    c = next((c for c in last["claims"] if c["id"] == claim), None)
    lock = next((x for x in last["locks"] if x["claim_id"] == claim), None)
    if not c or not lock:
        return f"No claim {claim} in case {r['case_id']}; it had {len(last['claims'])} claims. {DEADPAN}"
    return (f"{claim} {lock['status']}: \"{short(c['text'])}\" ({lock['reason']}). "
            f"Sworn at {c['confidence']:.0%} for a bond of {c['bond']}.")


def ledger_line(app: str, events: int, check: str, head: str) -> str:
    """check: court.ledger.verify()'s message, which already leads with the count when the chain is intact."""
    return f"Ledger for {app}: {events} events, {check.removeprefix(f'{events} events, ')}. Head {head[:12]}. {DEADPAN}"


def cross_result(app: str, steps: list, observe: str, v: dict) -> str:
    said = f"original says \"{short(v['original'], 50)}\", revival says \"{short(v['revival'], 50)}\""
    if v["flaky"]:
        verdict = "UNSWORN: the same build answered two different ways in two runs"
    elif v["match"]:
        verdict = "they agree, twice each"
    else:
        verdict = f"MISMATCH, smallest repro in {len(v['shrunk_steps'])} steps: {' '.join(v['shrunk_steps'])}"
    return f"Cross on {app}, {len(steps)} steps, watching {observe}: {said}. {verdict}. {DEADPAN}"


def cross_refused(reason: str) -> str:
    """reason: a commands.CrossError message."""
    return f"Objection sustained: {reason}. {DEADPAN}"


def rate_limited(seconds: float) -> str:
    return f"One cross per witness every 10 seconds. Wait {max(1, round(seconds))} more. {DEADPAN}"


def attacks_line(app: str, seal: dict, screens: dict) -> str:
    per = ", ".join(f"{k} {v}" for k, v in sorted(screens.items()))
    return (f"{len(seal['attacks'])} attacks on {app}, sealed (sha256 {seal['attacks_sha256'][:8]}): {per}. "
            f"The steps stay in the envelope until the court rules. Hoo.")


def seal_line(app: str, seal: dict, p4: dict) -> str:
    same = all(p4.get(k) == seal[k] for k in ("attacks_sha256", "regression_sha256"))  # what hear() checks too
    match = f"matches the seal P4 committed at {p4.get('created_utc')}" if same else "does NOT match P4's git seal"
    return (f"Seal for {app}: {len(seal['attacks'])} attacks, attacks sha256 {seal['attacks_sha256'][:12]}, "
            f"regression sha256 {seal['regression_sha256'][:12]}; it {match}.")


def reveal_refused(n: int) -> str:
    return f"Hoo hoo, no. {n} attacks stay sealed until the court rules. Ask the Bailiff to raise a case."


def reveal_list(app: str, attacks: list, verdicts: list) -> str:
    by = {v["ref"]: v for v in verdicts if v["kind"] == "attack"}
    caught = [a for a in attacks if a["id"] in by and not by[a["id"]]["match"] and not by[a["id"]]["flaky"]]
    rows = [f"  {a['id']} {a['screen']}: {short(' '.join(a['steps']), 70)} -> original "
            f"\"{short(by[a['id']]['original'], 25)}\", revival \"{short(by[a['id']]['revival'], 25)}\""
            for a in caught[:5]]
    return "\n".join([f"Revealed for {app}: {len(attacks)} attacks, {len(caught)} caught the revival.", *rows])


def claims_list(app: str, claims: list, locks: list) -> str:
    st = {x["claim_id"]: x["status"] for x in locks}
    rows = [f"  {c['id']} [{c['tier']}, {c['confidence']:.0%}, bond {c['bond']}] {st.get(c['id'], 'PENDING')}: "
            f"{short(c['text'])}" for c in claims[:15]]
    more = [f"  ...and {len(claims) - 15} more."] if len(claims) > 15 else []
    return "\n".join([f"My sworn testimony on {app}: {len(claims)} claims.", *rows, *more])


def credibility_line(r: dict) -> str:
    return (f"Credibility {_delta(r)}, Brier {r['brier']}, {r['counts'].get('LOCKED', 0)} LOCKED. "
            f"A rounding error, Your Honor.")


def why_line(c: dict, lock: dict | None) -> str:
    court = f"Court: {lock['status']}, {lock['reason']}." if lock else "The court has not ruled on it yet."
    ev = ", ".join(c.get("evidence") or []) or "no evidence (that is what FABRICATED means)"
    return (f"{c['id']}: \"{short(c['text'])}\". Tier {c['tier']}, {c['label']}, evidence: {ev}. "
            f"Sworn at {c['confidence']:.0%} for a bond of {c['bond']}. {court}")
