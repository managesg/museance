"""Live feed of court events over HTTP (stdlib only).

    python -m court.feed --runs runs --port 8787

Endpoints (all JSON, CORS `Access-Control-Allow-Origin: *`; <app> matches ^[A-Za-z0-9_-]+$):
  GET /apps                    -> ["app1", ...]  (subfolders of the runs dir)
  GET /<app>/verdicts          -> runs/<app>/verdicts.json   (404 {"error":..} if missing)
  GET /<app>/locks             -> runs/<app>/locks.json      (404 {"error":..} if missing)
  GET /<app>/ledger?after=N    -> JSON array of ledger events with seq > N (default 0)
  GET /<app>/verify            -> {"ok": bool, "message": str}  (court.ledger.verify)
  GET /<app>/events?after=N    -> Server-Sent Events. Each ledger event is sent as
        `id: <seq>` / `event: <type>` (commit|verdict|lock) / `data: <event json>`.
        Starts after `Last-Event-ID` header or ?after= (default 0), then tails ledger.jsonl
        (poll ~200 ms). `: hb` heartbeat comment every 15 s. The ledger may not exist yet.
        If it is truncated or recreated (new run) the server sends `event: reset`
        (data {}) and restarts from seq 0.

  POST /<app>/bench  (or POST /bench with "app" in the body)
        body {app, steps, observe, original?, revival?} -> ONE verdict (CONTRACTS.md shape,
        kind "attack", ref "bench-<n>") from court.court.rule: 2 runs per build, flaky check,
        shrink. Ad hoc: NOT written to runs/ or the ledger. 400 on bad steps/observe,
        504 after 60 s. Build URLs: body, else --build APP=ORIG,REV for that app, else --original-dir/--revival-dir, else the apps
        registry (--apps, default fixtures/apps.json: original.url / revival.url).
        All bench jobs run on one worker thread that owns the Playwright browser.
  OPTIONS answers CORS preflight (Allow-Methods GET, POST, OPTIONS).

JS example:
  const es = new EventSource("http://localhost:8787/app1/events");
  for (const t of ["commit", "verdict", "lock"])
    es.addEventListener(t, (e) => {
      const ev = JSON.parse(e.data);          // {seq, ts, type, payload, prev_hash, hash}
      console.log(t, ev.seq, ev.payload);     // animate the claim card / meter / glitch here
    });
  es.addEventListener("reset", () => clearStage());  // new run started: wipe local state
  es.onerror = () => {};                     // EventSource reconnects and sends Last-Event-ID
"""
from __future__ import annotations

import argparse
import contextlib
import itertools
import json
import pathlib
import queue
import re
import threading
import time
from concurrent.futures import Future, TimeoutError as FutureTimeout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from court import ledger as ledger_mod
from court import serve
from court import steps as steps_mod

APP_RE = re.compile(r"^[A-Za-z0-9_-]+$")
POLL_S = 0.2
HEARTBEAT_S = 15.0


def _parse_lines(buf: bytes):
    """Split buf into complete lines; returns (events, bytes consumed). Partial tail is left."""
    events, used = [], 0
    while True:
        i = buf.find(b"\n", used)
        if i < 0:
            break
        line = buf[used:i].strip()
        used = i + 1
        if line:
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
    return events, used


