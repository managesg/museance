"""Seal the regression set and Skeptic attacks before the Medium's claims are revealed.

python eval/seal.py --app app1 --regression eval/regression/app1-fixture.json --attacks runs/app1/attacks.json --out cases/app1.commits.json [--verify]
Hashes cover parsed JSON (sorted keys, compact), so line endings cannot change them.
"""
import argparse, datetime, hashlib, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from commit import commit_hash  # noqa: E402

load = lambda p: json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
digest = lambda obj: hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def seal(app, regression, attacks):
    return {"app": app,
            "created_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "regression_sha256": digest(regression),
            "attacks": [{"id": a["id"], "commit": commit_hash(a)} for a in attacks],
            "attacks_sha256": digest(attacks)}


def verify(sealed, regression, attacks):
    """Return a list of mismatch messages; empty means the seal holds."""
    want = {k: sealed.get(k) for k in ("app", "regression_sha256", "attacks", "attacks_sha256")}
    have = seal(sealed.get("app"), regression, attacks)
    bad = [f"{k} differs" for k in ("regression_sha256", "attacks_sha256") if want[k] != have[k]]
    old = {a["id"]: a["commit"] for a in want["attacks"] or []}
    new = {a["id"]: a["commit"] for a in have["attacks"]}
    bad += [f"attack {i} commit differs" for i in sorted(old.keys() & new.keys()) if old[i] != new[i]]
    bad += [f"attack {i} missing from seal" for i in sorted(new.keys() - old.keys())]
    bad += [f"attack {i} missing from attacks file" for i in sorted(old.keys() - new.keys())]
    bad += [f"attack {a['id']} stored commit is stale" for a in attacks if a.get("commit") != commit_hash(a)]
    return bad


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--app", required=True)
    p.add_argument("--regression", required=True)
    p.add_argument("--attacks", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--verify", action="store_true")
    a = p.parse_args()
    reg, atk = load(a.regression), load(a.attacks)
    out = pathlib.Path(a.out)
    if a.verify:
        bad = verify(load(out), reg, atk)
        print("\n".join(f"MISMATCH: {m}" for m in bad) or f"seal OK: {out}")
        sys.exit(1 if bad else 0)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(seal(a.app, reg, atk), f, indent=1)
        f.write("\n")
    print(f"sealed {len(atk)} attacks -> {out}")


if __name__ == "__main__":
    main()
