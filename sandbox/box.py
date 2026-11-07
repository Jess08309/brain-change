"""One debug box for the gate.

It listens on this machine only. It writes only inside the box.
It does not replace Windows, and it does not take over another system.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from director import reply
from laptop.surface import handle

HOST = "127.0.0.1"
PORT = 8765


def box_home(root: Path) -> Path:
    home = root / "local" / "sandbox" / "home"
    (home / "inbox").mkdir(parents=True, exist_ok=True)
    (home / "memory").mkdir(parents=True, exist_ok=True)
    return home


def box_dir(root: Path) -> Path:
    path = root / "local" / "sandbox"
    path.mkdir(parents=True, exist_ok=True)
    return path


def confine(path: Path, box: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(box.resolve())
    except ValueError as exc:
        raise PermissionError("path is outside the sandbox") from exc
    return resolved


def log_path(root: Path) -> Path:
    return box_dir(root) / "debug.log"


def pid_path(root: Path) -> Path:
    return box_dir(root) / "pid"


def log_line(root: Path, text: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with log_path(root).open("a", encoding="utf-8") as handle_file:
        handle_file.write(f"{stamp} {text}\n")


def alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def read_pid(root: Path) -> int:
    path = pid_path(root)
    if not path.is_file():
        return 0
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return 0


def serve(root: Path, port: int = PORT) -> None:
    home = box_home(root)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, port))
    sock.listen(1)
    pid_path(root).write_text(str(os.getpid()), encoding="utf-8")
    log_line(root, f"listening {HOST}:{port}")
    try:
        while True:
            conn, addr = sock.accept()
            with conn:
                if addr[0] != HOST:
                    log_line(root, "refused remote")
                    continue
                raw = conn.recv(4000).decode("utf-8", errors="replace").strip()
                try:
                    out = handle(raw, home)
                except Exception as exc:
                    out = reply("sandbox", f"stopped: {type(exc).__name__}")
                log_line(root, "one line handled")
                conn.sendall((out + "\n").encode("utf-8"))
    finally:
        sock.close()


def start(root: Path) -> str:
    pid = read_pid(root)
    if alive(pid):
        return reply("sandbox", f"already running as pid {pid} on {HOST}:{PORT}")
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    box_dir(root)
    log = log_path(root).open("a", encoding="utf-8")
    subprocess.Popen(
        [sys.executable, str(root / "sandbox" / "box.py"), "serve"],
        cwd=str(root),
        env={**os.environ, "PYTHONPATH": str(root)},
        creationflags=flags,
        close_fds=True,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    for _ in range(30):
        if alive(read_pid(root)):
            return reply("sandbox", f"running as pid {read_pid(root)} on {HOST}:{PORT}. It cannot leave the box.")
        time.sleep(0.1)
    return reply("sandbox", "start failed. Read local/sandbox/debug.log.")


def status(root: Path) -> str:
    pid = read_pid(root)
    if alive(pid):
        return reply("sandbox", f"running as pid {pid} on {HOST}:{PORT}")
    return reply("sandbox", "not running")


def stop(root: Path) -> str:
    pid = read_pid(root)
    if not alive(pid):
        return reply("sandbox", "not running")
    if os.name == "nt":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x0001, False, pid)
        if not handle:
            return reply("sandbox", "not running")
        ctypes.windll.kernel32.TerminateProcess(handle, 1)
        ctypes.windll.kernel32.CloseHandle(handle)
    else:
        os.kill(pid, 15)
    return reply("sandbox", f"stopped pid {pid}")


def main(argv: list[str] | None = None) -> None:
    root = Path(__file__).resolve().parents[1]
    command = (argv or sys.argv[1:3])[:1]
    name = command[0] if command else "status"
    if name == "serve":
        serve(root)
        return
    if name == "start":
        print(start(root))
        return
    if name == "stop":
        print(stop(root))
        return
    print(status(root))


if __name__ == "__main__":
    main()
