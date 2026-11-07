"""A case in plain Python, no uAgents: what the Bailiff runs over the mesh, and all of --no-mesh.

Wraps the lanes, never reimplements them: runs/<app>/sheet.json + evidence.json (dig/) -> agents/medium.py
cards; eval/skeptic.py attacks sealed with eval/seal.py; court/court.py judge; eval/score.py numbers.
Every hop is a 'mesh.<event>' ledger event with a caption (captions.py), written through
on_event(type, payload, caption); ledger_sink() is the Bailiff's writer.

    from agents.mesh import case
    result = case.run_case("todo")                       # --no-mesh: Hoot and McClusky in process
    result = await case.hear("todo", parties, on_event)  # the Bailiff: parties reach the agents over the mesh

SEANCE_FAKE_LLM=1: McClusky's cards come from fixtures/claims.json and remarks are the canned lines.
SEANCE_FAKE_BENCH=1: FakeBench instead of Playwright.
"""
from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import pathlib
import sys
import threading
import time
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from agents import medium  # noqa: E402
from agents.mesh import base, captions, commands  # noqa: E402
from court import serve  # noqa: E402
from court.court import Bench, default_workers, judge, rule  # noqa: E402
from court.feed import APP_RE  # noqa: E402
from court.ledger import Ledger, commit_hash, read as read_ledger, verify as verify_ledger  # noqa: E402
from eval import score, skeptic  # noqa: E402
from eval import seal as p4seal  # noqa: E402

RUNS = ROOT / "runs"
REG = ROOT / "eval" / "regression"
START = 1000  # credibility start, as eval/case_file.py


class MissingInput(LookupError):
    """The app cannot be raised; the message names every missing file and the command that makes it."""


class CaseError(RuntimeError):
    """A party failed or timed out; the case adjourns with this message."""


def _rel(p) -> str:
    p = pathlib.Path(p)
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


def _load(p):
    return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))


def _registry() -> dict:
    p = ROOT / "fixtures" / "apps.json"
    return {r["id"]: r for r in _load(p)} if p.is_file() else {}


def _build(app: str, kind: str, run: pathlib.Path):
    """A folder we serve ourselves beats a registry URL someone has to keep running."""
    dirs = [run / kind] + ([ROOT / "fixtures" / app] if kind == "original" else [])
    for d in dirs:
        if (d / "index.html").is_file():
            return {"dir": str(d)}
    url = _registry().get(app, {}).get(kind, {}).get("url")
    return {"url": url} if url else None


def load_inputs(app: str, runs=RUNS) -> dict:
    """Everything a case needs, from the files on main. Raises MissingInput naming each missing file.
    -> {app, sheet, evidence, selectors, regression, sealed, original, revival}; a build is {dir} or {url}."""
    if not APP_RE.match(app or ""):
        raise MissingInput(f"{app!r} is not an app id")
    run = pathlib.Path(runs) / app
    reg = next((p for p in (REG / f"{app}.json", REG / f"{app}-fixture.json") if p.is_file()), REG / f"{app}.json")
    files = {  # key: (path, how to make it)
        "evidence": (run / "evidence.json", f"python dig/pile.py {app}"),
        "sheet": (run / "sheet.json", f"python dig/reader.py {app}"),
        "selectors": (REG / f"{app}-selectors.json", "P4 writes it"),
        "regression": (reg, "P4 writes it"),
        "sealed": (ROOT / "cases" / f"{app}.commits.json", f"python eval/seal.py --app {app} ..."),
    }
    out, missing = {"app": app}, []
    for key, (path, make) in files.items():
        if path.is_file():
            out[key] = _load(path)
        else:
            missing.append(f"no {key} at {_rel(path)} ({make})")
    for kind in ("original", "revival"):
        out[kind] = _build(app, kind, run)
        if not out[kind]:
            where = f"{_rel(run / kind)}/index.html" + (f" or fixtures/{app}/" if kind == "original" else "")
            missing.append(f"no {kind} build at {where} or in fixtures/apps.json")
    if missing:
        raise MissingInput(f"{app}: " + "; ".join(missing))
    return out


