"""One task. One model. One check. Not a debate.

Only a model with a key is enabled. Naming another model is a refusal,
not a promise to call it.
"""

from __future__ import annotations

import re

ENABLED = "grok-4.7"
URL_RE = re.compile(r"https://[^\s\"]+")
PATH_RE = re.compile(r"(/home/(?:agent|botuser)/[A-Za-z0-9_./-]+)")
REQUEST_RE = re.compile(
    r"(?i)\b(?:use|model|route to)\s+(claude|sonnet|fable|gpt[-\w.]*|grok[-\w.]*)\b"
)


class Unavailable(ValueError):
    pass


def choose(task: str) -> str:
    match = REQUEST_RE.search(task or "")
    if not match:
        return ENABLED
    name = match.group(1).lower()
    if name == ENABLED or name == "grok":
        return ENABLED
    raise Unavailable(f"refused: {name} has no key")


def source_file(task: str) -> str:
    for match in PATH_RE.finditer(task or ""):
        path = match.group(1).rstrip(".")
        lower = path.lower()
        if "kalshi" in lower or "/.secrets" in lower or lower.endswith(".env"):
            continue
        return path
    return ""


def citation(task: str) -> str:
    match = URL_RE.search(task or "")
    if not match:
        return ""
    return match.group(0).rstrip(".,")


def local_check(answer: str, source: str, cite: str = "") -> str:
    text = answer or ""
    if source:
        if source not in text:
            return "refused: answer does not name the source"
        if "Condition:" not in text:
            return "refused: answer has no Condition:"
    if cite:
        if cite not in text:
            return "refused: answer has no citation"
        if "Condition:" not in text:
            return "refused: answer has no Condition:"
    return ""


def verdict(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return "bad"
    line = stripped.splitlines()[0].strip().upper()
    if line.startswith("PASS"):
        return "pass"
    if line.startswith("FAIL"):
        return "fail"
    return "bad"
