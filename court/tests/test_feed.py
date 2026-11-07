import json
import threading
import urllib.error
import urllib.request

import pytest

from court.feed import make_server
from court.ledger import Ledger


@pytest.fixture
def srv(tmp_path):
    runs = tmp_path / "runs"
    (runs / "app1").mkdir(parents=True)
    s = make_server(runs, 0, apps=tmp_path / "none.json")  # isolated from the shared fixtures/apps.json
    s.RequestHandlerClass.poll_s = 0.05
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_address[1]}", runs
    s.shutdown()
    s.server_close()


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            assert r.headers["Access-Control-Allow-Origin"] == "*"
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_apps_files_ledger_verify(srv):
    base, runs = srv
    assert get(base + "/apps") == (200, ["app1"])
    assert get(base + "/app1/verdicts")[0] == 404
    (runs / "app1" / "verdicts.json").write_text('[{"id":"c1"}]')
    assert get(base + "/app1/verdicts") == (200, [{"id": "c1"}])
    assert get(base + "/app1/locks")[0] == 404
    L = Ledger(runs / "app1" / "ledger.jsonl")
    for i in range(3):
        L.append("verdict", {"i": i})
    st, evs = get(base + "/app1/ledger?after=1")
    assert st == 200 and [e["seq"] for e in evs] == [2, 3]
    assert get(base + "/app1/verify") == (200, {"ok": True, "message": "3 events, chain intact"})


def test_404_and_traversal(srv):
    base, _ = srv
    assert get(base + "/nope/verdicts")[0] == 404
    assert get(base + "/..%2f/verdicts")[0] in (400, 404)
    assert get(base + "/a.b/verdicts")[0] == 400
    assert get(base + "/%2e%2e/ledger")[0] in (400, 404)


def read_event(r):
    ev = {}
    while True:
        line = r.readline().decode().rstrip("\n")
        if line == "":
            if ev:
                return ev
            continue
        if line.startswith(":") or line.startswith("retry"):
            continue
        k, _, v = line.partition(": ")
        ev[k] = v


def test_sse_tail_and_reset(srv):
    base, runs = srv
    path = runs / "app1" / "ledger.jsonl"  # does not exist yet
    r = urllib.request.urlopen(base + "/app1/events", timeout=5)
    L = Ledger(path)
    L.append("commit", {"a": 1})
    L.append("verdict", {"b": 2})
    e1, e2 = read_event(r), read_event(r)
    assert (e1["id"], e1["event"]) == ("1", "commit")
    assert json.loads(e2["data"])["payload"] == {"b": 2}
    path.unlink()
    assert read_event(r)["event"] == "reset"
    Ledger(path).append("lock", {"c": 3})
    e = read_event(r)
    assert (e["id"], e["event"]) == ("1", "lock")
    r.close()


def test_sse_after(srv):
    base, runs = srv
    L = Ledger(runs / "app1" / "ledger.jsonl")
    for i in range(3):
        L.append("verdict", {"i": i})
    r = urllib.request.urlopen(base + "/app1/events?after=2", timeout=5)
    assert read_event(r)["id"] == "3"
    r.close()


def post(url, body):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_bench_validation_and_preflight(srv):
    base, _ = srv
    assert post(base + "/app1/bench", {"steps": ["bogus"], "observe": "#d"})[0] == 400
    assert post(base + "/app1/bench", {"steps": ["click:#a"], "observe": ""})[0] == 400
    assert post(base + "/bench", {"steps": ["click:#a"], "observe": "#d"})[0] == 400  # no app
    assert post(base + "/app1/bench", {"steps": ["click:#a"], "observe": "#d"})[0] == 400  # no URLs
    req = urllib.request.Request(base + "/app1/bench", method="OPTIONS")
    with urllib.request.urlopen(req, timeout=5) as r:
        assert "POST" in r.headers["Access-Control-Allow-Methods"]
        assert r.headers["Access-Control-Allow-Headers"] == "Last-Event-ID, Content-Type"


def test_bench_a01(tmp_path):
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    attack = json.loads((root / "fixtures" / "attacks.json").read_text(encoding="utf-8"))[0]
    assert attack["id"] == "a01"
    s = make_server(tmp_path, 0, apps=tmp_path / "none.json", original_dir=root / "fixtures" / "app1",
                    revival_dir=root / "court" / "tests" / "revival_app1")
    threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{s.server_address[1]}"
        st, v = post(base + "/bench", {"app": "app1", "steps": attack["steps"], "observe": attack["observe"]})
        assert st == 200
        assert v["ref"].startswith("bench-") and v["kind"] == "attack"
        assert v["match"] is False and v["flaky"] is False and v["claim_true"] is None
        assert v["original"] != v["revival"] and v["shrunk_steps"]
        assert not list(tmp_path.iterdir())  # nothing written to runs/
    finally:
        s.shutdown()
        s.server_close()
