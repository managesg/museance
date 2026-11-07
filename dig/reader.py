"""Reader: whole evidence pile -> behavior sheet (sheet.json), one model pass. SubQ first, then Meta (Muse), then ASI-1.

usage: py -3 dig/reader.py app1   (reads runs/app1/evidence.json, writes runs/app1/sheet.json)
"""
import argparse, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agents"))
import llm

SYSTEM = """You read every piece of evidence about a dead web app and write its behavior sheet.
Return ONLY a JSON array. One object per observable behavior:
{"screen": short area name like "add" or "clear", "text": "one concrete, testable behavior with exact inputs and the exact visible output",
 "label": "SEEN" if the evidence directly shows or states it, "GUESSED" if you infer it,
 "citations": [evidence ids that support it], "conflicts": [evidence ids that contradict it]}
Prefer specific, checkable behaviors (exact numbers and text). Never invent citations."""


def read(evidence, chat=llm.chat, provider=None):
    provider = provider or llm.first_provider("SUBQ", "META", "ASI1")
    pile = [{k: e[k] for k in ("id", "tier", "kind", "source", "text", "path") if k in e} for e in evidence]
    lines = llm.parse_json(chat(provider, SYSTEM, json.dumps(pile, ensure_ascii=False)))
    ids, out = {e["id"] for e in evidence}, []
    for ln in lines:
        if not isinstance(ln, dict) or not ln.get("text"):
            continue
        cites = [c for c in ln.get("citations", []) if c in ids]  # drop invented citations
        out.append({"id": f"b{len(out) + 1:03d}", "screen": str(ln.get("screen") or "main"), "text": ln["text"],
                    "label": "SEEN" if cites and ln.get("label") == "SEEN" else "GUESSED",
                    "citations": cites, "conflicts": [c for c in ln.get("conflicts", []) if c in ids]})
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("app")
    p.add_argument("--provider", choices=["SUBQ", "META", "ASI1"])
    a = p.parse_args()
    run = ROOT / "runs" / a.app
    ev = json.loads((run / "evidence.json").read_text(encoding="utf-8"))
    sheet = {"app": a.app, "lines": read(ev, provider=a.provider)}
    (run / "sheet.json").write_text(json.dumps(sheet, indent=1, ensure_ascii=False), encoding="utf-8")
    seen = sum(l["label"] == "SEEN" for l in sheet["lines"])
    print(f"{len(sheet['lines'])} behaviors ({seen} SEEN) -> {run / 'sheet.json'}")


if __name__ == "__main__":
    main()