class BenchWorker:
    """One thread owns the court Bench (Playwright sync API is not thread-safe)."""

    def __init__(self):
        self.q: queue.Queue = queue.Queue()
        self.n = itertools.count(1)
        self._t = None
        self._lock = threading.Lock()

    def submit(self, item, orig, rev) -> Future:
        with self._lock:
            if self._t is None:
                self._t = threading.Thread(target=self._loop, daemon=True)
                self._t.start()
        fut = Future()
        self.q.put((fut, item, orig, rev))
        return fut

    def _loop(self):
        from court.court import Bench, rule
        bench = None
        while True:
            fut, item, orig, rev = self.q.get()
            if not fut.set_running_or_notify_cancel():
                continue
            try:
                if bench is None:
                    bench = Bench().__enter__()
                fut.set_result(rule(bench, item, "attack", orig, rev))
            except Exception as e:
                fut.set_exception(e)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    runs: pathlib.Path = pathlib.Path("runs")
    poll_s = POLL_S
    heartbeat_s = HEARTBEAT_S
    bench_timeout = 60.0
    worker: BenchWorker = None
    registry: dict = {}
    app_dir_urls: dict = {}
    dir_urls: tuple = (None, None)

    def log_message(self, *a):
        pass

    def _send(self, code: int, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _err(self, code, msg):
        self._send(code, {"error": msg})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Last-Event-ID, Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        parts = [p for p in u.path.split("/") if p]
        q = parse_qs(u.query)
        try:
            if parts == ["apps"]:
                apps = sorted(p.name for p in self.runs.iterdir() if p.is_dir() and APP_RE.match(p.name)) \
                    if self.runs.is_dir() else []
                return self._send(200, apps)
            if len(parts) != 2:
                return self._err(404, "not found")
            app, what = parts
            if not APP_RE.match(app):
                return self._err(400, "bad app id")
            d = self.runs / app
            if not d.is_dir():
                return self._err(404, f"unknown app {app}")
            if what in ("verdicts", "locks"):
                f = d / f"{what}.json"
                if not f.is_file():
                    return self._err(404, f"{what}.json not found")
                return self._send(200, f.read_bytes())
            if what == "ledger":
                after = self._int(q.get("after", ["0"])[0])
                f = d / "ledger.jsonl"
                evs = ledger_mod.read(f) if f.is_file() else []
                return self._send(200, [e for e in evs if e["seq"] > after])
            if what == "verify":
                f = d / "ledger.jsonl"
                if not f.is_file():
                    return self._err(404, "ledger.jsonl not found")
                ok, msg = ledger_mod.verify(f)
                return self._send(200, {"ok": ok, "message": msg})
            if what == "events":
                after = self._int(self.headers.get("Last-Event-ID") or q.get("after", ["0"])[0])
                return self._sse(d / "ledger.jsonl", after)
            return self._err(404, "not found")
        except (BrokenPipeError, ConnectionError):
            pass
        except Exception as e:  # keep the server alive
            try:
                self._err(500, str(e))
            except Exception:
                pass

    def do_POST(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        try:
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self._err(400, "body must be JSON")
            if not isinstance(body, dict):
                return self._err(400, "body must be a JSON object")
            if parts == ["bench"]:
                app = body.get("app")
            elif len(parts) == 2 and parts[1] == "bench":
                app = parts[0]
            else:
                return self._err(404, "not found")
            if not isinstance(app, str) or not APP_RE.match(app):
                return self._err(400, "bad or missing app id")
            steps, observe = body.get("steps"), body.get("observe")
            if not isinstance(steps, list) or not steps or not all(isinstance(x, str) for x in steps):
                return self._err(400, "steps must be a non-empty list of strings")
            try:
                for x in steps:
                    steps_mod.parse(x)
            except steps_mod.StepError as e:
                return self._err(400, str(e))
            if not isinstance(observe, str) or not observe.strip():
                return self._err(400, "observe must be a non-empty string")
            ent = self.registry.get(app, {})
            per_app = self.app_dir_urls.get(app, (None, None))
            orig = (body.get("original") or per_app[0] or self.dir_urls[0]
                    or ent.get("original", {}).get("url"))
            rev = (body.get("revival") or per_app[1] or self.dir_urls[1]
                   or ent.get("revival", {}).get("url"))
            if not orig or not rev:
                return self._err(400, f"no original/revival URL for {app}")
            item = {"id": f"bench-{next(self.worker.n)}", "steps": steps, "observe": observe}
            fut = self.worker.submit(item, orig, rev)
            try:
                return self._send(200, fut.result(timeout=self.bench_timeout))
            except FutureTimeout:
                return self._err(504, "bench timed out")
            except Exception as e:
                return self._err(500, f"bench failed: {e}")
        except (BrokenPipeError, ConnectionError):
            pass

    @staticmethod
    def _int(s) -> int:
        try:
            return max(0, int(s))
        except (TypeError, ValueError):
            return 0

    def _sse(self, path: pathlib.Path, after: int):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.close_connection = True
        w = self.wfile
        w.write(b"retry: 1000\n\n")
        w.flush()
        offset, head, last_hb = 0, b"", time.monotonic()
        while True:
            out = b""
            try:
                size = path.stat().st_size
            except OSError:
                size = -1
            if size >= 0:
                with path.open("rb") as f:
                    first = f.readline() if size else b""
                    recreated = offset > 0 and (size < offset or (first.endswith(b"\n") and first != head))
                    if recreated:
                        out += b"event: reset\ndata: {}\n\n"
                        offset, head, after = 0, b"", 0
                    if not head and first.endswith(b"\n"):
                        head = first
                    f.seek(offset)
                    evs, used = _parse_lines(f.read())
                    offset += used
                for ev in evs:
                    if ev["seq"] > after:
                        after = ev["seq"]
                        out += (f"id: {ev['seq']}\nevent: {ev['type']}\ndata: "
                                f"{json.dumps(ev, separators=(',', ':'))}\n\n").encode()
            elif offset > 0:
                out += b"event: reset\ndata: {}\n\n"
                offset, head, after = 0, b"", 0
            now = time.monotonic()
            if not out and now - last_hb >= self.heartbeat_s:
                out = b": hb\n\n"
            if out:
                last_hb = now
                w.write(out)
                w.flush()
            time.sleep(self.poll_s)


def make_server(runs, port=8787, host="127.0.0.1", apps=None, original_dir=None,
                revival_dir=None, builds=None) -> ThreadingHTTPServer:
    """builds: {app_id: (original_dir, revival_dir)}, served per app for POST /bench.
    original_dir/revival_dir (no app) are a global fallback for every app."""
    registry = {}
    ap = pathlib.Path(apps or "fixtures/apps.json")
    if ap.is_file():
        registry = {r["id"]: r for r in json.loads(ap.read_text(encoding="utf-8"))}
    stack = contextlib.ExitStack()
    urls = (stack.enter_context(serve.maybe(original_dir)), stack.enter_context(serve.maybe(revival_dir)))
    app_urls = {app: (stack.enter_context(serve.maybe(o)), stack.enter_context(serve.maybe(r)))
                for app, (o, r) in (builds or {}).items()}
    h = type("FeedHandler", (Handler,), {"runs": pathlib.Path(runs), "worker": BenchWorker(),
                                         "registry": registry, "dir_urls": urls,
                                         "app_dir_urls": app_urls})
    srv = ThreadingHTTPServer((host, port), h)
    srv.daemon_threads = True
    close = srv.server_close
    srv.server_close = lambda: (close(), stack.close())
    return srv


def main(argv=None):
    ap = argparse.ArgumentParser(prog="court.feed")
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--apps", default="fixtures/apps.json")
    ap.add_argument("--original-dir")
    ap.add_argument("--revival-dir")
    ap.add_argument("--build", action="append", default=[], metavar="APP=ORIGINAL_DIR,REVIVAL_DIR",
                    help="serve local build folders for ONE app's bench (repeatable), e.g. "
                         "--build todo=apps/todo/original,revive/out/todo")
    a = ap.parse_args(argv)
    builds = {}
    for spec in a.build:
        app, sep, dirs = spec.partition("=")
        o, sep2, r = dirs.partition(",")
        if not (sep and sep2 and APP_RE.match(app) and o and r):
            ap.error(f"bad --build {spec!r}, want APP=ORIGINAL_DIR,REVIVAL_DIR")
        builds[app] = (o, r)
    srv = make_server(a.runs, a.port, a.host, a.apps, a.original_dir, a.revival_dir, builds)
    print(f"court feed on http://{a.host}:{srv.server_address[1]} (runs={a.runs})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
