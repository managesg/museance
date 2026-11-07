"""Build the case file. CLI: python eval/case_file.py <claims.json> <verdicts.json> <app> > cases/<app>.case.yml"""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from score import brier, credibility, fidelity, statuses  # noqa: E402

START = 1000


def build_case(app, claims, verdicts):
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
        "counts": {"claims": len(claims), **{k.lower(): len(v) for k, v in groups.items()}},
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
            lines += [f"  {kk}: {vv}" for kk, vv in v.items()]
        else:
            lines.append(f"{k}: {_q(v) if isinstance(v, str) else v}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage: case_file.py <claims.json> <verdicts.json> <app>")
    load = lambda p: json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stdout.write(to_yaml(build_case(sys.argv[3], load(sys.argv[1]), load(sys.argv[2]))))