def apps(runs=RUNS) -> dict:
    """Every app the court has heard of -> '' when it can be raised, else what is missing."""
    names = {p.name[: -len("-selectors.json")] for p in REG.glob("*-selectors.json")}
    names |= {p.parent.name for p in pathlib.Path(runs).glob("*/evidence.json")}
    out = {}
    for name in sorted(names):
        try:
            load_inputs(name, runs)
            out[name] = ""
        except MissingInput as ex:
            out[name] = str(ex).split(": ", 1)[-1]
    return out


# --- the parties' work ---------------------------------------------------------------------------------
def make_attacks(app: str, inputs: dict | None = None) -> list[dict]:
    """Dr. Hoot's attacks: P4's deterministic skeptic, never shown a claim."""
    return skeptic.generate(app, (inputs or load_inputs(app))["selectors"])


def seal_attacks(app: str, attacks: list[dict], inputs: dict | None = None) -> dict:
    """What Hoot sends before anyone testifies (SealedAttacks.seal): commits and hashes, no steps."""
    return p4seal.seal(app, (inputs or load_inputs(app))["regression"], attacks)


def _canned_chat(app: str):
    """SEANCE_FAKE_LLM=1: the Medium's model reply, canned from fixtures/claims.json (lines = claim ids)."""
    cards = [{"line": c["id"], "screen": c["screen"], "text": c["text"], "test": c["test"], "confidence": c["confidence"]}
             for c in _load(ROOT / "fixtures" / "claims.json") if c["app"] == app]
    if not cards:
        raise MissingInput(f"SEANCE_FAKE_LLM=1 has no canned claims for {app} in fixtures/claims.json")
    return lambda *_: json.dumps(cards)


def make_claims(app: str, inputs: dict | None = None, chat=None) -> tuple[list[dict], list]:
    """McClusky's testimony: P2's Medium (ASI-1, replies cached in runs/cache) -> (claims, dropped). Blocking."""
    inp = inputs or load_inputs(app)
    chat = chat or (_canned_chat(app) if base.flag("SEANCE_FAKE_LLM") else medium.llm.chat)
    return medium.cards(app, inp["sheet"], inp["evidence"], inp["selectors"], chat=chat)


def objection(r: dict, answer: str = "") -> str:
    """McClusky's closing remark: ASI-1 in character, else the canned line."""
    return base.persona("mcclusky", captions.objection_prompt(r, answer), captions.objection(r))


def verify_reveal(sealed: dict, attacks: list[dict]) -> tuple[list[dict], list[dict]]:
    """Hoot's reveal against Hoot's seal: an attack is accepted only if its content still hashes to the commit he
    sealed before the testimony. -> (accepted, refused); refused rows are {id, why}."""
    want = {a["id"]: a["commit"] for a in sealed.get("attacks", [])}
    ok, bad, seen = [], [], set()
    for a in attacks:
        h, i = commit_hash(a), a.get("id")
        why = ("never sealed" if i not in want else "revealed twice" if i in seen
               else "content changed after the seal" if h != want[i]
               else "stated commit does not match its content" if a.get("commit") not in (None, h) else "")
        seen.add(i)
        (bad.append({"id": i, "why": why}) if why else ok.append(a))
    bad += [{"id": i, "why": "sealed but never revealed"} for i in want if i not in seen]
    return ok, bad


def _consistent(claims: list[dict]) -> tuple[list[dict], list[dict]]:
    """Claims whose stated commit matches their content (judge() would refuse the case over one that does not)."""
    ok, bad = [], []
    for c in claims:
        (ok if c.get("commit") in (None, commit_hash(c)) else bad).append(c)
    return ok, [{"id": c.get("id"), "why": "commit does not match its content"} for c in bad]


