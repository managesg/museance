"""court.regression --out report.json -> cases/<app>/regression-result.json rows {id, kind, passed, observed}.

python eval/regression_result.py report.json > cases/todo/regression-result.json
passed = the build under test (the court's `revival` side) showed exactly the regression entry's `expect`, in a non-flaky run.
"""
import json, sys

rows = json.load(open(sys.argv[1], encoding="utf-8"))["rows"]
out = [{"id": r["id"], "kind": r["group"], "passed": r["revival"] == r["expect"] and not r["flaky"],
        "observed": r["revival"]} for r in rows]
sys.stdout.reconfigure(encoding="utf-8", newline="\n")
print(json.dumps(out, indent=1, ensure_ascii=False))
