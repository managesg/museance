"""Tiny OpenAI-compatible chat client (stdlib). Every response is cached in runs/cache/ so a run can be replayed offline.

Providers come from .env: <P>_API_KEY, <P>_BASE_URL, <P>_MODEL for P in ASI1, SUBQ, META.
"""
import hashlib, json, os, pathlib, re, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / "runs" / "cache"
DEFAULTS = {"ASI1": ("https://api.asi1.ai/v1", "asi1")}  # Vi's probe: asi1-mini gave broken cards
EXTRA = {"ASI1": {"reasoning_effort": "medium"}}


def _load_env():
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip() and not k.startswith("#") and v.strip():
                os.environ.setdefault(k.strip(), v.strip())


def configured(p):
    _load_env()
    return bool(os.environ.get(f"{p}_API_KEY")) and bool(os.environ.get(f"{p}_BASE_URL") or p in DEFAULTS)


def chat(p, system, user):
    _load_env()
    base, model = DEFAULTS.get(p, (None, None))
    base, model = os.environ.get(f"{p}_BASE_URL", base), os.environ.get(f"{p}_MODEL", model)
    body = {"model": model, "temperature": 0, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], **EXTRA.get(p, {})}
    key = hashlib.sha256(json.dumps([p, body], sort_keys=True).encode()).hexdigest()[:24]
    hit = CACHE / f"{key}.txt"
    if hit.exists():
        return hit.read_text(encoding="utf-8")
    if not configured(p):
        raise RuntimeError(f"{p} not configured (set {p}_API_KEY{'' if p in DEFAULTS else f', {p}_BASE_URL, {p}_MODEL'} in .env) and no cached reply")
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "Authorization": f"Bearer {os.environ[f'{p}_API_KEY']}"})
    with urllib.request.urlopen(req, timeout=180) as r:
        text = json.load(r)["choices"][0]["message"]["content"]
    CACHE.mkdir(parents=True, exist_ok=True)
    hit.write_text(text, encoding="utf-8")
    return text


def first_provider(*ps):
    for p in ps:
        if configured(p):
            return p
    return ps[0]  # may still replay from cache


def parse_json(text):
    """Pull the JSON array/object out of a model reply (handles ``` fences and chatter)."""
    m = re.search(r"[\[{].*[\]}]", text, re.S)
    if not m:
        raise ValueError(f"no JSON in model reply: {text[:200]}")
    return json.loads(m.group(0))