# --- the court -----------------------------------------------------------------------------------------
class FakeBench:
    """SEANCE_FAKE_BENCH=1: no browser. The original answers from the app's regression set (P4 observed those
    on the running original), the revival agrees on good entries and drifts on traps, and anything else
    reads "" on both builds."""

    def __init__(self, original_url: str, regression: dict):
        self.original = original_url
        self.answers = {(tuple(e["steps"]), e["observe"]): (e["expect"], trap)
                        for trap, group in ((False, "good"), (True, "traps")) for e in regression.get(group, [])}

    def run(self, url: str, steps: list[str], observe: str) -> str:
        expect, trap = self.answers.get((tuple(steps), observe), ("", False))
        return f"{expect} (drift)" if trap and url != self.original else expect


@contextlib.contextmanager
def _url(build: dict):
    with serve.maybe(build.get("dir")) as served:
        yield served or build["url"]


def ruling(app: str, claims: list, attacks: list, verdicts: list, locks: list, case_id: str = "", refused: int = 0) -> dict:
    """The numbers the court hands down (Ruling model fields), from P1's locks and P4's scoring."""
    status = {x["claim_id"]: x["status"] for x in locks}
    orig = {v["ref"]: v["original"] for v in verdicts if v["kind"] == "claim"}
    struck = [{"id": c["id"], "text": c["text"], "expect": c["test"]["expect"], "original": orig[c["id"]],
               "bond": c["bond"], "confidence": c["confidence"]} for c in claims if status.get(c["id"]) == "STRUCK"]
    worst = max(struck, key=lambda s: (s["confidence"], s["bond"]), default=None)
    return {"case_id": case_id, "app": app,
            "counts": {k: sum(s == k for s in status.values()) for k in captions.STATUSES},
            "claims": len(claims), "attacks": len(attacks), "refused": refused,
            "catches": sum(1 for v in verdicts if v["kind"] == "attack" and not v["match"] and not v["flaky"]),
            "fidelity": score.fidelity(verdicts), "brier": round(score.brier(claims, verdicts), 3),
            "credibility_start": START, "credibility_end": score.credibility(claims, verdicts, START),
            "struck": struck, "funniest": captions.funniest(worst) if worst else ""}


def run_court(app: str, claims: list, attacks: list, on_event=None, inputs: dict | None = None, runs=RUNS,
              clock=None, case_id: str = "", refused: int = 0, workers: int | None = None) -> dict:
    """P1's judge() on original + revival, scored by P4. Blocking: from async code use asyncio.to_thread.
    Writes runs/<app>/claims.json and attacks.json (judge adds verdicts.json, locks.json and the commit,
    verdict and lock ledger events). Emits 'court' before and 'ruling' after. Returns the ruling dict."""
    inp = inputs or load_inputs(app, runs)
    out = pathlib.Path(runs) / app
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("claims", claims), ("attacks", attacks)):
        (out / f"{name}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    _note(on_event, "court", {"case_id": case_id, "app": app, "claims": len(claims), "attacks": len(attacks)})
    with _url(inp["original"]) as orig, _url(inp["revival"]) as rev:
        bench = FakeBench(orig, inp["regression"]) if base.flag("SEANCE_FAKE_BENCH") else None
        verdicts, locks = judge(claims, attacks, orig, rev, out, clock=clock, bench=bench,
                                workers=workers or default_workers())
    r = {**ruling(app, claims, attacks, verdicts, locks, case_id, refused),
         "chain": verify_ledger(out / "ledger.jsonl")[1]}
    _note(on_event, "ruling", r)
    return r


def cross(app: str, text: str, inputs: dict | None = None, runs=RUNS) -> dict:
    """The Bailiff's cross: map the expression with commands.to_steps (known selectors only, max 30 steps;
    raises commands.CrossError), then one court.court.rule verdict. Ad hoc, like court/feed.py's bench: not
    written to runs/ or the ledger. Blocking. -> {steps, observe, ...verdict}."""
    inp = inputs or load_inputs(app, runs)
    steps, observe = commands.to_steps(inp["selectors"], text)
    item = {"id": "cross", "app": app, "steps": steps, "observe": observe}
    with _url(inp["original"]) as orig, _url(inp["revival"]) as rev:
        if base.flag("SEANCE_FAKE_BENCH"):
            v = rule(FakeBench(orig, inp["regression"]), item, "attack", orig, rev)
        else:
            with Bench() as bench:
                v = rule(bench, item, "attack", orig, rev)
    return {"steps": steps, "observe": observe, **v}


# --- ledger ------------------------------------------------------------------------------------------------
_WRITE = threading.Lock()


def ledger_sink(app: str, runs=RUNS, clock=None):
    """on_event that appends 'mesh.<type>' {...payload, caption} to runs/<app>/ledger.jsonl. Reopens the ledger
    on every event: court.ledger.Ledger caches seq and hash, and judge() appends in between."""
    path = pathlib.Path(runs) / app / "ledger.jsonl"

    def on_event(type_: str, payload: dict, caption: str) -> dict:
        with _WRITE:
            return Ledger(path, clock=clock).append(f"mesh.{type_}", {**payload, "caption": caption})
    return on_event


def archive_ledger(app: str, runs=RUNS) -> pathlib.Path | None:
    """A new case starts a new chain. The old ledger.jsonl is renamed, never deleted, and court/feed.py sends
    the stage a 'reset' when the file is recreated."""
    p = pathlib.Path(runs) / app / "ledger.jsonl"
    if not (p.is_file() and p.stat().st_size):
        return None
    stamp, n = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), 0
    dest = p.with_name(f"ledger-{stamp}.jsonl")
    while dest.exists():
        n += 1
        dest = p.with_name(f"ledger-{stamp}-{n}.jsonl")
    return p.rename(dest)


