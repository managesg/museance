"""P4 stage replay on the todo app: seal -> court on revival v1 -> repair -> court on v2 -> final numbers.

python eval/demo_p4.py [--fast] [--live]

Default is deterministic, offline, no model: every number is read from a committed file and labelled
with it. --live re-runs the court's regression set (Playwright; COURT_BROWSER_CHANNEL=chrome uses installed Chrome) on v1
and v2 and prints the fresh numbers next to the committed ones; if that fails it says so and falls back.
"""
import argparse, contextlib, hashlib, io, json, pathlib, subprocess, sys, tempfile, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "eval"), str(ROOT)]
from metrics_report import parse_case  # noqa: E402

C, OUT = ROOT / "cases", ROOT / "revive/out/todo"
REG, ATK, SEAL = ROOT / "eval/regression/todo.json", C / "todo/attacks.json", C / "todo.commits.json"
load = lambda p: json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
rel = lambda p: str(pathlib.Path(p).relative_to(ROOT)).replace("\\", "/")
sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes().replace(b"\r\n", b"\n")).hexdigest()  # CRLF-proof


sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # court prints observed page text


class Show:
    def __init__(self, fast):
        self.fast = fast

    def head(self, n, title):
        print(f"\n[{n}] {title}")
        self.pause()

    def row(self, label, value, src):
        print(f"    {label:<32}{str(value):<30}<- {src}")
        self.pause(0.25)

    def pause(self, s=0.9):
        if not self.fast:
            time.sleep(s)


def seal_check():
    cmd = [sys.executable, str(ROOT / "eval/seal.py"), "--app", "todo", "--regression", str(REG),
           "--attacks", str(ATK), "--out", str(SEAL), "--verify"]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return p.returncode == 0, (p.stdout + p.stderr).strip().splitlines()


