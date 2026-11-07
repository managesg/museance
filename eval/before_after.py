"""Build cases/before_after.json and cases/BEFORE_AFTER.md: per app, per revival version, from committed evidence only.

python eval/before_after.py [--repo .] [--cases cases]
Sources: cases/<app>/repairs.jsonl (sha chain, scores, reason), cases/<app>/regression-result.json (HEAD file = last version;
oldest git revision whose pass count equals the first version's recorded score = first version), cases/<app>*.case.yml (fidelity),
git subject of the commit that added a repair line (builder). Anything not recoverable stays null ("not recorded").
Middle versions have no committed regression file, so only the scores a repair recorded are used for them. Denominators
(20 regression, 12 good, 8 trap) are the sizes of the app's committed regression set.
"""
import argparse, json, pathlib, re, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from metrics_report import parse_case  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILDERS = ("codex", "claude", "glm", "muse")  # revive/repair.py --builder choices
REG_RE = re.compile(r"regression(?: score)? (\d+)\s*->\s*(\d+)")
KEYS = ["regression_passed", "attack_mismatches", "traps_flagged", "false_strikes", "fidelity"]


def _pair(r, key):
    """[before, after] for a metric a repair recorded: a 2-list field, or parsed from the reason (regression only)."""
    if isinstance(r.get(key), list) and len(r[key]) == 2:
        return r[key]
    m = key == "regression" and REG_RE.search(r.get("reason") or "")
    return [int(m[1]), int(m[2])] if m else [None, None]


def _counts(rows):
    good, trap = [x for x in rows if x["kind"] == "good"], [x for x in rows if x["kind"] == "trap"]
    return dict(regression_passed=sum(x["passed"] for x in rows), traps_flagged=sum(not x["passed"] for x in trap),
                false_strikes=sum(not x["passed"] for x in good))


def _bs(b):
    """builders entry: a name, or (name, source commit/file)."""
    return b if isinstance(b, tuple) else (b, None)


def build_app(app, repairs, reg_old, reg_head, fid_old, fid_head, builders):
    """repairs: jsonl dicts in order; reg_old/reg_head: regression row lists (old may be None); fid_*: case fidelity or None."""
    n, rows = len(repairs), []
    sizes = dict(regression_total=len(reg_head), traps_of=sum(x["kind"] == "trap" for x in reg_head),
                 false_strikes_of=sum(x["kind"] == "good" for x in reg_head))
    for i in range(n + 1):
        out_r = repairs[i] if i < n else None  # repair that leaves this version
        side, r = (0, out_r) if out_r else (1, repairs[i - 1])
        row = dict(app=app, version=f"v{i + 1}", sha256=r["from_sha256"] if out_r else r["to_sha256"], **sizes,
                   regression_passed=_pair(r, "regression")[side], attack_mismatches=_pair(r, "mismatches")[side],
                   traps_flagged=None, false_strikes=_pair(r, "false_strikes")[side], fidelity=_pair(r, "fidelity")[side],
                   repair_claim=None, repair_decision=None, repair_builder=None, repair_builder_source=None, repair_reason=None, repair_to=None)
        if out_r:
            row.update(repair_claim=out_r.get("claim_id"), repair_decision=out_r.get("decision"), repair_builder=_bs(builders[i])[0], repair_builder_source=_bs(builders[i])[1],
                       repair_reason=out_r.get("reason"), repair_to=f"v{i + 2}")
        # a stored regression file counts for a version only when its pass count agrees with what the repair recorded
        rr = reg_head if i == n else reg_old if i == 0 else None
        if rr and row["regression_passed"] in (None, _counts(rr)["regression_passed"]):
            row.update(_counts(rr))
        if row["fidelity"] is None:
            row["fidelity"] = fid_head if i == n else fid_old if i == 0 else None
        for den, num in (("regression_total", "regression_passed"), ("traps_of", "traps_flagged"), ("false_strikes_of", "false_strikes")):
            row[den] = row[den] if row[num] is not None else None  # no denominator without a numerator
        row["not_recorded"] = [k for k in KEYS if row[k] is None]
        rows.append(row)
    return rows


def _git(repo, *a):
    p = subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, encoding="utf-8")
    return p.stdout if p.returncode == 0 else ""


