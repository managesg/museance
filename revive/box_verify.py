"""Score a revival html with P1's Playwright court on the box, in a throwaway worktree of origin/main.

verify(html_path, attacks_path, claims_path) -> {regression, regression_of, false_strikes, traps_caught,
  mismatches, attacks, fidelity, locks, verdicts}   (verdicts = court verdicts.json rows, for the evidence)
Needs: ssh seabridge-pilot (BatchMode), ~/hack/venv-p4 (playwright). Never touches ~/hack/repo's checked-out branch.
"""
import json
from pathlib import Path
import subprocess
import tempfile
import uuid

HOST = "seabridge-pilot"
SSH = ["ssh", "-n", "-o", "BatchMode=yes", HOST]
SCP = ["scp", "-q", "-o", "BatchMode=yes"]
REMOTE = r"""set -e
W=/tmp/{tag}
cd ~/hack/repo && git fetch -q origin && git worktree add -q --detach $W origin/main
cd $W && mkdir -p rev && cp /tmp/{tag}.html rev/index.html
PY=~/hack/venv-p4/bin/python
$PY -m court.regression eval/regression/todo.json --original-dir apps/todo/original --revival-dir rev --out /tmp/{tag}.reg.json || true
$PY -m court.court --app todo --claims /tmp/{tag}.claims.json --attacks /tmp/{tag}.attacks.json \
  --original-dir apps/todo/original --revival-dir rev --out /tmp/{tag}.out
"""
CLEAN = "cd ~/hack/repo && git worktree remove --force /tmp/{tag}; rm -rf /tmp/{tag} /tmp/{tag}.*"


def verify(html_path, attacks_path, claims_path):
    tag = "p4v-" + uuid.uuid4().hex[:8]
    run = lambda cmd, **kw: subprocess.run(cmd, check=True, text=True, capture_output=True, timeout=1800, **kw)
    try:
        for src, name in ((html_path, "html"), (attacks_path, "attacks.json"), (claims_path, "claims.json")):
            run(SCP + [str(src), f"{HOST}:/tmp/{tag}.{name}"])
        subprocess.run(["ssh", "-o", "BatchMode=yes", HOST, "bash -s"], input=REMOTE.format(tag=tag).encode(),  # bytes: keep LF
                       check=True, capture_output=True, timeout=1800)
        with tempfile.TemporaryDirectory() as d:
            run(SCP + [f"{HOST}:/tmp/{tag}.reg.json", f"{HOST}:/tmp/{tag}.out/verdicts.json",
                       f"{HOST}:/tmp/{tag}.out/locks.json", d])
            reg = json.loads((Path(d) / f"{tag}.reg.json").read_text(encoding="utf-8"))
            verdicts = json.loads((Path(d) / "verdicts.json").read_text(encoding="utf-8"))
            locks = json.loads((Path(d) / "locks.json").read_text(encoding="utf-8"))
    finally:
        subprocess.run(SSH + [CLEAN.format(tag=tag)], capture_output=True, text=True)
    rows = reg["rows"]
    att = [v for v in verdicts if v["kind"] == "attack"]
    bad = sum(1 for v in att if not v["match"] and not v["flaky"])
    ok = sum(1 for v in att if v["match"])
    c = reg["counts"]
    return {"regression": sum(1 for r in rows if r["revival"] == r["expect"] and not r["flaky"]),
            "regression_of": len(rows), "false_strikes": c["false_strikes"], "traps_caught": c["traps_caught"],
            "mismatches": bad, "attacks": len(att), "fidelity": round(100 * ok / (ok + bad)) if ok + bad else None,
            "reg_rows": rows, "locks": {s: sum(1 for l in locks if l["status"] == s) for s in {l["status"] for l in locks}},
            "verdicts": verdicts}