def live_court(html_path, tmp):
    """Fresh court run of one revival on the regression set: (passed, total). Raises on any failure."""
    from court import regression
    d = pathlib.Path(tmp) / html_path.stem
    d.mkdir()
    (d / "index.html").write_bytes(html_path.read_bytes())
    rep = d / "report.json"
    orig = ROOT / "apps/todo/original"
    regression.main([str(REG), "--original-dir", str(orig), "--revival-dir", str(d), "--out", str(rep)])
    rows = load(rep)["rows"]
    return sum(1 for r_ in rows if not r_["mismatch"]), len(rows)  # attacks (105 x 2 runs) take ~10 min per build: not live


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--fast", action="store_true", help="no pauses")
    ap.add_argument("--live", action="store_true", help="re-run the court on v1 and v2 (needs Playwright)")
    a = ap.parse_args(argv)
    s = Show(a.fast)

    rows = {r["version"]: r for r in load(C / "before_after.json")["rows"] if r["app"] == "todo"}
    v1, v2 = rows["v1"], rows["v2"]
    rep = [json.loads(l) for l in (C / "todo/repairs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()][0]
    case = parse_case((C / "todo.case.yml").read_text(encoding="utf-8"))
    orig = load(C / "todo/original-regression-result.json")
    reg2 = load(C / "todo/regression-result.json")
    verd = load(C / "todo/verdicts.json")
    BA, REGF, VERF = rel(C / "before_after.json"), rel(C / "todo/regression-result.json"), rel(C / "todo/verdicts.json")
    live = {}
    if a.live:
        print("--live: re-running the court on v1 and v2 (regression set, about 2 min per build)...", flush=True)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                with contextlib.redirect_stdout(io.StringIO()):  # court is chatty
                    live = {v: live_court(OUT / f, tmp) for v, f in (("v1", "index.v1.html"), ("v2", "index.html"))}
        except Exception as e:  # noqa: BLE001 - any failure falls back to evidence
            print(f"--live failed ({type(e).__name__}: {str(e)[:120]}); using committed evidence only.")

    print("SEANCE / P4 - todo app: a revival is judged, caught wrong, repaired, re-judged")
    ok = True

    s.head(1, "SEAL: tests were locked before the revival was built")
    good, out = seal_check()
    ok &= good
    s.row("seal.py --verify", "OK" if good else "FAILED", f"{rel(SEAL)}, {rel(REG)}, {rel(ATK)}")
    if not good:
        print("\n".join("    " + l for l in out[:5]))
    s.row("sealed attacks", len(load(SEAL)["attacks"]), rel(SEAL))
    s.row("sealed at (UTC)", load(SEAL)["created_utc"], rel(SEAL))

    def court(n, title, ver, row, html, label):
        s.head(n, title)
        s.row("revival sha256", sha(html)[:12], f"{rel(html)} (matches repairs.jsonl: {sha(html) == rep[label]})")
        s.row("regression passed", f"{row['regression_passed']}/{row['regression_total']}", BA)
        s.row("traps flagged (diverged)", f"{row['traps_flagged']}/{row['traps_of']}", BA)
        s.row("false strikes", f"{row['false_strikes']}/{row['false_strikes_of']}", BA)
        s.row("attack mismatches", f"{row['attack_mismatches']}/{len(load(SEAL)['attacks'])}", BA)
        s.row("fidelity (attacks only)", row["fidelity"], BA)
        if ver in live:
            s.row("LIVE regression re-run", "%d/%d" % live[ver], "court.regression on this machine")

    s.head("2a", "BASELINE: the original app against its own regression set")
    s.row("original regression passed", f"{sum(r['passed'] for r in orig)}/{len(orig)}", rel(C / "todo/original-regression-result.json"))
    court("2b", "COURT on revival v1 (first build) vs original", "v1", v1, OUT / "index.v1.html", "from_sha256")

    s.head(3, "REPAIR: court evidence goes back to the builder")
    s.row("builder", v1["repair_builder"], BA)
    s.row("decision", rep["decision"], rel(C / "todo/repairs.jsonl"))
    s.row("reason", "", rel(C / "todo/repairs.jsonl"))
    print(f"      {rep['reason']}")
    s.row("from sha256", rep["from_sha256"][:12], "repairs.jsonl")
    s.row("to sha256", rep["to_sha256"][:12], "repairs.jsonl")

    court(4, "COURT on revival v2 (repaired) vs original", "v2", v2, OUT / "index.html", "to_sha256")
    m2 = sum(1 for v in verd if not v["match"] and not v["flaky"])
    s.row("cross-check: regression passed", f"{sum(r['passed'] for r in reg2)}/{len(reg2)}", REGF)
    s.row("cross-check: mismatches", f"{m2}/{len(verd)} verdicts", VERF)

    s.head(5, "FINAL NUMBERS")
    CF = rel(C / "todo.case.yml")
    s.row("fidelity (attacks only)", f"{v1['fidelity']} -> {case['fidelity']}", f"{BA} / {CF}")
    print("      (all-verdict fidelity per CONTRACTS.md, 105 attacks + 16 claims: 41 -> 100 as on the stage and in DEMO.md;"
          " the 41 is from the uncommitted runs/ v1 court run. Committed v1 verdicts at 9a5877c (8 claims + 105 attacks): 36)")
    s.row("attack mismatches", f"{v1['attack_mismatches']} -> {v2['attack_mismatches']}", BA)
    s.row("regression", f"{v1['regression_passed']} -> {v2['regression_passed']} of {v2['regression_total']}", BA)
    s.row("claims locked / struck", f"{case['counts']['locked']} / {case['counts']['struck']} of {case['counts']['claims']}", CF)
    s.row("false strikes", f"{case['counts']['false_strikes']} of {case['counts']['false_strikes_of']}", CF)
    s.row("Brier score", case["brier"], CF)
    s.row("credibility", f"{case['credibility_start']} -> {case['credibility_end']}", CF)
    s.pause(0.5)
    print("\nAll numbers above are read from committed files. No model was called."
          + (" Live court re-run shown where marked." if live else ""))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
