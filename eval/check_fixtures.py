"""Check that fixtures have the required fields in contracts/*.schema.json (stdlib only)."""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAIRS = {"claims.json": "claim", "attacks.json": "attack", "verdicts.json": "verdict"}


def main() -> int:
    bad = 0
    for fname, schema in PAIRS.items():
        req = json.loads((ROOT / "contracts" / f"{schema}.schema.json").read_text())["required"]
        rows = json.loads((ROOT / "fixtures" / fname).read_text(encoding="utf-8"))
        for row in rows:
            missing = [k for k in req if k not in row]
            if missing:
                bad += 1
                print(f"{fname} {row.get('id', row.get('ref'))}: missing {missing}")
        print(f"{fname}: {len(rows)} rows checked")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
