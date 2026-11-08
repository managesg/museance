"""Cold-room court (role 2): model, HTTP backend, /run server, flaky -> UNSWORN. No browser needed."""
import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from court import coldroom
from court.ledger import verify

CLOCK = lambda: "2026-11-07T00:30:00+00:00"  # noqa: E731


def serve_model(patched: bool):
    """A controller speaking the HTTP contract, backed by the in-process model (stands in for role 1)."""
    m = coldroom.ColdRoomModel(patched)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, obj):
            b = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            self._send(m.state())

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            if self.path == "/reset":
                return self._send(m.reset(**body))
            if self.path == "/tick":
                return self._send(m.tick(body.get("n", 1)))
            if self.path == "/setpoint":
                return self._send(m.write_setpoint(body["value"], body.get("pin")))
            if self.path == "/defrost":
                return self._send(m.write_defrost(body["minutes"], body.get("pin")))

    s = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_address[1]}"


def check(res):
    assert res["control_match"] == "6/6" and res["attacks_blocked"] == "2/2" and res["flaky"] == 0
    assert res["counts"]["LOCKED"] == 6 and res["counts"]["STRUCK"] == 0
    v = {x["ref"]: x for x in res["verdicts"]}
    assert v["sec-setpoint"]["original"].startswith("ok=1") and "hr1=250" in v["sec-setpoint"]["original"]
    assert v["sec-setpoint"]["revival"].startswith("ok=0") and "hr1=40" in v["sec-setpoint"]["revival"]
    assert v["sec-defrost"]["original"] == "ok=1,defrost_len=120"
    assert v["sec-defrost"]["revival"] == "ok=0,defrost_len=20"


def test_model_rules():
    m = coldroom.ColdRoomModel(False)
    m.reset(temp=12.0)
    assert not m.tick(9)["alarm"] and m.tick(1)["alarm"]  # alarm only after 10 min high
    m.reset(minute=359)
    assert sum(m.tick(1)["defrost"] for _ in range(30)) == 20
    p = coldroom.ColdRoomModel(True)
    assert p.write_setpoint(5.0, pin="4242")["ok"] and not p.write_setpoint(9.0, pin="4242")["ok"]
    assert not p.write_defrost(21, pin="4242")["ok"] and p.write_defrost(20, pin="4242")["ok"]


def test_run_case_in_process(tmp_path):
    res = coldroom.run_case(coldroom.ModelBackend(False), coldroom.ModelBackend(True), tmp_path, clock=CLOCK)
    check(res)
    assert verify(tmp_path / "ledger.jsonl")[0]
    for f in ("verdicts.json", "locks.json", "ledger.jsonl"):
        assert (tmp_path / f).is_file()


def test_run_case_over_http_contract(tmp_path):
    so, uo = serve_model(False)
    sp, up = serve_model(True)
    try:
        o, p, source = coldroom.backends(uo, up)
        assert source == "live"
        check(coldroom.run_case(o, p, tmp_path, clock=CLOCK))
    finally:
        for s in (so, sp):
            s.shutdown()
            s.server_close()


def test_court_server_run_and_fallback(tmp_path):
    srv = coldroom.make_server(0, original="http://127.0.0.1:9", patched="http://127.0.0.1:9",
                               out_dir=str(tmp_path / "runs"))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        req = urllib.request.Request(base + "/run", data=b"{}", method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            assert r.headers["Access-Control-Allow-Origin"] == "*"
            res = json.loads(r.read())
        assert res["source"] == "in-process model"  # controllers down: never claims "live"
        check(res)
        assert len(res["ledger_head"]) == 64
    finally:
        srv.shutdown()
        srv.server_close()


def test_flaky_build_is_unsworn_never_struck(tmp_path):
    class Flaky(coldroom.ModelBackend):
        n = 0

        def tick(self, n=1):
            Flaky.n += 1
            s = super().tick(n)
            if Flaky.n % 2:  # every other call lies about the compressor
                s = {**s, "compressor": not s["compressor"]}
            return s

    res = coldroom.run_case(Flaky(False), coldroom.ModelBackend(True), tmp_path, clock=CLOCK)
    locks = {r["claim_id"]: r["status"] for r in res["locks"]}
    flaky = [v["ref"] for v in res["verdicts"] if v["flaky"]]
    assert flaky and all(locks[r] == "UNSWORN" for r in flaky if r in locks)
    assert "STRUCK" not in {locks[r] for r in flaky if r in locks}
