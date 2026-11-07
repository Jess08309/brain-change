"""Laptop surface for the FRED gate.

One instruction. Then stop. This folder is the only write root.
The model key is not copied here.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from director import reply


def blocked(text: str) -> str:
    low = (text or "").lower()
    if "kalshi" in low:
        return "refused: trading path"
    if any(word in low for word in (".env", "xai_api_key", "api_key", "wallet", "password")):
        return "refused: secret"
    if "systemctl" in low or ("ssh" in low and "root" in low):
        return "refused: not a root session"
    if re.search(r"\b(place|cancel|replace)\b.{0,40}\border\b", low):
        return "refused: no orders"
    return ""


def ensure_local(root: Path) -> Path:
    local = root / "local"
    (local / "inbox").mkdir(parents=True, exist_ok=True)
    memory = local / "memory"
    memory.mkdir(parents=True, exist_ok=True)
    index = memory / "INDEX.md"
    if not index.exists():
        index.write_text(
            "Memory is this file. A model call is not memory.\n",
            encoding="utf-8",
        )
    return local


def handle(text: str, root: Path) -> str:
    problem = blocked(text)
    if problem:
        return reply("laptop surface", problem)
    ensure_local(root)
    key = root / ".secrets" / "xai_api_key"
    cleaned = (text or "").strip()
    if not cleaned:
        present = "present" if key.is_file() else "not on this machine"
        return reply(
            "laptop surface",
            f"name one task. The model key is {present}. This folder is the only write root.",
        )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (root / "local" / "inbox" / f"{stamp}.md").write_text(cleaned + "\n", encoding="utf-8")
    if not key.is_file():
        step = "task filed. The model key is not on this machine, so the call stops here."
    else:
        step = "task filed. A key file is present. The model call is not wired on this surface yet."
    return reply("laptop surface", step)