def last_case(app: str, runs=RUNS) -> dict:
    """The case on file, for the chat commands: {app, ruling (the last mesh.ruling payload or None), claims,
    attacks, verdicts, locks, events, chain}. Empty lists when a file is missing."""
    d = pathlib.Path(runs) / app
    get = lambda name: _load(d / name) if (d / name).is_file() else []  # noqa: E731
    events = read_ledger(d / "ledger.jsonl") if (d / "ledger.jsonl").is_file() else []
    rul = next((e["payload"] for e in reversed(events) if e["type"] == "mesh.ruling"), None)
    return {"app": app, "ruling": rul, "claims": get("claims.json"), "attacks": get("attacks.json"),
            "verdicts": get("verdicts.json"), "locks": get("locks.json"), "events": events,
            "chain": verify_ledger(d / "ledger.jsonl")[1] if events else "no ledger yet"}


def _note(on_event, type_: str, payload: dict):
    return on_event(type_, payload, captions.caption(type_, payload)) if on_event else None


# --- the case ------------------------------------------------------------------------------------------------
def new_case_id(app: str) -> str:
    return f"{app}-{uuid.uuid4().hex[:6]}"


class LocalParties:
    """Dr. Hoot and McClusky in process (--no-mesh). The Bailiff's mesh version has the same four coroutines
    and sends CallSkeptic, CallMedium, RequestReveal and RemarkRequest instead; it raises CaseError when a
    party answers with an error or not at all."""

    def __init__(self, inputs: dict):
        self.inputs, self._attacks = inputs, []

    async def seal(self, case_id: str, app: str) -> dict:
        self._attacks = make_attacks(app, self.inputs)
        return seal_attacks(app, self._attacks, self.inputs)

    async def testify(self, case_id: str, app: str) -> tuple[list[dict], int]:
        claims, dropped = await asyncio.to_thread(make_claims, app, self.inputs)
        return claims, len(dropped)

    async def reveal(self, case_id: str, app: str) -> list[dict]:
        return self._attacks

    async def remark(self, speaker: str, case_id: str, app: str, r: dict, answer: str = "") -> str:
        return captions.taunt(r) if speaker == "hoot" else await asyncio.to_thread(objection, r, answer)


