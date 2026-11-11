"""Run external programs safely: fixed argv, no shell, wall-clock timeout, whole-tree kill."""
from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

MAX_CAPTURE = 200_000  # bytes kept per stream before parsing

# Children never inherit Hermes's environment (it holds every provider API key). They get only
# what arduino-cli and wokwi-cli need to run; callers add anything else explicitly (for example
# WOKWI_CLI_TOKEN, for wokwi-cli only).
PASS_ENV = (
    "PATH", "HOME", "LANG", "LANGUAGE", "LC_ALL", "LC_CTYPE", "TMPDIR", "TMP", "TEMP", "TZ",
    # proxies, so library/core downloads and the Wokwi websocket work behind a proxy
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy",
    # Windows: needed to start processes and locate per-user data folders
    "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATHEXT", "USERPROFILE", "APPDATA",
    "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
)
PASS_PREFIXES = ("ARDUINO_",)  # arduino-cli configuration (ARDUINO_DIRECTORIES_DATA, ...)


def minimal_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The environment every child process gets: an allow-list, never ``os.environ`` itself."""
    env = {k: v for k, v in os.environ.items()
           if k.upper() in PASS_ENV or k in PASS_ENV or k.startswith(PASS_PREFIXES)}
    env.update(extra or {})
    return env


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
                           capture_output=True, timeout=10, shell=False, env=minimal_env())
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
    process failures: a missing program gives ``not_found``, an overrun gives ``timed_out``.
    ``env`` defaults to :func:`minimal_env`; pass one built from it, never ``os.environ``."""
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
        raise ValueError("argv must be a non-empty list of strings")
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    else:
        kwargs["start_new_session"] = True
    if env is None:
        env = minimal_env()
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
