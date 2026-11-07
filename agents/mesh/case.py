"""A case in plain Python, no uAgents: what the Bailiff runs over the mesh, and all of --no-mesh.

Wraps the lanes, never reimplements them:
  inputs   runs/<app>/ when present, else P2's dig/out/<app>/ (evidence, sheet, claims), else P2 makes them:
           dig/pile.py, dig/reader.py and agents/medium.py on ASI-1 (P2's cache in runs/cache makes reruns instant)
  attacks  P4's eval/skeptic.py, only the ids P4 sealed in cases/<app>.commits.json (checked with eval/seal.py
           verify), at most MAX_ATTACKS of them spread over the list
  court    P1's court/court.py judge on original + revival (court/serve.py folders), court/shots.py for the
           first mismatches, then P4's eval/case_file.py build_case and eval/score.py numbers
Every hop is one mesh.<type> ledger event (R2 payload + agent + caption) through on_event(type, payload);
ledger_sink() is the Bailiff's writer, so judge() and the mesh events share one chain. runs/<app>/ruling.json
keeps the full ruling (status, transcript and the final chat reply read it).

    from agents.mesh import case
    r = case.run_case("todo")                                   # --no-mesh: Hoot and McClusky in process
    r = await case.hear("todo", parties, on_event, progress=...)  # the Bailiff: parties reach the agents over the mesh

No model code is imported at module level: the Bailiff imports this module. SEANCE_FAKE_LLM=1: claims come from
fixtures/claims.json, voices are the canned lines. SEANCE_FAKE_BENCH=1: FakeBench instead of Playwright.
"""
from __future__ import annotations

import asyncio
import contextlib
import http.server
import inspect
import json
import os
import pathlib
import sys
import threading
import time
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from agents.mesh import base, captions, commands  # noqa: E402
from court import serve  # noqa: E402
from court.court import RUNS_PER_BUILD, Bench, judge, rule  # noqa: E402
from court.feed import APP_RE  # noqa: E402
from court.ledger import Ledger, commit_hash, read as read_ledger, verify as verify_ledger  # noqa: E402
from court.shots import take_shots  # noqa: E402
from eval import case_file, score, skeptic  # noqa: E402
from eval import seal as p4seal  # noqa: E402

# shortcut: court/serve.py serves with the stdlib listen backlog of 5, so 8 browsers loading at once get refused
# connections that the court then rules flaky (measured on todo: 4 flaky of 36 tests -> 0 with 128). Drop this once
# P1 sets request_queue_size in court/serve.py.
http.server.ThreadingHTTPServer.request_queue_size = 128
RUNS = ROOT / "runs"
DIG = ROOT / "dig" / "out"
PILES = ROOT / "dig" / "piles"
REG = ROOT / "eval" / "regression"
CASES = ROOT / "cases"
START = 1000  # credibility start, as eval/case_file.py
# shortcut: P4 sealed 75 (app1) and 105 (todo) attacks, 55-90 s in court on this laptop; 20 keeps a raise under
# 90 s. Raise it when the court gets faster.
MAX_ATTACKS = 20
MAX_SHOTS = 3  # mismatches photographed per case: the chat attaches the first
WORKERS = min(8, os.cpu_count() or 1)
RULING_KEYS = ("locked", "struck", "fabricated", "unsworn", "fidelity", "credibility")
PROGRESS = {  # R6: at most 4 short status lines while a case runs; each replaces the last in ASI:One
    "open": "⏳ Dr. Hoot is sealing his attacks...",
    "sealed": "⏳ McClusky, Esq. is swearing his claims...",
    "revealed": "⏳ The court is running every test twice on each build...",
    "ruling": "⏳ Ruling in. The parties are having words...",
}


class MissingInput(LookupError):
    """The app cannot be raised; the message names every missing file and the command that makes it."""


class CaseError(RuntimeError):
    """A party failed or timed out; the case adjourns with this message."""


