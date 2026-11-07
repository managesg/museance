"""Run CONTRACTS.md string steps in a Playwright page and read `observe`.

Steps: click:<css> | type:<css>:<text> | key:<key name> | wait:<ms>
`type` splits on the FIRST ':' after the selector prefix, so selectors must not contain ':'
(no pseudo-classes); the text may contain ':'.
"""
from __future__ import annotations

ACTION_TIMEOUT_MS = 2000
LOAD_TIMEOUT_MS = 10000


def _origin(url: str) -> str:
    from urllib.parse import urlsplit
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}"


class StepError(ValueError):
    """A step string that doesn't match the contract grammar."""


def parse(step: str) -> tuple[str, list[str]]:
    kind, sep, rest = step.partition(":")
    if not sep or not rest:
        raise StepError(f"bad step {step!r}")
    if kind == "click":
        return kind, [rest]
    if kind == "type":
        sel, sep2, text = rest.partition(":")
        if not sep2 or not sel:
            raise StepError(f"bad type step {step!r}, want type:<css>:<text>")
        return kind, [sel, text]
    if kind == "key":
        return kind, [rest]
    if kind == "wait":
        if not rest.isdigit():
            raise StepError(f"bad wait step {step!r}, want wait:<ms>")
        return kind, [rest]
    raise StepError(f"unknown step kind {kind!r} in {step!r}")


def run_steps(page, url: str, steps: list[str], observe: str) -> str:
    """Load `url` fresh, run `steps`, return innerText of `observe`.

    Never raises for app behaviour: a missing element or a timeout becomes a
    deterministic `ERROR:` string so original and revival can be compared like any
    other output. Malformed steps raise StepError (that is a contract bug, not a ruling).
    """
    parsed = [parse(s) for s in steps]
    origin = _origin(url)

    def _same_origin_only(route):
        # Offline + deterministic: the app under trial may only load its own files.
        # (e.g. todo's Google Fonts link otherwise hangs the page load.)
        if _origin(route.request.url) == origin or route.request.url.startswith(("data:", "blob:")):
            route.continue_()
        else:
            route.abort()

    page.route("**/*", _same_origin_only)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=LOAD_TIMEOUT_MS)
    except Exception as e:  # noqa: BLE001 - an unreachable build is an observation, not a crash
        return f"ERROR:load {type(e).__name__}"
    for i, (kind, args) in enumerate(parsed):
        try:
            if kind == "click":
                page.click(args[0], timeout=ACTION_TIMEOUT_MS)
            elif kind == "type":
                page.fill(args[0], args[1], timeout=ACTION_TIMEOUT_MS)
            elif kind == "key":
                page.keyboard.press(args[0])
            elif kind == "wait":
                page.wait_for_timeout(int(args[0]))
        except Exception as e:  # noqa: BLE001 - any Playwright failure is an observation
            return f"ERROR:step {i} {steps[i]}: {type(e).__name__}"
    try:
        return page.inner_text(observe, timeout=ACTION_TIMEOUT_MS).strip()
    except Exception as e:  # noqa: BLE001
        return f"ERROR:observe {observe}: {type(e).__name__}"
