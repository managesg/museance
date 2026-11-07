"""Shared commit hash: sha256 of the object's JSON without `commit`, sorted keys."""
import hashlib, json


def commit_hash(obj: dict) -> str:
    body = {k: v for k, v in obj.items() if k != "commit"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