def _rel(p) -> str:
    p = pathlib.Path(p)
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


def _load(p):
    return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))


def _write(p, rows) -> None:
    pathlib.Path(p).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(p).write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def _registry() -> dict:
    p = ROOT / "fixtures" / "apps.json"
    return {r["id"]: r for r in _load(p)} if p.is_file() else {}


def _on_file(app: str, name: str, runs) -> pathlib.Path | None:
    """runs/<app>/<name> (the last case) first, then P2's dig/out/<app>/<name>."""
    return next((d / name for d in (pathlib.Path(runs) / app, DIG / app) if (d / name).is_file()), None)


def _build(app: str, kind: str, runs):
    """A folder we serve ourselves beats a registry URL someone has to keep running. runs/<app>/<kind>/ first
    (tests put a drifted revival there), then the repo: apps/<app>/original or fixtures/<app>, revive/out/<app>."""
    dirs = [pathlib.Path(runs) / app / kind]
    dirs += [ROOT / "apps" / app / "original", ROOT / "fixtures" / app] if kind == "original" else [
        ROOT / "revive" / "out" / app]
    for d in dirs:
        if (d / "index.html").is_file():
            return {"dir": str(d)}
    url = _registry().get(app, {}).get(kind, {}).get("url")
    return {"url": url} if url else None


def load_inputs(app: str, runs=RUNS) -> dict:
    """Everything a case needs, from the files on the tree. Raises MissingInput naming what is missing.
    -> {app, selectors, regression, sealed (P4's seal or None), evidence/sheet/claims (or None: P2 makes them
    at testimony), original, revival}; a build is {dir} or {url}."""
    if not APP_RE.match(app or ""):
        raise MissingInput(f"{app!r} is not an app id")
    sel = REG / f"{app}-selectors.json"
    reg = next((p for p in (REG / f"{app}.json", REG / f"{app}-fixture.json") if p.is_file()), None)
    seal_p = CASES / f"{app}.commits.json"
    out = {"app": app, "selectors": _load(sel) if sel.is_file() else None, "regression": _load(reg) if reg else {},
           "sealed": _load(seal_p) if seal_p.is_file() else None}
    for name in ("evidence", "sheet", "claims"):
        p = _on_file(app, f"{name}.json", runs)
        out[name] = _load(p) if p else None
    missing = []
    if out["selectors"] is None:
        missing.append(f"no selectors at {_rel(sel)} (P4 writes it)")
    if out["evidence"] is None and not (PILES / app / "pile.json").is_file():
        missing.append(f"no evidence in runs/{app}/ or dig/out/{app}/ and no dig/piles/{app}/pile.json")
    for kind in ("original", "revival"):
        out[kind] = _build(app, kind, runs)
        if not out[kind]:
            missing.append(f"no {kind} build on disk or in fixtures/apps.json")
    if missing:
        raise MissingInput(f"{app}: " + "; ".join(missing))
    return out


def apps(runs=RUNS) -> dict:
    """Every app the court has heard of -> '' when it can be raised, else what is missing."""
    names = {p.name[: -len("-selectors.json")] for p in REG.glob("*-selectors.json")} | set(_registry())
    names |= {p.parent.name for p in [*pathlib.Path(runs).glob("*/evidence.json"), *DIG.glob("*/evidence.json")]}
    out = {}
    for name in sorted(names):
        try:
            load_inputs(name, runs)
            out[name] = ""
        except MissingInput as ex:
            out[name] = str(ex).split(": ", 1)[-1]
    return out


