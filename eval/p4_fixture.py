"""P4 fixture pipeline: skeptic attacks -> revival check -> score -> case file -> one summary block.

python eval/p4_fixture.py [--revival runs/app1/revival/index.html] [--write-case]

The case file goes to runs/<app>/ (gitignored); --write-case updates the committed cases/ file.
"""
import argparse, json, pathlib, re, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from case_file import build_case, to_yaml  # noqa: E402
from skeptic import generate  # noqa: E402

load = lambda p: json.loads(pathlib.Path(p).read_text(encoding="utf-8"))


def regression_run(revival):
    """Return (summary line, [{id, kind, passed}] or None when no revival was checked)."""
    revival = pathlib.Path(revival)
    if not revival.is_file():
        return f"skipped (no revival at {revival})", None
    r = subprocess.run([sys.executable, str(ROOT / "revive/check_revival.py"), "--json", str(revival)], capture_output=True, text=True)
    try:
        rows = json.loads(r.stdout)
    except ValueError:
        return f"error (exit {r.returncode}): {r.stderr.strip()[-200:]}", None
    return f"{sum(x['passed'] for x in rows)}/{len(rows)}", rows


def run(app="app1", revival=ROOT / "runs/app1/revival/index.html", attacks_out=None, case_out=None, write_case=False):
    attacks_out = pathlib.Path(attacks_out or ROOT / f"runs/{app}/attacks.json")
    case_out = pathlib.Path(case_out or ROOT / ("cases" if write_case else f"runs/{app}") / f"{app}-fixture.case.yml")
    attacks = generate(app, load(ROOT / f"eval/regression/{app}-selectors.json"))
    attacks_out.parent.mkdir(parents=True, exist_ok=True)
    attacks_out.write_text(json.dumps(attacks, indent=1), encoding="utf-8")
    reg, rows = regression_run(revival)
    case = build_case(f"{app}-fixture", load(ROOT / "fixtures/claims.json"), load(ROOT / "fixtures/verdicts.json"), rows)
    case_out.parent.mkdir(parents=True, exist_ok=True)
    with open(case_out, "w", encoding="utf-8", newline="\n") as f:
        f.write(to_yaml(case))
    print(f"== P4 fixture pipeline: {app} ==\n"
          f"attacks:       {len(attacks)} -> {attacks_out}\n"
          f"regression:    {reg}\n"
          f"fidelity:      {case['fidelity']}\n"
          f"brier:         {case['brier']}\n"
          f"credibility:   {case['credibility_start']} -> {case['credibility_end']}\n"
          f"case file:     {case_out}")
    return {"attacks": len(attacks), "regression": reg, **case}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--app", default="app1")
    p.add_argument("--revival", default=str(ROOT / "runs/app1/revival/index.html"))
    p.add_argument("--write-case", action="store_true", help="update the tracked cases/ file")
    a = p.parse_args()
    run(a.app, a.revival, write_case=a.write_case)
