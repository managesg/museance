"""Shared commit hash: sha256 of UTF-8 JSON without `commit`: sorted keys, separators (",",":"), ensure_ascii=False.
Must match court/ledger.py canon()."""
import hashlib, json


def commit_hash(obj: dict) -> str:
    body = {k: v for k, v in obj.items() if k != "commit"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