# --- the parties' work ---------------------------------------------------------------------------------
def spread(rows: list, n: int) -> list:
    """n rows evenly spaced over the list, in order (all of them when there are at most n)."""
    return rows if len(rows) <= n else [rows[i * len(rows) // n] for i in range(n)]


def sealed_pool(app: str, inp: dict) -> list[dict]:
    """P4's deterministic skeptic output, restricted to the ids P4 sealed (all of it without a seal on file)."""
    attacks = skeptic.generate(app, inp["selectors"])
    if inp["sealed"]:
        ids = {a["id"] for a in inp["sealed"]["attacks"]}
        attacks = [a for a in attacks if a["id"] in ids]
    return attacks


def make_attacks(app: str, inp: dict) -> list[dict]:
    """Dr. Hoot's attacks, never shown a claim: at most MAX_ATTACKS of the sealed pool."""
    return spread(sealed_pool(app, inp), MAX_ATTACKS)


def seal_attacks(app: str, attacks: list[dict], inp: dict) -> dict:
    """What Hoot sends before anyone testifies: eval.seal.seal (commits and hashes, no steps)."""
    return p4seal.seal(app, inp["regression"], attacks)


def p4_check(app: str, inp: dict, attacks: list[dict]) -> tuple[int, list[str]]:
    """P4's git seal: eval.seal.verify on the pool Hoot picked from, and every attack the court will run must be
    the very attack P4 sealed under its id. -> (attacks P4 sealed, problems); (0, []) without a seal on file."""
    p4 = inp["sealed"]
    if not p4:
        return 0, []
    problems = p4seal.verify(p4, inp["regression"], sealed_pool(app, inp))
    want = {a["id"]: a["commit"] for a in p4["attacks"]}
    problems += [f"attack {a['id']} is not the attack P4 sealed" for a in attacks if want.get(a["id"]) != commit_hash(a)]
    return len(p4["attacks"]), problems


def _canned_chat(app: str):
    """SEANCE_FAKE_LLM=1: the Medium's model reply, canned from fixtures/claims.json (lines = claim ids)."""
    cards = [{"line": c["id"], "screen": c["screen"], "text": c["text"], "test": c["test"], "confidence": c["confidence"]}
             for c in _load(ROOT / "fixtures" / "claims.json") if c["app"] == app]
    if not cards:
        raise MissingInput(f"SEANCE_FAKE_LLM=1 has no canned claims for {app} in fixtures/claims.json")
    return lambda *_: json.dumps(cards)


def make_claims(app: str, inp: dict, runs=RUNS) -> tuple[list[dict], list]:
    """McClusky's testimony: P2's sworn claims on file, else P2's pipeline makes them (dig/pile.py ->
    dig/reader.py -> agents/medium.py, ASI-1). Blocking. Fills inp's evidence and sheet when it made them."""
    if inp.get("claims"):
        return inp["claims"], []
    from agents import medium  # noqa: PLC0415 - model code stays out of the Bailiff's process
    from dig import pile, reader  # noqa: PLC0415
    run = pathlib.Path(runs) / app
    if inp.get("evidence") is None:
        inp["evidence"] = pile.build(app, PILES / app)
        _write(run / "evidence.json", inp["evidence"])
    if inp.get("sheet") is None:
        inp["sheet"] = {"app": app, "lines": reader.read(inp["evidence"], provider="ASI1")}
        _write(run / "sheet.json", inp["sheet"])
    chat = _canned_chat(app) if base.flag("SEANCE_FAKE_LLM") else medium.llm.chat
    return medium.cards(app, inp["sheet"], inp["evidence"], inp["selectors"], chat=chat)


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


def _consistent(claims: list[dict]) -> list[dict]:
    """Claims whose stated commit matches their content (judge() would refuse the case over one that does not)."""
    return [c for c in claims if c.get("commit") in (None, commit_hash(c))]


# --- the court -----------------------------------------------------------------------------------------
class FakeBench:
    """SEANCE_FAKE_BENCH=1: no browser. The original answers from the app's regression set, the revival agrees
    on good entries and drifts on traps, and anything else reads "" on both builds."""

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


def run_court(app: str, claims: list, attacks: list, inputs: dict, runs=RUNS, clock=None) -> dict:
    """P1's judge() on original + revival (writes verdicts.json, locks.json and the commit, verdict and lock
    ledger events), then court.shots for the first mismatches. Blocking: from async code use asyncio.to_thread."""
    out = pathlib.Path(runs) / app
    _write(out / "claims.json", claims)
    _write(out / "attacks.json", attacks)
    t = time.monotonic()
    fake = base.flag("SEANCE_FAKE_BENCH")
    with _url(inputs["original"]) as orig, _url(inputs["revival"]) as rev:
        bench = FakeBench(orig, inputs["regression"]) if fake else None
        verdicts, locks = judge(claims, attacks, orig, rev, out, clock=clock, bench=bench, workers=WORKERS)
        court_s = time.monotonic() - t
        bad = [v for v in verdicts if not v["match"] and not v["flaky"]][:MAX_SHOTS]
        shots = take_shots(bad, claims, attacks, orig, rev, out) if bad and not fake else []
    return {"verdicts": verdicts, "locks": locks, "shots": shots, "court_s": court_s}


def cross(app: str, text: str, inputs: dict | None = None, runs=RUNS) -> dict:
    """The Bailiff's cross: commands.to_steps (known selectors only, at most 30 steps; raises
    commands.CrossError), then one court.court.rule verdict on both builds. Blocking. -> {steps, observe, ...}."""
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
    """on_event(type, payload) that appends 'mesh.<type>' to runs/<app>/ledger.jsonl. Reopens the ledger on every
    event: court.ledger.Ledger caches seq and hash, and judge() appends in between."""
    path = pathlib.Path(runs) / app / "ledger.jsonl"

    def on_event(type_: str, payload: dict) -> dict:
        with _WRITE:
            return Ledger(path, clock=clock).append(f"mesh.{type_}", payload)
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


def ledger_check(app: str, runs=RUNS) -> dict:
    path = pathlib.Path(runs) / app / "ledger.jsonl"
    if not path.is_file():
        return {"entries": 0, "ok": False, "check": "no ledger yet"}
    ok, msg = verify_ledger(path)
    return {"entries": len(read_ledger(path)), "ok": ok, "check": msg}


def last_case(app: str, runs=RUNS) -> dict:
    """The case on file, for the chat commands: {app, ruling (ruling.json or None), claims, attacks, verdicts,
    locks, events, ledger}. Empty lists when a file is missing."""
    d = pathlib.Path(runs) / app
    get = lambda name, empty: _load(d / name) if (d / name).is_file() else empty  # noqa: E731
    events = read_ledger(d / "ledger.jsonl") if (d / "ledger.jsonl").is_file() else []
    return {"app": app, "ruling": get("ruling.json", None), "claims": get("claims.json", []),
            "attacks": get("attacks.json", []), "verdicts": get("verdicts.json", []), "locks": get("locks.json", []),
            "events": events, "ledger": ledger_check(app, runs)}


# --- the case ------------------------------------------------------------------------------------------------
def new_case_id(app: str) -> str:
    return f"{app}-{uuid.uuid4().hex[:6]}"


class LocalParties:
    """Dr. Hoot and McClusky in process (--no-mesh). The Bailiff's MeshParties has the same four coroutines and
    sends CallSkeptic, CallMedium, RequestReveal and RemarkRequest instead; it raises CaseError when a party
    answers with an error or not at all."""

    def __init__(self, inputs: dict, runs=RUNS):
        self.inputs, self.runs, self._attacks = inputs, runs, []

    async def seal(self, case_id: str, app: str) -> dict:
        self._attacks = make_attacks(app, self.inputs)
        return seal_attacks(app, self._attacks, self.inputs)

    async def testify(self, case_id: str, app: str) -> tuple[list[dict], int]:
        claims, dropped = await asyncio.to_thread(make_claims, app, self.inputs, self.runs)
        return claims, len(dropped)

    async def reveal(self, case_id: str, app: str) -> list[dict]:
        return self._attacks

    async def remark(self, speaker: str, case_id: str, app: str, r: dict, answer: str = "") -> str:
        if speaker == "hoot":
            return captions.taunt(r)
        from agents.mesh import voice  # noqa: PLC0415 - McClusky's ASI-1 voice, never the Bailiff's
        return await asyncio.to_thread(voice.mcclusky_line, r, answer)


def numbers(r: dict) -> dict:
    """The final reply's machine line."""
    if r.get("error"):
        return {"app": r["app"], "case_id": r["case_id"], "ok": False, "error": captions.short(r["error"], 120),
                "ledger": r["ledger"]["entries"], "chain": r["ledger"]["ok"]}
    c = r["counts"]
    return {"app": r["app"], "case_id": r["case_id"], "ok": True, "locked": c["LOCKED"], "struck": c["STRUCK"],
            "fabricated": c["FABRICATED"], "unsworn": c["UNSWORN"], "fidelity": r["fidelity"],
            "credibility": r["credibility_end"], "claims": r["claims"], "attacks": r["attacks"],
            "differ": r["differ"], "seconds": r["seconds"]["total"], "ledger": r["ledger"]["entries"],
            "chain": r["ledger"]["ok"], "shots": len(r.get("shots", []))}


async def hear(app: str, parties=None, on_event=None, case_id: str | None = None, requested_by: str = "",
               runs=RUNS, clock=None, inputs: dict | None = None, progress=None) -> dict:
    """One full case: open, sealed, sworn, revealed, the court (judge, shots, case file), ruling, two remarks.
    Raises MissingInput before anything is written when the app cannot be raised; after that a failure appends a
    mesh.ruling with an error caption instead of raising. on_event(type, payload) and progress(line) may be sync
    or async; on_event defaults to ledger_sink(). Writes runs/<app>/ruling.json and returns that dict."""
    inp = inputs or load_inputs(app, runs)
    parties = parties or LocalParties(inp, runs)
    case_id = case_id or new_case_id(app)
    on_event = on_event or ledger_sink(app, runs, clock)
    out = pathlib.Path(runs) / app
    t0, record = time.monotonic(), []
    r = {"case_id": case_id, "app": app, "requested_by": requested_by or "terminal", "error": "", "record": record}

    async def call(fn, *a):
        res = fn(*a) if fn else None
        if inspect.isawaitable(res):
            await res

    async def emit(type_: str, agent: str, payload: dict, **extra):
        p = {**payload, "agent": agent, "caption": captions.caption(type_, payload, **extra)}
        record.append(p["caption"])
        await call(on_event, type_, p)
        if type_ in PROGRESS and not extra.get("error"):
            await call(progress, PROGRESS[type_])

    out.mkdir(parents=True, exist_ok=True)
    archive_ledger(app, runs)
    ruled = False
    try:
        await emit("open", "bailiff", {"app": app, "case_id": case_id, "requested_by": r["requested_by"]})
        sealed = await parties.seal(case_id, app)
        await emit("sealed", "hoot", {"count": len(sealed.get("attacks", [])), "seal": sealed.get("attacks_sha256", "")})
        claims, dropped = await parties.testify(case_id, app)
        claims = _consistent(claims)
        if not claims:
            raise CaseError("McClusky swore no claims the court can test")
        await emit("sworn", "mcclusky", {"count": len(claims), "total_bond": sum(c["bond"] for c in claims)})
        revealed = await parties.reveal(case_id, app)
        attacks, refused = verify_reveal(sealed, revealed)
        await emit("revealed", "hoot", {"count": len(revealed), "matched": len(attacks)})
        p4_count, p4_problems = p4_check(app, inp, attacks)
        court = await asyncio.to_thread(run_court, app, claims, attacks, inp, runs, clock)
        verdicts, locks = court["verdicts"], court["locks"]
        counts = {k: sum(x["status"] == k for x in locks) for k in captions.STATUSES}
        live = [v for v in verdicts if not v["flaky"]]
        r.update(counts=counts, claims=len(claims), attacks=len(attacks), runs_per_build=RUNS_PER_BUILD,
                 differ=sum(not v["match"] for v in live), judged=len(live), flaky=len(verdicts) - len(live),
                 fidelity=score.fidelity(verdicts), brier=round(score.brier(claims, verdicts), 3),
                 credibility_start=START, credibility_end=score.credibility(claims, verdicts, START),
                 seal={"count": len(revealed), "matched": len(attacks), "sha256": sealed.get("attacks_sha256", ""),
                       "refused": refused, "p4_count": p4_count, "p4_problems": p4_problems[:10]},
                 sworn={"count": len(claims), "total_bond": sum(c["bond"] for c in claims), "dropped": dropped},
                 struck=[{"id": c["id"], "text": c["text"], "expect": c["test"]["expect"], "bond": c["bond"],
                          "confidence": c["confidence"], "original": next(v["original"] for v in verdicts
                                                                          if v["ref"] == c["id"])}
                         for c in claims if any(x["claim_id"] == c["id"] and x["status"] == "STRUCK" for x in locks)],
                 shots=[{"ref": s["ref"], **{k: _rel(out / "shots" / s["files"][k]) for k in ("original", "revival")}}
                        for s in court["shots"]],
                 case_file=case_file.build_case(app, claims, verdicts),
                 tests=captions.test_lines(verdicts, claims, attacks, locks, inp["selectors"]))
        if inp.get("sheet") is None and (out / "sheet.json").is_file():  # McClusky made it in his own process
            inp["sheet"] = _load(out / "sheet.json")
        r["thinking"] = captions.thinking_lines(r, inp.get("sheet") or {}, claims, locks)
        r["seconds"] = {"court": round(court["court_s"]), "total": round(time.monotonic() - t0)}
        await emit("ruling", "bailiff", {"locked": counts["LOCKED"], "struck": counts["STRUCK"],
                                         "fabricated": counts["FABRICATED"], "unsworn": counts["UNSWORN"],
                                         "fidelity": r["fidelity"], "credibility": r["credibility_end"]},
                   differ=r["differ"], judged=r["judged"])
        ruled = True
        remarks = {}
        for speaker in ("hoot", "mcclusky"):  # Hoot taunts first, McClusky answers him
            try:
                text = await parties.remark(speaker, case_id, app, r, remarks.get("hoot", ""))
            except Exception:  # noqa: BLE001 - after the ruling a silent party gets its canned line
                text = captions.taunt(r) if speaker == "hoot" else captions.objection(r)
            text = " ".join(str(text).split())
            remarks[speaker] = text if len(text.split()) <= 18 else (
                captions.taunt(r) if speaker == "hoot" else captions.objection(r))
            await emit("remark", speaker, {"from": speaker, "text": remarks[speaker]})
        r.update(remarks=remarks, voice=remarks["mcclusky"])
        r["seconds"]["total"] = round(time.monotonic() - t0)
    except Exception as ex:  # noqa: BLE001 - the case adjourns on the record instead of crashing the Bailiff
        r["error"] = str(ex) if isinstance(ex, (CaseError, MissingInput)) else f"{type(ex).__name__}: {ex}"
        r["error"] = base.redact(captions.short(r["error"], 300))
        if not ruled:
            await emit("ruling", "bailiff", dict.fromkeys(RULING_KEYS), error=r["error"])
    r["ledger"] = ledger_check(app, runs)
    _write(out / "ruling.json", r)
    return r


def run_case(app: str, on_event=None, runs=RUNS, clock=None, case_id: str | None = None, progress=None,
             requested_by: str = "") -> dict:
    """--no-mesh: the whole case in this process (not from inside a running event loop)."""
    return asyncio.run(hear(app, on_event=on_event, case_id=case_id, runs=runs, clock=clock, progress=progress,
                            requested_by=requested_by))
