"""Append-only hash-chained ledger (ledger.jsonl), per CONTRACTS.md.

event = {seq, ts, type, payload, prev_hash, hash}; hash = sha256(prev_hash + payload_json).
payload_json and commit hashes use the same canonical JSON as eval/commit.py
(sorted keys, compact separators) so every lane computes identical hashes.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib

GENESIS = "0" * 64


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))  # == eval/commit.py (ensure_ascii default)


def commit_hash(obj: dict) -> str:
    return hashlib.sha256(canon({k: v for k, v in obj.items() if k != "commit"}).encode()).hexdigest()


class Ledger:
    def __init__(self, path: pathlib.Path, clock=None):
        self.path = pathlib.Path(path)
        self.clock = clock or (lambda: dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
        self.seq, self.prev = 0, GENESIS
        if self.path.exists():
            for ev in read(self.path):
                self.seq, self.prev = ev["seq"], ev["hash"]

    def append(self, type_: str, payload: dict) -> dict:
        h = hashlib.sha256((self.prev + canon(payload)).encode()).hexdigest()
        ev = {"seq": self.seq + 1, "ts": self.clock(), "type": type_, "payload": payload,
              "prev_hash": self.prev, "hash": h}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(canon(ev) + "\n")
        self.seq, self.prev = ev["seq"], h
        return ev


def read(path) -> list[dict]:
    text = pathlib.Path(path).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def verify(path) -> tuple[bool, str]:
    """Recompute the chain. Returns (ok, message naming the first bad seq)."""
    prev, seq = GENESIS, 0
    for ev in read(path):
        if ev["seq"] != seq + 1:
            return False, f"seq {ev['seq']}: expected {seq + 1}"
        if ev["prev_hash"] != prev:
            return False, f"seq {ev['seq']}: prev_hash does not match previous hash"
        want = hashlib.sha256((prev + canon(ev["payload"])).encode()).hexdigest()
        if ev["hash"] != want:
            return False, f"seq {ev['seq']}: hash mismatch (payload edited?)"
        prev, seq = ev["hash"], ev["seq"]
    return True, f"{seq} events, chain intact"
