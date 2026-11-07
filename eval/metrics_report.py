"""Write cases/METRICS.md from cases/*.case.yml (+ cases/<app>/repairs.jsonl, regression-result.json). Measured values only.

python eval/metrics_report.py [--cases cases] [--runs cases] [--out cases/METRICS.md]
Nothing is invented: a missing or null value prints "not measured yet".
"""
import argparse, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
NM = "not measured yet"
HOW = {  # one sentence each, same definitions as CONTRACTS.md
    "Regression": "Revival behaviors that match the original on the regression set (good + trap), passed/total from check_revival.",
    "False strikes": "Good behaviors (the original's known-correct ones) the revival got wrong, out of all good behaviors.",
    "Traps caught": "Trap behaviors where the revival diverged from the original, out of all traps.",
    "Fidelity": "100 * matched / (matched + mismatched) over court verdicts, flaky excluded.",
    "Brier": "Mean over claims of (confidence - claim_true)^2; n is claims minus unsworn.",
    "Credibility": "Starts at 1000; STRUCK loses bond, LOCKED gains round(bond * (1 - confidence)).",
    "Repairs": "Count of decisions (patched, rollback, unsworn) in the repair log; patched = narrow fix kept, rollback = fix dropped the regression score, unsworn = builder could not fix.",
}


def parse_case(text):
    """Parse the flat YAML that eval/case_file.py writes (JSON scalars, '  - json' lists, '  k: json' maps)."""
    out, key = {}, None
    for line in text.splitlines():
        if line.startswith("  - "):
            if out[key] is None:
                out[key] = []
            out[key].append(json.loads(line[4:]))
        elif line.startswith("  "):
            k, v = line.strip().split(": ", 1)
            if out[key] is None:
                out[key] = {}
            out[key][k] = json.loads(v)
        elif line.strip():
            key, v = line.split(":", 1)
            v = v.strip()
            out[key] = [] if v == "[]" else json.loads(v) if v else None
    return out


def _rel(p):
    p = pathlib.Path(p).resolve()
    return (p.relative_to(ROOT) if p.is_relative_to(ROOT) else p).as_posix()


def _frac(x, n):
    return NM if x is None or n is None else f"{x}/{n}"


def _read_jsonl(path):
    if not path.is_file():
        return None
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def app_section(case_path, runs):
    case = parse_case(case_path.read_text(encoding="utf-8"))
    c = case.get("counts") or {}
    sources = [_rel(case_path)]
    run_dir = runs / str(case.get("app", "")).removesuffix("-fixture")

    reg = None
    rf = run_dir / "regression-result.json"
    if rf.is_file():
        rows = json.loads(rf.read_text(encoding="utf-8"))
        reg = (sum(1 for r in rows if r["passed"]), len(rows))
        sources.append(_rel(rf))
    reps = _read_jsonl(run_dir / "repairs.jsonl")
    if reps is not None:
        sources.append(_rel(run_dir / "repairs.jsonl"))

    n = None if c.get("claims") is None or c.get("unsworn") is None else c["claims"] - c["unsworn"]
    brier = case.get("brier")
    cs, ce = case.get("credibility_start"), case.get("credibility_end")
    rows = [
        ("Regression", NM if reg is None else f"{reg[0]}/{reg[1]}"),
        ("False strikes", _frac(c.get("false_strikes"), c.get("false_strikes_of"))),
        ("Traps caught", _frac(c.get("traps_caught"), c.get("traps_of"))),
        ("Fidelity", NM if case.get("fidelity") is None else str(case["fidelity"])),
        ("Brier", NM if brier is None or n is None else f"{brier} (n={n})"),
        ("Credibility", NM if cs is None or ce is None else f"{cs} -> {ce}"),
        ("Repairs", NM if reps is None else
            "patched {}, rollback {}, unsworn {}".format(*(sum(r.get("decision") == d for r in reps) for d in ("patched", "rollback", "unsworn")))),
    ]
    out = [f"## {case.get('app', case_path.stem)}", "", "Source: " + ", ".join(f"`{s}`" for s in sources), "",
           "| Metric | Value | How measured |", "|---|---|---|"]
    out += [f"| {m} | {v} | {HOW[m]} |" for m, v in rows]
    missing = [m for m, v in rows if v == NM]
    out += ["", "Not measured yet: " + (", ".join(missing) if missing else "none") + ".", ""]
    return "\n".join(out)


def regression_section(app, run_dir):
    """Apps with court regression runs but no case file yet (no claims): regression rows only."""
    rf, of = run_dir / "regression-result.json", run_dir / "original-regression-result.json"
    rows = json.loads(rf.read_text(encoding="utf-8"))
    good, traps = [r for r in rows if r["kind"] == "good"], [r for r in rows if r["kind"] == "trap"]
    sources = [_rel(rf)]
    table = [("Regression", f"{sum(r['passed'] for r in rows)}/{len(rows)}"),
             ("False strikes", f"{sum(not r['passed'] for r in good)}/{len(good)}"),
             ("Traps caught", f"{sum(not r['passed'] for r in traps)}/{len(traps)}")]
    if of.is_file():
        orig = [r for r in json.loads(of.read_text(encoding="utf-8")) if r["kind"] == "good"]
        table.append(("Original false strikes", f"{sum(not r['passed'] for r in orig)}/{len(orig)}"))
        sources.append(_rel(of))
    HOW["Original false strikes"] = "The original app run through the same court runner as its own revival; good behaviors it fails, out of all good behaviors (should be 0)."
    out = [f"## {app}", "", "Source: " + ", ".join(f"`{s}`" for s in sources), "", "| Metric | Value | How measured |", "|---|---|---|"]
    out += [f"| {m} | {v} | {HOW[m]} |" for m, v in table]
    return "\n".join(out + ["", "Not measured yet: Fidelity, Brier, Credibility, Repairs (no claims or case file for this app yet).", ""])


def report(cases, runs):
    parts = ["# P4 metrics", "", "Generated by `eval/metrics_report.py`. Only values read from the source files below; nothing is rounded up or estimated.", ""]
    parts += [app_section(p, runs) for p in sorted(cases.glob("*.case.yml"))]
    have = {p.name.removesuffix(".case.yml").removesuffix("-fixture") for p in cases.glob("*.case.yml")}
    parts += [regression_section(d.name, d) for d in sorted(runs.iterdir() if runs.is_dir() else [])
              if d.is_dir() and d.name not in have and (d / "regression-result.json").is_file()]
    return "\n".join(parts)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=str(ROOT / "cases"))
    ap.add_argument("--runs", default=str(ROOT / "cases"), help="folder of <app>/regression-result.json, repairs.jsonl (committed under cases/)")
    ap.add_argument("--out")
    a = ap.parse_args()
    cases = pathlib.Path(a.cases)
    with open(a.out or cases / "METRICS.md", "w", encoding="utf-8", newline="\n") as f:
        f.write(report(cases, pathlib.Path(a.runs)))
