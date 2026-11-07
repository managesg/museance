"""Shrinker: smallest step list that still makes original and revival disagree.

Greedy one-step-at-a-time removal (repeat until no single removal keeps the mismatch).
Steps lists are short (<= ~15), so this is cheap and its result is 1-minimal:
removing any one remaining step makes the builds agree again.
"""
from __future__ import annotations

from typing import Callable


def shrink(steps: list[str], still_differs: Callable[[list[str]], bool]) -> list[str]:
    cur = list(steps)
    changed = True
    while changed and cur:
        changed = False
        for i in range(len(cur)):
            cand = cur[:i] + cur[i + 1:]
            if still_differs(cand):
                cur = cand
                changed = True
                break
    return cur
