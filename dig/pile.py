"""Dig: turn a pre-collected pile (dig/piles/<app>/pile.json) into evidence.json, with measured word count.

pile.json: [{"tier":"A-D","kind":"page|screenshot|video|issue|doc","source":url,"license":..,"text":.. | "path":file}]
Text items count words; path items (screenshots) are referenced, not read.
usage: py -3 dig/pile.py app1 [--out runs/app1/evidence.json]
"""
import argparse, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
KINDS, TIERS = {"page", "screenshot", "video", "issue", "doc"}, {"A", "B", "C", "D"}


def build(app, pile_dir):
    items = json.loads((pile_dir / "pile.json").read_text(encoding="utf-8"))
    out = []
    for i, it in enumerate(items, 1):
        if it["tier"] not in TIERS or it["kind"] not in KINDS or not it.get("source") or not it.get("license"):
            raise ValueError(f"pile item {i} needs tier A-D, kind in {sorted(KINDS)}, source, license: {it}")
        ev = {"id": f"e{i:03d}", "app": app, **{k: it[k] for k in ("tier", "kind", "source", "license")}}
        if "text" in it:
            ev["text"] = it["text"]
        else:
            ev["path"] = str((pile_dir / it["path"]).relative_to(ROOT)).replace("\\", "/")
        out.append(ev)
    return out


def words(evidence):
    return sum(len(e.get("text", "").split()) for e in evidence)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("app")
    p.add_argument("--pile", help="default dig/piles/<app>")
    p.add_argument("--out", help="default runs/<app>/evidence.json")
    a = p.parse_args()
    ev = build(a.app, pathlib.Path(a.pile) if a.pile else ROOT / "dig" / "piles" / a.app)
    out = pathlib.Path(a.out or ROOT / "runs" / a.app / "evidence.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ev, indent=1, ensure_ascii=False), encoding="utf-8")
    tiers = {t: sum(e["tier"] == t for e in ev) for t in sorted(TIERS)}
    print(f"{len(ev)} evidence items, {words(ev)} words measured, tiers {tiers} -> {out}")


if __name__ == "__main__":
    main()
