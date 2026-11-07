"""Pure scoring per CONTRACTS.md (stdlib only). Claims and verdicts are lists of dicts."""


def _by_ref(verdicts):
    return {v["ref"]: v for v in verdicts if v.get("kind", "claim") == "claim"}


def _state(claim, v):
    """LOCKED / STRUCK / UNSWORN for one claim (no verdict or flaky -> UNSWORN)."""
    if v is None or v.get("flaky"):
        return "UNSWORN"
    return "LOCKED" if v["claim_true"] else "STRUCK"


def statuses(claims, verdicts):
    vs = _by_ref(verdicts)
    out = {}
    for c in claims:
        s = _state(c, vs.get(c["id"]))
        out[c["id"]] = "FABRICATED" if c.get("label") == "FABRICATED" and s != "STRUCK" else s
    return out


def credibility(claims, verdicts, start=1000):
    vs = _by_ref(verdicts)
    total = start
    for c in claims:
        s = _state(c, vs.get(c["id"]))
        if s == "LOCKED":
            total += round(c["bond"] * (1 - c["confidence"]))
        elif s == "STRUCK":
            total -= c["bond"]
    return int(total)


def brier(claims, verdicts):
    vs = _by_ref(verdicts)
    errs = [(c["confidence"] - (1 if vs[c["id"]]["claim_true"] else 0)) ** 2
            for c in claims if c["id"] in vs and not vs[c["id"]].get("flaky")]
    return sum(errs) / len(errs) if errs else 0.0


def fidelity(verdicts):
    live = [v for v in verdicts if not v.get("flaky")]
    if not live:
        return 0
    return round(100 * sum(1 for v in live if v["match"]) / len(live))
