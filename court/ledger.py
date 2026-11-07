"""Append-only hash-chained ledger (ledger.jsonl), per CONTRACTS.md.

event = {seq, ts, type, payload, prev_hash, hash}; hash = sha256(prev_hash + payload_json).
payload_json and commit hashes use the same canonical JSON as eval/commit.py
(sorted keys, compact separators) so every lane computes identical hashes.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import threading
from contextlib import contextmanager

GENESIS = "0" * 64


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)  # CONTRACTS.md canon, == eval/commit.py


def commit_hash(obj: dict) -> str:
    return hashlib.sha256(canon({k: v for k, v in obj.items() if k != "commit"}).encode("utf-8")).hexdigest()


class Ledger:
    def __init__(self, path: pathlib.Path, clock=None):
        self.path = pathlib.Path(path)
        self.clock = clock or (lambda: dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
        self.seq, self.prev = self._tip()

    def _tip(self):
        if self.path.exists():
            evs = read(self.path)
            if evs:
                return evs[-1]["seq"], evs[-1]["hash"]
        return 0, GENESIS

    @contextmanager
    def _locked(self):
        """OS lock on <ledger>.lock, plus a process-local lock (OS locks don't exclude threads)."""
        lock_path = self.path.with_name(self.path.name + ".lock")
        with _THREAD_LOCK, open(lock_path, "a+b") as lf:
            if lf.seek(0, 2) == 0:
                lf.write(b"\0")
                lf.flush()
            lf.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lf.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(lf, fcntl.LOCK_EX)
            try:
                yield
            finally:
                lf.seek(0)
                if os.name == "nt":
                    msvcrt.locking(lf.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lf, fcntl.LOCK_UN)

    def append(self, type_: str, payload: dict) -> dict:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._locked():
            self.seq, self.prev = self._tip()  # re-read inside the lock: another writer may have appended
            h = hashlib.sha256((self.prev + canon(payload)).encode("utf-8")).hexdigest()
            ev = {"seq": self.seq + 1, "ts": self.clock(), "type": type_, "payload": payload,
                  "prev_hash": self.prev, "hash": h}
            _drop_partial_tail(self.path)  # a crashed writer's unterminated last line is not an event
            with self.path.open("ab") as f:
                f.write((canon(ev) + "\n").encode("utf-8"))
            self.seq, self.prev = ev["seq"], h
        return ev


_THREAD_LOCK = threading.Lock()


def _drop_partial_tail(path) -> None:
    if not path.exists() or not path.stat().st_size:
        return
    data = path.read_bytes()
    if not data.endswith(b"\n"):
        path.write_bytes(data[: data.rfind(b"\n") + 1])


def read(path, strict: bool = False) -> list[dict]:
    """Events in order. An unparseable FINAL line (crash mid-write) is ignored unless strict."""
    lines = [ln for ln in pathlib.Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]
    out = []
    for i, line in enumerate(lines):
        try:
            out.append(json.loads(line))
        except ValueError:
            if strict or i != len(lines) - 1:
                raise
    return out


def verify(path) -> tuple[bool, str]:
    """Recompute the chain. Returns (ok, message naming the first bad seq)."""
    prev, seq = GENESIS, 0
    try:
        events = read(path, strict=True)
    except ValueError as e:
        return False, f"unparseable line (truncated write?): {e}"
    for ev in events:
        if ev["seq"] != seq + 1:
            return False, f"seq {ev['seq']}: expected {seq + 1}"
        if ev["prev_hash"] != prev:
            return False, f"seq {ev['seq']}: prev_hash does not match previous hash"
        want = hashlib.sha256((prev + canon(ev["payload"])).encode("utf-8")).hexdigest()
        if ev["hash"] != want:
            return False, f"seq {ev['seq']}: hash mismatch (payload edited?)"
        prev, seq = ev["hash"], ev["seq"]
    return True, f"{seq} events, chain intact"


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "verify":
        _ok, _msg = verify(sys.argv[2])
        print(_msg)
        sys.exit(0 if _ok else 1)
    print("usage: python -m court.ledger verify <path>", file=sys.stderr)
    sys.exit(2)
