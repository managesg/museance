"""Build the case file. CLI: python eval/case_file.py <claims.json> <verdicts.json> <app> [--regression-result r.json] > cases/<app>.case.yml"""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from score import brier, credibility, fidelity, statuses  # noqa: E402

START = 1000


def regression_counts(regression):
    """false_strikes: good behaviors that failed; traps_caught: traps that diverged. None (not 0) without a run."""
    keys = ("false_strikes", "false_strikes_of", "traps_caught", "traps_of")
    if regression is None:
        return dict.fromkeys(keys)
    for r in regression:
        if r.get("kind") not in ("good", "trap") or not isinstance(r.get("passed"), bool):
            raise ValueError(f"bad regression row (need kind good|trap and bool passed): {r!r}")
    good = [r for r in regression if r["kind"] == "good"]
    traps = [r for r in regression if r["kind"] == "trap"]
    return dict(zip(keys, (sum(not r["passed"] for r in good), len(good), sum(not r["passed"] for r in traps), len(traps))))


def build_case(app, claims, verdicts, regression=None):
    st = statuses(claims, verdicts)
    groups = {k: [] for k in ("LOCKED", "STRUCK", "FABRICATED", "UNSWORN")}
    for c in claims:
        groups[st[c["id"]]].append(f'{c["screen"]}: {c["text"]} [{c["tier"]}]')
    return {
        "app": app,
        "fidelity": fidelity(verdicts),
        "brier": round(brier(claims, verdicts), 3),
        "credibility_start": START,
        "credibility_end": credibility(claims, verdicts, START),
        "locked": groups["LOCKED"],
        "struck": groups["STRUCK"],
        "fabricated": groups["FABRICATED"],
        "unsworn": groups["UNSWORN"],
        "counts": {"claims": len(claims), **{k.lower(): len(v) for k, v in groups.items()},
                   **regression_counts(regression)},
    }


def _q(s):
    return json.dumps(s, ensure_ascii=False)  # JSON strings are valid YAML scalars


def to_yaml(case):
    lines = []
    for k, v in case.items():
        if isinstance(v, list):
            lines.append(f"{k}:" if v else f"{k}: []")
            lines += [f"  - {_q(x)}" for x in v]
        elif isinstance(v, dict):
            lines.append(f"{k}:")
            lines += [f"  {kk}: {json.dumps(vv)}" for kk, vv in v.items()]  # None -> null
        else:
            lines.append(f"{k}: {_q(v) if isinstance(v, str) else v}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("claims"), ap.add_argument("verdicts"), ap.add_argument("app")
    ap.add_argument("--regression-result", help="JSON list of {id, kind, passed} from revive/check_revival.py --json")
    a = ap.parse_args()
    load = lambda p: json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stdout.write(to_yaml(build_case(a.app, load(a.claims), load(a.verdicts),
                                        load(a.regression_result) if a.regression_result else None)))
