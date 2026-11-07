"""Skeptic v0: deterministic edge-case attacks, no model, never reads claim text.

Selectors JSON: {"digits":[..],"zero":sel,"decimal":sel,"operators":{screen:sel},"equals":sel,"clear":sel,"observe":sel}
Screens are the operator names plus digit, decimal, equals, clear.
Todo-list selectors ({"input","add","lists":{todo,completed},"item_buttons":{...},"observe":[...]}) use _todo_patterns instead.
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


def _todo_patterns(s):
    """Yield (screen, steps, observe) for a todo-list app: add, complete, remove edge cases."""
    inp, add, b = s["input"], s["add"], s["item_buttons"]
    todo, done = s["lists"]["todo"], s["lists"]["completed"]
    typ = lambda t: [f"type:{inp}:{t}", f"click:{add}"]
    ent = lambda t, k="Enter": [f"type:{inp}:{t}", f"key:{k}"]
    cc, rt, uc, rc = (f"click:{b[k]}" for k in ("complete_open", "remove_open", "complete_done", "remove_done"))
    for obs in (todo, done, "body"):
        yield "add", [f"click:{add}"], obs                             # empty input
        yield "add", [f"key:Enter"], obs                               # Enter on nothing
        yield "add", typ("   "), obs                                   # whitespace only
        yield "add", typ("a    b"), obs                                # inner whitespace collapse
        yield "add", typ("0"), obs                                     # falsy-looking string
        yield "add", typ("x" * 500), obs                               # very long, no spaces
        yield "add", typ("<b>bold</b><script>1</script>"), obs         # HTML must stay literal
        yield "add", typ("&amp; &lt; &#65;"), obs                      # entities stay literal
        yield "add", typ("a:b:c: 10:30"), obs                          # colons
        yield "add", typ("ñ ☕ 日本 😀"), obs  # unicode
        yield "add", typ("A") + typ("A"), obs                          # duplicates
        yield "add", ent("A") + ent("B", "NumpadEnter"), obs           # Enter variants
        yield "add", ent("A", "Shift+Enter"), obs                      # modified Enter
        yield "add", [f"type:{inp}:A", "key:Enter", "key:Enter"], obs  # Enter twice
        yield "add", typ("A") + [f"click:{add}"], obs                  # add twice, input cleared
        yield "add", [f"type:{inp}:" + "y" * 40, f"click:{add}"] * 6, obs   # many long items
        yield "add", [f"type:{inp}:{i}" if k == 0 else f"click:{add}" for i in range(12) for k in (0, 1)], obs
        yield "complete", typ("A") + [cc], obs
        yield "complete", typ("A") + [cc, uc], obs                     # toggle back
        yield "complete", typ("A") + [cc, uc, cc, uc, cc], obs         # toggle repeatedly
        yield "complete", typ("A") + typ("B") + typ("C") + [cc, cc], obs   # ordering in completed
        yield "complete", typ("A") + typ("B") + typ("C") + [cc, cc, uc], obs
        yield "complete", typ("A") + typ("A") + [cc], obs              # duplicate task, complete one
        yield "complete", typ("A") + typ("A") + [cc, uc], obs
        yield "complete", typ("a    b") + [cc], obs                    # collapsed whitespace item moved
        yield "remove", typ("A") + [rt], obs                           # delete the last item
        yield "remove", typ("A") + [rt] + typ("B"), obs                # add after emptying
        yield "remove", typ("A") + typ("B") + [rt], obs
        yield "remove", typ("A") + typ("B") + [cc, rc], obs            # complete then delete
        yield "remove", typ("A") + [cc, rc] + typ("B"), obs
        yield "remove", typ("A") + typ("A") + [rt], obs                # duplicate remove
        yield "remove", typ("A") + typ("A") + [cc, rc], obs
        yield "remove", typ("A") + typ("B") + typ("C") + [cc, rt, rc], obs  # remove from both lists
        yield "remove", typ("   ") + [rt], obs                         # remove a blank item
        yield "remove", typ("A") + [rt, rt], obs                       # remove on empty list


def generate(app, selectors, screens=None):
    seen, out = set(), []
    todo = "input" in selectors
    for row in (_todo_patterns(selectors) if todo else _patterns(selectors)):
        screen, steps = row[:2]
        observe = row[2] if todo else selectors["observe"]
        if (screens and screen not in screens) or (tuple(steps), observe) in seen:
            continue
        seen.add((tuple(steps), observe))
        a = {"id": f"a{len(out) + 1:03d}", "app": app, "screen": screen, "steps": steps, "observe": observe}
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