def gather(repo, app):
    """Read repairs, regression files, case files and git history for one app; returns build_app's arguments."""
    cases = pathlib.Path(repo) / "cases"
    rp = f"cases/{app}/repairs.jsonl"
    repairs = [json.loads(l) for l in (cases / app / "repairs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    subject = {}  # to_sha256 -> (subject, short sha) of the first commit whose repairs.jsonl has it
    for rev in _git(repo, "log", "--reverse", "--format=%H", "--", rp).split():
        for l in _git(repo, "show", f"{rev}:{rp}").splitlines():
            if l.strip():
                subject.setdefault(json.loads(l)["to_sha256"], (_git(repo, "log", "-1", "--format=%s", rev).lower(), rev[:7]))
    builders = []  # (builder, source) per repair: the event's own builder field, else a builder named in the commit subject
    for r in repairs:
        subj, sha = subject.get(r["to_sha256"], ("", None))
        b = r.get("builder") or next((b for b in BUILDERS if re.search(rf"\b{b}\b", subj)), None)
        builders.append((b, "repairs.jsonl" if r.get("builder") else sha if b else None))
    regp = f"cases/{app}/regression-result.json"
    reg_head = json.loads((cases / app / "regression-result.json").read_text(encoding="utf-8"))
    want, reg_old, rev_old = _pair(repairs[0], "regression")[0], None, None
    for rev in reversed(_git(repo, "log", "--format=%H", "--", regp).split()):  # oldest first
        rows = json.loads(_git(repo, "show", f"{rev}:{regp}") or "null")
        if rows and _counts(rows)["regression_passed"] == want:
            reg_old, rev_old = rows, rev
            break
    cf = sorted(cases.glob(f"{app}*.case.yml"))
    fid = lambda t: parse_case(t).get("fidelity") if t else None  # noqa: E731
    return (app, repairs, reg_old, reg_head, fid(_git(repo, "show", f"{rev_old}:cases/{cf[0].name}")) if cf and rev_old else None,
            fid(cf[0].read_text(encoding="utf-8")) if cf else None, builders)


def _v(x):
    return "not recorded" if x is None else str(x)


def _of(x, n):
    return "not recorded" if x is None or n is None else f"{x}/{n}"


def render(rows):
    out = ["# Before and after repair", "",
           "Generated by `eval/before_after.py` from committed evidence only (`cases/<app>/repairs.jsonl`, `cases/<app>/regression-result.json` "
           "and its git history, `cases/*.case.yml`, commit subjects). A value missing from every committed file is `null` in the JSON and "
           "`not recorded` here; nothing is estimated.", "",
           "## JSON shape (`cases/before_after.json`)", "",
           "`{\"rows\": [ ... ]}`: one flat row per app and revival version. Keys: `app`, `version` (v1 = first revival), `sha256`, "
           "`regression_passed`, `regression_total`, `attack_mismatches`, `traps_flagged`, `traps_of`, `false_strikes`, `false_strikes_of`, "
           "`fidelity`, `repair_claim`, `repair_decision`, `repair_builder`, `repair_builder_source` (commit or file that proves the builder), `repair_reason`, `repair_to` (the repair that produced the next "
           "version; null on the last version), `not_recorded` (keys that are null because no committed file has them).", "",
           "`traps_flagged` = trap behaviors where the revival diverged from the original, i.e. traps the court caught. Fewer after repair "
           "means the revival now matches the original on them, not that the court got worse.", "",
           "Fidelity differs by source: todo v1 shows 35 because it is read from `repairs.jsonl`, which scores attacks only; the todo case file "
           "at 9a5877c shows 36 because it scores claims plus attacks.", ""]
    for app in dict.fromkeys(r["app"] for r in rows):
        out += [f"## {app}", "", "| Version | Regression | Attack mismatches | Traps flagged | False strikes | Fidelity | Repair that produced the next version |",
                "|---|---|---|---|---|---|---|"]
        for r in (x for x in rows if x["app"] == app):
            rep = "final" if not r["repair_to"] else (f"{r['repair_claim']} -> {r['repair_to']} ({r['repair_decision']}), builder "
                                                      f"{_v(r['repair_builder'])}"
                                                      f"{' (' + r['repair_builder_source'] + ')' if r['repair_builder_source'] else ''}"
                                                      f": {r['repair_reason']}")
            out.append(f"| {r['version']} | {_of(r['regression_passed'], r['regression_total'])} | {_v(r['attack_mismatches'])} | "
                       f"{_of(r['traps_flagged'], r['traps_of'])} | {_of(r['false_strikes'], r['false_strikes_of'])} | {_v(r['fidelity'])} | {rep} |")
        out.append("")
    return "\n".join(out)


def main(repo, cases):
    cases = pathlib.Path(cases)
    rows = []
    for d in sorted(p for p in cases.iterdir() if (p / "repairs.jsonl").is_file()):
        rows += build_app(*gather(repo, d.name))
    (cases / "before_after.json").write_text(json.dumps({"rows": rows}, indent=1) + "\n", encoding="utf-8", newline="\n")
    (cases / "BEFORE_AFTER.md").write_text(render(rows) + "\n", encoding="utf-8", newline="\n")
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(ROOT))
    ap.add_argument("--cases", default=str(ROOT / "cases"))
    a = ap.parse_args()
    main(a.repo, a.cases)
