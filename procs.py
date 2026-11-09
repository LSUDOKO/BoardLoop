"""Run external programs safely: fixed argv, no shell, wall-clock timeout, whole-tree kill."""
from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

MAX_CAPTURE = 200_000  # bytes kept per stream before parsing


@dataclass
class ProcResult:
    code: int | None          # None when the process was killed on timeout
    stdout: str
    stderr: str
    seconds: float
    timed_out: bool = False
    not_found: bool = False

    @property
    def ok(self) -> bool:
        return self.code == 0 and not self.timed_out

    @property
    def output(self) -> str:
        return (self.stdout + "\n" + self.stderr).strip()


def _truncate(data: bytes) -> str:
    if len(data) > MAX_CAPTURE:
        data = data[-MAX_CAPTURE:]  # keep the tail: errors and results are at the end
    return data.decode("utf-8", errors="replace")


def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                           capture_output=True, timeout=10, shell=False)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        try:
            proc.kill()
        except OSError:
            pass


def run(argv: list[str], *, cwd: Path | str | None = None, timeout: float = 60,
        env: dict[str, str] | None = None) -> ProcResult:
    """Run ``argv`` (a list, never a shell string) and return its result. Never raises for
    process failures: a missing program gives ``not_found``, an overrun gives ``timed_out``."""
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
        raise ValueError("argv must be a non-empty list of strings")
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    else:
        kwargs["start_new_session"] = True
    started = time.monotonic()
    try:
        proc = subprocess.Popen(
            argv, cwd=str(cwd) if cwd else None, env=env, shell=False,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs,
        )
    except FileNotFoundError:
        return ProcResult(None, "", f"program not found: {argv[0]}", 0.0, not_found=True)
    except PermissionError as exc:
        return ProcResult(None, "", f"cannot run {argv[0]}: {exc}", 0.0, not_found=True)
    try:
        out, err = proc.communicate(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            out, err = b"", b""
        timed_out = True
    seconds = round(time.monotonic() - started, 2)
    return ProcResult(
        None if timed_out else proc.returncode, _truncate(out or b""), _truncate(err or b""),
        seconds, timed_out=timed_out,
    )
