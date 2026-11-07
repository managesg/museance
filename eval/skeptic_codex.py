"""Skeptic via Codex CLI: extra attacks from ONLY screen names and selectors. Never sees claims."""
import argparse, json, pathlib, re, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from commit import commit_hash

STEP = re.compile(r"^(click:\S+|type:[^:\s]+:.*|key:\S+|wait:\d+)$")
REQ = json.loads((pathlib.Path(__file__).resolve().parent.parent / "contracts" / "attack.schema.json").read_text())["required"]


def prompt(screens, selectors):
    return (
        "You are a QA skeptic for a web app you cannot see. Known screens: " + json.dumps(screens)
        + ". Known CSS selectors: " + json.dumps(selectors)
        + '.\nReply with ONLY a JSON array of up to 15 attacks, each {"screen": <one of the screens>, "steps": [..]}. '
        "Steps are strings: click:<css selector>, type:<css selector>:<text>, key:<key name>, wait:<ms>. "
        "Use only the selectors given. Aim for edge cases: empty input, zero, repeated operators, very long sequences, "
        "rapid repeated clicks, clearing mid-operation, decimals."
    )


def parse(text, app, observe, screens, selectors, start=1):
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    allowed = set(selectors)
    out = []
    for r in json.loads(m.group(0)):
        steps = r.get("steps")
        ok = (r.get("screen") in screens and isinstance(steps, list) and 0 < len(steps) <= 200
              and all(isinstance(s, str) and STEP.match(s) for s in steps)
              and all(s.split(":")[1] in allowed for s in steps if s.startswith(("click:", "type:"))))
        if ok:
            a = {"id": f"x{start + len(out):03d}", "app": app, "screen": r["screen"], "steps": steps, "observe": observe}
            a["commit"] = commit_hash(a)
            assert all(k in a for k in REQ)
            out.append(a)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--app", required=True)
    p.add_argument("--selectors", required=True, help="skeptic.py selectors JSON file")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    sel = json.loads(pathlib.Path(a.selectors).read_text(encoding="utf-8"))
    flat = [*sel["digits"], sel["zero"], sel["decimal"], *sel["operators"].values(), sel["equals"], sel["clear"]]
    screens = ["digit", "decimal", "equals", "clear", *sel["operators"]]
    r = subprocess.run(["codex", "exec", "-s", "read-only", "--skip-git-repo-check", "--ephemeral", "-"],
                       input=prompt(screens, flat), capture_output=True, text=True, encoding="utf-8", timeout=300, shell=sys.platform == "win32")
    attacks = parse(r.stdout, a.app, sel["observe"], screens, flat)
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(attacks, indent=1), encoding="utf-8")
    print(f"{len(attacks)} codex attacks -> {out}")


if __name__ == "__main__":
    main()
