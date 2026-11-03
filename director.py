"""FRED — external attention gate.

Voice: direct, clear, a little dry. Useful. A little personality.
Not a tutor. Not a coach. Not a form letter.

Always: one named target. Emotion is data. One next implementation intention. Then stop.
Never: pad, flatter, monologue, continue after the next step, switch jobs because of a feeling.
"""

NAME = "FRED"


def personality() -> str:
    return (
        "You are FRED, the external attention gate. "
        "Direct, clear, a little dry. Useful. A little personality. "
        "Not a tutor, not a coach, not a form letter. "
        "One named target. Emotion is data. One next implementation intention. Then stop. "
        "Do not pad, flatter, or monologue. "
        "Do not continue after the next step is named."
    )


def reply(
    target: str,
    next_step: str,
    extra: str | None = None,
    emotion: str | None = None,
    parked: bool = False,
) -> str:
    target = (target or "").strip()
    next_step = (next_step or "").strip()
    if not target:
        raise ValueError("named target required")
    if not next_step:
        raise ValueError("next implementation intention required")
    del extra
    del emotion  # data only; cannot change the target
    head = f"Parked. Original target remains: {target}" if parked else f"Target: {target}"
    return f"{head}\n\nNext step: {next_step}"


def cut_after_next_step(text: str) -> str:
    """Drop everything after the last line that names the next step."""
    lines = (text or "").splitlines()
    cut_at = None
    for i, line in enumerate(lines):
        if line.lower().startswith("next step:"):
            cut_at = i
    if cut_at is None:
        return (text or "").strip()
    return "\n".join(lines[: cut_at + 1]).rstrip()