async def hear(app: str, parties=None, on_event=None, case_id: str | None = None, requester: str = "",
               front_door: str = "", runs=RUNS, clock=None, inputs: dict | None = None) -> dict:
    """One full case, in the order of models.py. Raises MissingInput before anything is written when the app
    cannot be raised; after that a failure adjourns the case (event 'adjourned') instead of raising.
    on_event may be sync or async; default ledger_sink(). Returns the ruling dict + remarks, or
    {case_id, app, error}."""
    inp = inputs or load_inputs(app, runs)
    parties = parties or LocalParties(inp)
    case_id = case_id or new_case_id(app)
    on_event = on_event or ledger_sink(app, runs, clock)
    ids = {"case_id": case_id, "app": app}

    async def emit(type_: str, payload: dict):
        r = _note(on_event, type_, {**ids, **payload})
        if inspect.isawaitable(r):
            await r

    archive_ledger(app, runs)
    try:
        await emit("open", {"requester": requester, "front_door": front_door,
                            "evidence": len(inp["evidence"]), "lines": len(inp["sheet"].get("lines", []))})
        await emit("summon", {"who": "hoot", "for": "seal"})
        sealed = await parties.seal(case_id, app)
        p4 = inp["sealed"]
        await emit("sealed", {"attacks": len(sealed.get("attacks", [])), "attacks_sha256": sealed.get("attacks_sha256", ""),
                              "p4_match": sealed.get("attacks_sha256") == p4.get("attacks_sha256")
                              and sealed.get("regression_sha256") == p4.get("regression_sha256"),
                              "p4_sealed_utc": p4.get("created_utc", "")})
        await emit("summon", {"who": "mcclusky", "for": "testimony"})
        claims, dropped = await parties.testify(case_id, app)
        claims, bad_claims = _consistent(claims)
        await emit("testimony", {"claims": len(claims), "dropped": dropped, "refused": bad_claims,
                                 "fabricated": sum(c.get("label") == "FABRICATED" for c in claims),
                                 "bond": sum(c.get("bond", 0) for c in claims)})
        await emit("summon", {"who": "hoot", "for": "reveal", "attacks": len(sealed.get("attacks", []))})
        attacks, refused = verify_reveal(sealed, await parties.reveal(case_id, app))
        await emit("reveal", {"accepted": len(attacks), "refused": refused,
                              "p4_problems": p4seal.verify(p4, inp["regression"], attacks)[:10]})
        await emit("court", {"claims": len(claims), "attacks": len(attacks)})
        r = await asyncio.to_thread(run_court, app, claims, attacks, inputs=inp, runs=runs, clock=clock,
                                    case_id=case_id, refused=len(refused))
        await emit("ruling", r)
    except Exception as ex:  # noqa: BLE001 - the case adjourns on the record instead of crashing the Bailiff
        reason = str(ex) if isinstance(ex, CaseError) else f"{type(ex).__name__}: {ex}"
        await emit("adjourned", {"reason": captions.short(reason, 200)})
        return {**ids, "error": reason}
    remarks = {}
    for speaker in ("hoot", "mcclusky"):  # Hoot taunts first, McClusky answers him
        try:
            text = await parties.remark(speaker, case_id, app, r, remarks.get("hoot", ""))
        except Exception:  # noqa: BLE001 - after the ruling a silent party gets its canned line
            text = captions.taunt(r) if speaker == "hoot" else captions.objection(r)
        remarks[speaker] = text
        await emit("remark", {"speaker": speaker, "text": text})
    await emit("closed", {k: r[k] for k in ("counts", "catches", "attacks", "credibility_start", "credibility_end")})
    return {**r, "remarks": remarks}


def run_case(app: str, on_event=None, runs=RUNS, clock=None, case_id: str | None = None) -> dict:
    """--no-mesh: the whole case in this process (not from inside a running event loop)."""
    return asyncio.run(hear(app, on_event=on_event, case_id=case_id, runs=runs, clock=clock))
