"""Run CONTRACTS.md string steps in a Playwright page and read `observe`.

Steps: click:<css> | type:<css>:<text> | key:<key name> | wait:<ms>
`type:<css>:<text>` splits at the first ':' that is (a) outside [...] and (...) and
(b) not the start of a known pseudo-class (nth-child, nth-of-type, first-child, last-child,
not, checked, disabled, focus, hover, has, is, where, empty). So `type:input:nth-child(2):hi`
-> (`input:nth-child(2)`, `hi`) and `type:[name="a:b"]:x` -> (`[name="a:b"]`, `x`); the text may
contain ':'. Limitation: text that itself starts with a pseudo-class name right after the
separator (e.g. `type:#x:checked`) is read as part of the selector.
Requests to any other origin than the app URL are aborted; goto waits for domcontentloaded (10 s).
Typing sends real key events: click, Control+A, Delete, then press_sequentially (old apps that
listen on keyup/keypress work). After the last step the page settles (networkidle, then the
observed text must be equal across two reads 50 ms apart, max 1500 ms) before `observe` is read.
"""
from __future__ import annotations

import re
import time
from urllib.parse import urlsplit

ACTION_TIMEOUT_MS = 2000
GOTO_TIMEOUT_MS = 10000
SETTLE_MAX_MS = 1500
SETTLE_POLL_MS = 50
_FUNC_PSEUDO = ("nth-child", "nth-of-type", "not", "has", "is", "where")
_BARE_PSEUDO = ("first-child", "last-child", "checked", "disabled", "focus", "hover", "empty")
_PSEUDO_RE = re.compile(
    r"(?:(?:%s)\(|(?:%s)(?![A-Za-z0-9_-]))" % ("|".join(_FUNC_PSEUDO), "|".join(_BARE_PSEUDO)))


def launch_browser(pw):
    """Chromium for the court. COURT_BROWSER_CHANNEL=chrome (or msedge) uses the installed
    browser instead of Playwright's downloaded Chromium, e.g. on a demo laptop."""
    import os
    channel = os.environ.get("COURT_BROWSER_CHANNEL") or None
    return pw.chromium.launch(channel=channel) if channel else pw.chromium.launch()


def split_type(rest: str):
    """Split `<css>:<text>` per the rule in the module docstring; None if no separator."""
    depth, quote = 0, None
    for i, ch in enumerate(rest):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'" and depth:
            quote = ch
        elif ch in "[(":
            depth += 1
        elif ch in "])":
            depth = max(0, depth - 1)
        elif ch == ":" and depth == 0 and not _PSEUDO_RE.match(rest, i + 1):
            return rest[:i], rest[i + 1:]
    return None


class StepError(ValueError):
    """A step string that doesn't match the contract grammar."""


def parse(step: str) -> tuple[str, list[str]]:
    kind, sep, rest = step.partition(":")
    if not sep or not rest:
        raise StepError(f"bad step {step!r}")
    if kind == "click":
        return kind, [rest]
    if kind == "type":
        parts = split_type(rest)
        if not parts or not parts[0]:
            raise StepError(f"bad type step {step!r}, want type:<css>:<text>")
        return kind, [parts[0], parts[1]]
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
    origin = urlsplit(url)[:2]

    def _same_origin(route):
        if urlsplit(route.request.url)[:2] == origin or route.request.url.startswith(("data:", "blob:", "about:")):
            route.continue_()
        else:
            route.abort()  # offline-deterministic: no fonts/CDNs/analytics, identical for both builds
    try:
        page.route("**/*", _same_origin)
        page.goto(url, wait_until="domcontentloaded", timeout=GOTO_TIMEOUT_MS)
    except Exception as e:  # noqa: BLE001 - connection refused, DNS, timeout: the oracle is unreachable
        return f"ERROR:load {type(e).__name__}"
    for i, (kind, args) in enumerate(parsed):
        try:
            if kind == "click":
                page.click(args[0], timeout=ACTION_TIMEOUT_MS)
            elif kind == "type":
                page.click(args[0], timeout=ACTION_TIMEOUT_MS)
                page.keyboard.press("Control+A")
                page.keyboard.press("Delete")
                page.locator(args[0]).press_sequentially(args[1], timeout=ACTION_TIMEOUT_MS)
            elif kind == "key":
                page.keyboard.press(args[0])
            elif kind == "wait":
                page.wait_for_timeout(int(args[0]))
        except Exception as e:  # noqa: BLE001 - any Playwright failure is an observation
            return f"ERROR:step {i} {steps[i]}: {type(e).__name__}"
    try:
        page.wait_for_load_state("networkidle", timeout=2000)
    except Exception:  # noqa: BLE001 - a busy page is fine, we poll below
        pass
    try:
        cur = page.inner_text(observe, timeout=ACTION_TIMEOUT_MS)
        deadline = time.monotonic() + SETTLE_MAX_MS / 1000
        while time.monotonic() < deadline:
            page.wait_for_timeout(SETTLE_POLL_MS)
            nxt = page.inner_text(observe, timeout=ACTION_TIMEOUT_MS)
            if nxt == cur:
                break
            cur = nxt
        return cur.strip()
    except Exception as e:  # noqa: BLE001
        return f"ERROR:observe {observe}: {type(e).__name__}"
