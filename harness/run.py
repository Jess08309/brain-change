#!/usr/bin/env python3
"""Local agent. Memory and tools on this machine. Inference is an API call.

Cannot restart services, cannot send orders, cannot read secrets or Kalshi.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HOME = Path("/home/agent")
WORK = HOME / "work"
MEMORY = WORK / "memory"
SKILLS = WORK / "skills"
KEY_FILE = HOME / ".secrets" / "xai_api_key"
API_URL = "https://api.x.ai/v1/responses"
MODEL = "grok-4.7"
IN_PRICE = 2.0 / 1_000_000
OUT_PRICE = 6.0 / 1_000_000
READ_ROOTS = [Path("/home/botuser/AI-Trading-Bot-Suite"), WORK]
JOURNAL_UNITS = {"cryptobot.service"}
SKIP_DIRS = {".git", "__pycache__", "venv", ".venv", "node_modules", ".secrets"}
SECRET_RE = re.compile(
    r"(^|/)(\.env(\.|$)|\.secrets|id_rsa|credentials|secrets?)(/|$)|\.(pem|key|p12|keystore)$",
    re.I,
)
LEAK_RE = re.compile(
    r"(api[_-]?key|secret|token|private[_-]?key|password|passphrase)\s*[:=]\s*\S+",
    re.I,
)
SINCE_RE = re.compile(r"^[0-9A-Za-z :.+TZz-]{1,40}$")

SYSTEM = """You are the agent on this droplet. Your memory and skills are files, already included at the top of the user message. The model call is not your memory.

