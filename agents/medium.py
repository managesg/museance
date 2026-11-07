"""Medium: behavior sheet -> executable claim cards (claims.json). Model: ASI-1.

The model writes claim text, test steps and confidence. Code (no model) then enforces the contract:
steps only use the step grammar and known selectors, tier comes from the cited evidence, no evidence = FABRICATED,
bond is a fixed function of confidence, and each claim gets its commit hash.
usage: py -3 agents/medium.py app1 --selectors eval/regression/app1-selectors.json
"""
import argparse, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "agents"), str(ROOT / "eval")]
import llm
from commit import commit_hash

STEP = re.compile(r"^(click:(?P<c>.+)|type:(?P<t>[^:]+):.*|key:\w+|wait:\d+)$")
SYSTEM = """You are the Medium. You turn a behavior sheet about a dead web app into claim cards that a browser can test.
You never see the app's source. You get the sheet and the app's selectors (the controls and the display).
Return ONLY a JSON array. One object per behavior you are willing to bet on:
{"line": behavior id, "screen": ..., "text": the claim, "test": {"steps": [...], "observe": css selector, "expect": exact visible text},
 "confidence": 0..1 probability the original app really does this}
Step grammar: "click:<selector>", "type:<selector>:<text>", "key:<KeyName>", "wait:<ms>". Use only the given selectors.
Be calibrated: GUESSED behaviors and behaviors with conflicts get lower confidence. Skip behaviors you cannot test."""


def _selectors(sel):
    """All selector strings in the selectors JSON (any nesting)."""
    if isinstance(sel, str):
        return {sel}
    vals = sel.values() if isinstance(sel, dict) else sel
    return set().union(*(_selectors(v) for v in vals)) if vals else set()


def bond(conf):
    return round(250 * conf ** 2)  # ponytail: fixed curve, tune once Brier on app1 is measured


def cards(app, sheet, evidence, selectors, chat=llm.chat, provider="ASI1"):
    known, tier_of = _selectors(selectors), {e["id"]: e["tier"] for e in evidence}
    lines = {l["id"]: l for l in sheet["lines"]}
    user = json.dumps({"selectors": selectors, "sheet": sheet["lines"]}, ensure_ascii=False)
    out, dropped = [], []
    for c in llm.parse_json(chat(provider, SYSTEM, user)):
        t, line = c.get("test") or {}, lines.get(c.get("line"), {})
        steps, observe = t.get("steps") or [], t.get("observe")
        ok = steps and observe in known and all(
            (m := STEP.match(s)) and (m["c"] or m["t"] or "") in known | {""} for s in steps)
        if not ok or "expect" not in t or not c.get("text"):
            dropped.append(c.get("text") or c)
            continue
        ev = [e for e in line.get("citations", []) if e in tier_of]
        conf = min(1.0, max(0.0, float(c.get("confidence", 0.5))))
        claim = {"id": f"c{len(out) + 1:02d}", "app": app, "screen": str(c.get("screen") or line.get("screen") or "main"),
                 "text": c["text"], "test": {"steps": steps, "observe": observe, "expect": str(t["expect"])},
                 "tier": min((tier_of[e] for e in ev), default="D"),
                 "label": line.get("label", "GUESSED") if ev else "FABRICATED",
                 "evidence": ev, "confidence": conf, "bond": bond(conf)}
        claim["commit"] = commit_hash(claim)
        out.append(claim)
    return out, dropped


def main():
    p = argparse.ArgumentParser()
    p.add_argument("app")
    p.add_argument("--selectors", required=True)
    a = p.parse_args()
    run = ROOT / "runs" / a.app
    load = lambda f: json.loads(pathlib.Path(f).read_text(encoding="utf-8"))
    claims, dropped = cards(a.app, load(run / "sheet.json"), load(run / "evidence.json"), load(a.selectors))
    (run / "claims.json").write_text(json.dumps(claims, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(claims)} claims, {len(dropped)} dropped (bad steps/selectors) -> {run / 'claims.json'}")
    for d in dropped:
        print("  dropped:", d)


if __name__ == "__main__":
    main()
