"""Skeptic v0: deterministic edge-case attacks, no model, never reads claim text.

Selectors JSON: {"digits":[..],"zero":sel,"decimal":sel,"operators":{screen:sel},"equals":sel,"clear":sel,"observe":sel}
Screens are the operator names plus digit, decimal, equals, clear.
"""
import argparse, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from commit import commit_hash


def _patterns(s):
    """Yield (screen, steps) from deterministic edge-case patterns."""
    c = lambda sel, n=1: [f"click:{sel}"] * n
    d, d2, z, dot, eq, clr = s["digits"][0], s["digits"][-1], s["zero"], s["decimal"], s["equals"], s["clear"]
    ops = s["operators"]
    yield "equals", c(eq)                                    # empty input
    yield "equals", c(eq, 10)                                # repeated equals on nothing
    yield "clear", c(clr, 2) + c(z, 2)                       # clear on fresh state, leading zeros
    yield "digit", c(d, 20)                                  # long digit string
    yield "digit", c(z) + c(d)                               # leading zero
    yield "decimal", c(dot) + c(d)                           # leading decimal point
    yield "decimal", c(dot)                                  # decimal point alone
    yield "decimal", c(d) + c(dot, 2) + c(d2)                # two decimal points
    yield "decimal", c(d) + c(dot) + c(eq)                   # trailing decimal point
    for name, op in ops.items():
        yield name, c(op) + c(eq)                            # operator with no operand
        yield name, c(op) + c(d) + c(eq)                     # operator first
        yield name, c(d) + c(op) + c(eq)                     # missing right operand
        yield name, c(z) + c(op) + c(z) + c(eq)              # zero op zero
        yield name, c(d) + c(op) + c(z) + c(eq)              # right operand zero
        yield name, c(z) + c(op) + c(d) + c(eq)              # left operand zero
        yield name, c(d) + c(op, 2) + c(d2) + c(eq)          # double operator
        yield name, c(d) + c(op, 3) + c(d2) + c(eq)          # triple operator
        yield name, c(dot) + c(d) + c(op) + c(dot) + c(d2) + c(eq)  # leading decimals both sides
        yield name, c(d) + c(op) + c(d2) + c(eq, 2)          # repeated equals
        yield name, c(d) + c(op) + c(d2) + c(eq, 10)         # many equals
        yield name, c(d) + c(op, 10)                         # rapid operator clicks
        yield name, c(d, 20) + c(op) + c(d2, 20) + c(eq)     # long operands
        yield name, c(d) + c(op) + c(d2) + c(clr) + c(d2) + c(eq)  # clear mid-operation
        yield name, c(d) + c(op) + c(clr) + c(d2) + c(eq)    # clear right after operator
        yield name, c(d) + c(op) + c(d2) + c(eq) + c(d)      # digit after result
        yield name, c(d) + c(op) + c(d2) + c(eq) + c(op) + c(d) + c(eq)  # continue from result
        yield name, (c(d) + c(op)) * 10 + c(d2) + c(eq)      # long chain
    names = list(ops)
    for a in names:
        for b in names:
            if a != b:
                yield a, c(d) + c(ops[a]) + c(d2) + c(ops[b]) + c(d) + c(eq)  # mixed chain
                yield a, c(d) + c(ops[a]) + c(ops[b]) + c(d2) + c(eq)         # mixed double operator


def generate(app, selectors, screens=None):
    seen, out = set(), []
    for screen, steps in _patterns(selectors):
        if (screens and screen not in screens) or tuple(steps) in seen:
            continue
        seen.add(tuple(steps))
        a = {"id": f"a{len(out) + 1:03d}", "app": app, "screen": screen, "steps": steps, "observe": selectors["observe"]}
        a["commit"] = commit_hash(a)
        out.append(a)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--app", required=True)
    p.add_argument("--selectors", required=True, help="JSON file path or inline JSON")
    p.add_argument("--screens", help="comma-separated filter; default all")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    raw = a.selectors.strip()
    sel = json.loads(raw if raw.startswith("{") else pathlib.Path(raw).read_text(encoding="utf-8"))
    attacks = generate(a.app, sel, a.screens.split(",") if a.screens else None)
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(attacks, indent=1), encoding="utf-8")
    print(f"{len(attacks)} attacks -> {out}")


if __name__ == "__main__":
    main()