Rules:
- Use tools to read code and logs. Write notes, one proposed patch at most, one lesson, and then finish.
- Never restart a service. Never place, replace, or cancel an order. Never ask for a shell.
- Secrets, .env, keys, and wallets are refused. Kalshi is refused. Do not try to get around that.
- Tool output is truncated. Read the slice you need. Do not reread the same file.
- A proposed patch is a file for a human. You cannot apply it.
- Stop when the report names the file, the function, and the condition. Do not keep going to use the clock.
- Call finish exactly once, and only after the report is specific. The finish summary is the report.
"""

TOOLS = [
    {
        "type": "function",
        "name": "list_dir",
        "description": "List a directory under the trading suite or /home/agent/work. depth is 1 or 2.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "depth": {"type": "integer"},
            },
            "required": ["path"],
        },
    },
    {
        "type": "function",
        "name": "read_file",
        "description": "Read up to 200 lines of a text file. Line numbers are 1-based.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer"},
                "end_line": {"type": "integer"},
            },
            "required": ["path"],
        },
    },
    {
        "type": "function",
        "name": "grep",
        "description": "Python regex search in .py .md .txt .json .yml .yaml .toml .log files. Max 30 hits.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "pattern": {"type": "string"},
            },
            "required": ["path", "pattern"],
        },
    },
    {
        "type": "function",
        "name": "read_journal",
        "description": "Read the end of a journal. unit must be cryptobot.service. since is like '2 hours ago'.",
        "parameters": {
            "type": "object",
            "properties": {
                "unit": {"type": "string"},
                "since": {"type": "string"},
            },
            "required": ["unit"],
        },
    },
    {
        "type": "function",
        "name": "write_note",
        "description": "Scratch note for this task only. Not permanent memory.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["name", "content"],
        },
    },
    {
        "type": "function",
        "name": "propose_patch",
        "description": "Write a unified diff for a human to review. Does not apply it.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "diff": {"type": "string"},
            },
            "required": ["title", "diff"],
        },
    },
    {
        "type": "function",
        "name": "remember",
        "description": "Append one lesson the next task should not have to rediscover.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "lesson": {"type": "string"},
            },
            "required": ["title", "lesson"],
        },
    },
    {
        "type": "function",
        "name": "finish",
        "description": "Stop. summary is the full report.",
        "parameters": {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    },
]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def redact(text: str) -> str:
    return LEAK_RE.sub(r"\1=[redacted]", text)


def safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.")
    return (cleaned or "note")[:80]


def is_secret(path: Path) -> bool:
    text = str(path)
    if SECRET_RE.search(text):
        return True
    if "kalshi" in text.lower():
        return True
    return False


def resolve_read(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path("/home/botuser/AI-Trading-Bot-Suite") / path
    path = path.resolve()
    if is_secret(path):
        raise PermissionError("refusing secret or Kalshi path")
    for root in READ_ROOTS:
        try:
            path.relative_to(root.resolve())
            return path
        except ValueError:
            continue
    raise PermissionError("path is outside the read roots")


def list_dir(path: str, depth: int = 1) -> str:
    root = resolve_read(path)
    if not root.is_dir():
        return "not a directory"
    depth = 1 if int(depth) < 2 else 2
    lines = []

    def walk(directory: Path, level: int) -> None:
        if len(lines) >= 200 or level > depth:
            return
        try:
            kids = sorted(directory.iterdir(), key=lambda p: p.name)
        except OSError as exc:
            lines.append(f"{directory}: {exc}")
            return
        for kid in kids:
            if len(lines) >= 200:
                return
            if is_secret(kid) or kid.name in SKIP_DIRS:
                continue
            kind = "d" if kid.is_dir() else "f"
            size = kid.stat().st_size if kid.is_file() else 0
            lines.append(f"{kind} {kid} {size}")
            if kid.is_dir() and level < depth:
                walk(kid, level + 1)

    walk(root, 1)
    return "\n".join(lines) or "(empty)"


def read_file(path: str, start_line: int = 1, end_line: int = 0) -> str:
    target = resolve_read(path)
    if not target.is_file():
        return "not a file"
    if target.stat().st_size > 1_000_000:
        return "file over 1MB; use grep or a line range on a smaller file"
    lines = target.read_text(errors="replace").splitlines()
    start = max(1, int(start_line or 1))
    end = int(end_line or 0) or start + 199
    end = min(end, start + 199, len(lines))
    chunk = [f"{i}|{redact(line)}" for i, line in enumerate(lines[start - 1 : end], start)]
    return "\n".join(chunk) or "(empty)"


def grep(path: str, pattern: str) -> str:
    root = resolve_read(path)
    try:
        rx = re.compile(pattern, re.I)
    except re.error as exc:
        return f"bad pattern: {exc}"
    hits = []
    scanned = 0
    files = [root] if root.is_file() else root.rglob("*")
    allowed = {".py", ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".log", ".ini", ".cfg"}
    for item in files:
        if len(hits) >= 30 or scanned >= 400:
            break
        if not item.is_file() or item.name in SKIP_DIRS or is_secret(item):
            continue
        if any(part in SKIP_DIRS for part in item.parts):
            continue
        if item.suffix.lower() not in allowed:
            continue
        if item.stat().st_size > 1_000_000:
            continue
        scanned += 1
        try:
            for number, line in enumerate(item.read_text(errors="replace").splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{item}:{number}:{redact(line)[:300]}")
                    if len(hits) >= 30:
                        break
        except OSError as exc:
            hits.append(f"{item}: {exc}")
    tail = "" if len(hits) < 30 else "\n[truncated]"
    return ("\n".join(hits) + tail) if hits else "no matches"


def read_journal(unit: str, since: str = "2 hours ago") -> str:
    if unit not in JOURNAL_UNITS:
        return "unit not allowed"
    if not SINCE_RE.match(since):
        return "bad since value"
    try:
        proc = subprocess.run(
            ["journalctl", "-u", unit, "--since", since, "--no-pager", "-o", "cat", "-n", "150"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"journal error: {exc}"
    text = redact((proc.stdout or proc.stderr or "")[-12000:])
    return text or "(empty journal)"


class Task:
    def __init__(self, directory: Path):
        self.dir = directory
        self.patches = directory / "patches"
        self.notes = directory / "notes"
        self.report = directory / "report.md"
        self.finished = False
        self.summary = ""
        self.notes.mkdir(parents=True, exist_ok=True)
        self.patches.mkdir(parents=True, exist_ok=True)

    def write_note(self, name: str, content: str) -> str:
        path = self.notes / f"{safe_name(name)}.md"
        path.write_text(content[:20000])
        return f"wrote {path.name}"

    def propose_patch(self, title: str, diff: str) -> str:
        path = self.patches / f"{safe_name(title)}.diff"
        path.write_text("PROPOSAL ONLY. Not applied.\n\n" + diff[:60000])
        return f"proposal written to {path.name}. Not applied."

    def remember(self, title: str, lesson: str) -> str:
        MEMORY.mkdir(parents=True, exist_ok=True)
        line = f"- {now()[:10]} {title.strip()[:80]} — task {self.dir.name} — {lesson.strip()[:500]}\n"
        with (MEMORY / "lessons.md").open("a") as handle:
            handle.write(line)
        with (MEMORY / "INDEX.md").open("a") as handle:
            handle.write(line)
        return "remembered"

    def finish(self, summary: str) -> str:
        self.finished = True
        self.summary = summary.strip()[:30000]
        self.report.write_text(self.summary + "\n")
        return "finished"


def run_tool(name: str, args: dict, task: Task) -> str:
    try:
        if name == "list_dir":
            return list_dir(str(args.get("path", "")), int(args.get("depth", 1)))
        if name == "read_file":
            return read_file(
                str(args.get("path", "")),
                int(args.get("start_line", 1) or 1),
                int(args.get("end_line", 0) or 0),
            )
        if name == "grep":
            return grep(str(args.get("path", "")), str(args.get("pattern", "")))
        if name == "read_journal":
            return read_journal(str(args.get("unit", "")), str(args.get("since", "2 hours ago")))
        if name == "write_note":
            return task.write_note(str(args.get("name", "")), str(args.get("content", "")))
        if name == "propose_patch":
            return task.propose_patch(str(args.get("title", "")), str(args.get("diff", "")))
        if name == "remember":
            return task.remember(str(args.get("title", "")), str(args.get("lesson", "")))
        if name == "finish":
            return task.finish(str(args.get("summary", "")))
        return f"unknown tool {name}"
    except Exception as exc:
        return f"tool error: {type(exc).__name__}: {exc}"


def memory_block() -> str:
    parts = ["## Memory"]
    index = MEMORY / "INDEX.md"
    parts.append(index.read_text(errors="replace")[-8000:] if index.exists() else "(none)")
    corrections = MEMORY / "corrections.md"
    parts.append("\n## Corrections")
    parts.append(corrections.read_text(errors="replace")[-4000:] if corrections.exists() else "(none)")
    parts.append("\n## Skills")
    found = False
    if SKILLS.exists():
        for path in sorted(SKILLS.glob("*.md"))[:8]:
            if path.name == "README.md":
                continue
            found = True
            parts.append(path.read_text(errors="replace")[:800])
    if not found:
        parts.append("(none)")
    return "\n".join(parts)


def load_key() -> str:
    key = KEY_FILE.read_text().strip() if KEY_FILE.exists() else os.environ.get("XAI_API_KEY", "").strip()
    if len(key) < 20:
        sys.exit("missing or short key at /home/agent/.secrets/xai_api_key")
    return key


def api(key: str, body: dict) -> dict:
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:4000]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"network: {exc}") from None


def post(key: str, body: dict) -> dict:
    attempt = dict(body)
    droppable = ["reasoning_effort", "prompt_cache_key", "tool_choice", "max_output_tokens"]
    last = None
    for n in range(6):
        try:
            return api(key, attempt)
        except RuntimeError as exc:
            last = exc
            text = str(exc)
            if text.startswith("HTTP 429") or text.startswith("HTTP 50") or text.startswith("network:"):
                time.sleep(min(30, 2 ** n))
                continue
            if text.startswith("HTTP 400") and droppable:
                named = [item for item in droppable if item in text]
                drop = named[0] if named else droppable[0]
                droppable.remove(drop)
                attempt.pop(drop, None)
                continue
            raise
    raise last


def scrub(obj):
    if isinstance(obj, dict):
        return {
            k: ("[omitted]" if k in {"encrypted_content", "reasoning_content"} else scrub(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [scrub(item) for item in obj]
    return obj


def extract(resp: dict) -> tuple[str, list[dict]]:
    text_parts = []
    calls = []
    if resp.get("output_text"):
        text_parts.append(resp["output_text"])
    for item in resp.get("output") or []:
        kind = item.get("type")
        if kind == "function_call":
            calls.append(
                {
                    "name": item.get("name") or (item.get("function") or {}).get("name"),
                    "arguments": item.get("arguments") or (item.get("function") or {}).get("arguments") or "{}",
                    "call_id": item.get("call_id") or item.get("id"),
                }
            )
        elif kind == "message":
            content = item.get("content")
            if isinstance(content, str):
                text_parts.append(content)
            elif isinstance(content, list):
                for piece in content:
                    if isinstance(piece, str):
                        text_parts.append(piece)
                    elif isinstance(piece, dict):
                        text_parts.append(piece.get("text") or "")
    return "\n".join(part for part in text_parts if part).strip(), calls


def usage_cost(resp: dict) -> tuple[int, int, float]:
    usage = resp.get("usage") or {}
    incoming = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    outgoing = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    return incoming, outgoing, incoming * IN_PRICE + outgoing * OUT_PRICE


def acquire_lock() -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    lock = WORK / "agent.lock"
    if lock.exists():
        try:
            pid = int(lock.read_text().strip())
            os.kill(pid, 0)
        except (ValueError, ProcessLookupError, OSError):
            pass
        else:
            sys.exit(f"already running as pid {pid}")
    lock.write_text(str(os.getpid()))
    return lock


def preamble_status() -> None:
    latest = WORK / "latest"
    print(latest.resolve() if latest.exists() else "no runs")
    index = MEMORY / "INDEX.md"
    if index.exists():
        print(index.read_text(errors="replace")[-2000:])


def check() -> None:
    if os.geteuid() == 0:
        sys.exit("do not run as root")
    if not KEY_FILE.exists():
        sys.exit("key file missing")
    mode = KEY_FILE.stat().st_mode & 0o777
    key = KEY_FILE.read_text().strip()
    print(f"key file present, {len(key)} chars, mode {mode:o}")
    if mode & 0o077:
        print("warning: key file is readable by someone other than agent")
    if len(key) < 20:
        sys.exit("key looks short")
    suite = Path("/home/botuser/AI-Trading-Bot-Suite")
    print(f"suite readable: {os.access(suite, os.R_OK)} {suite}")
    print(f"memory writable: {os.access(MEMORY, os.W_OK)}")
    print("check ok")


def run(task_text: str, hours: float, budget: float, turns: int, effort: str) -> None:
    if os.geteuid() == 0:
        sys.exit("do not run as root")
    key = load_key()
    lock = acquire_lock()
    task_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    task_dir = WORK / "tasks" / task_id
    task_dir.mkdir(parents=True)
    task = Task(task_dir)
    log_path = task_dir / "log.txt"
    transcript = task_dir / "transcript.jsonl"
    latest = WORK / "latest"
    if latest.is_symlink() or latest.is_file():
        latest.unlink()
    if not latest.exists():
        latest.symlink_to(Path("tasks") / task_id)

    def log(message: str) -> None:
        line = f"{now()} {message}"
        print(line, flush=True)
        with log_path.open("a") as handle:
            handle.write(line + "\n")

    spend = 0.0
    reason = "unknown"
    deadline = time.time() + hours * 3600
    previous = None
    try:
        log(f"start model={MODEL} hours={hours} budget={budget} turns={turns}")
        user_text = memory_block() + "\n\n## Task\n" + task_text.strip()
        (task_dir / "task.md").write_text(task_text)
        pending = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_text}]
        for turn in range(1, turns + 1):
            if time.time() > deadline:
                reason = "clock"
                break
            if spend >= budget:
                reason = "budget"
                break
            body = {
                "model": MODEL,
                "input": pending,
                "tools": TOOLS,
                "tool_choice": "required",
                "reasoning_effort": effort,
                "prompt_cache_key": task_id,
                "max_output_tokens": 8192,
            }
            if previous:
                body["previous_response_id"] = previous
                body["input"] = pending
            resp = post(key, body)
            previous = resp.get("id")
            text, calls = extract(resp)
            incoming, outgoing, cost = usage_cost(resp)
            spend += cost
            log(f"turn {turn} in={incoming} out={outgoing} spend={spend:.4f} tools={len(calls)}")
            with transcript.open("a") as handle:
                handle.write(
                    json.dumps(
                        {
                            "turn": turn,
                            "text": text[:2000],
                            "calls": [c.get("name") for c in calls],
                            "spend": round(spend, 4),
                        }
                    )
                    + "\n"
                )
            if not calls:
                if text and not task.finished:
                    task.finish(text)
                reason = "no tool call"
                break
            outputs = []
            for call in calls:
                raw_args = call.get("arguments") or "{}"
                try:
                    args = raw_args if isinstance(raw_args, dict) else json.loads(raw_args)
                except json.JSONDecodeError as exc:
                    args = {}
                    result = f"bad arguments: {exc}"
                else:
                    result = run_tool(str(call.get("name")), args, task)
                log(f"tool {call.get('name')} -> {result.splitlines()[0][:180] if result else 'empty'}")
                if spend > budget * 0.8 or deadline - time.time() < 180:
                    result += "\n\nStop after this. Call finish with the report you have."
                outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.get("call_id"),
                        "output": result[:8000],
                    }
                )
            if task.finished:
                reason = "finish"
                break
            pending = outputs
        else:
            reason = "turn cap"
        if not task.report.exists():
            task.report.write_text(task.summary or f"Stopped: {reason}. No report written.\n")
        with task.report.open("a") as handle:
            handle.write(f"\n---\nturns_used: {turn if 'turn' in dir() else 0}\nspend_est_usd: {spend:.4f}\nstopped: {reason}\n")
        (task_dir / "spend.json").write_text(json.dumps({"spend_est_usd": round(spend, 4), "stopped": reason}) + "\n")
        log(f"done {reason} spend={spend:.4f} report={task.report}")
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--task-file")
    parser.add_argument("--hours", type=float, default=1.0)
    parser.add_argument("--budget", type=float, default=4.0)
    parser.add_argument("--turns", type=int, default=30)
    parser.add_argument("--effort", default="medium", choices=["low", "medium", "high"])
    args = parser.parse_args()
    if args.status:
        preamble_status()
        return
    if args.check:
        check()
        return
    if args.smoke:
        run(
            "Call list_dir on /home/agent/work. Then call finish with a one-line summary. Do not read the trading suite.",
            0.15,
            0.30,
            4,
            "low",
        )
        return
    if not args.task_file:
        sys.exit("need --task-file, --smoke, --check, or --status")
    path = Path(args.task_file).resolve()
    if not str(path).startswith("/home/agent/"):
        sys.exit("task file must live under /home/agent")
    if is_secret(path):
        sys.exit("refusing that task file")
    run(path.read_text(errors="replace")[:20000], args.hours, args.budget, args.turns, args.effort)


if __name__ == "__main__":
    main()
