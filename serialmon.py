"""Real-board serial monitor (pyserial, imported lazily so the plugin loads without it)."""
from __future__ import annotations

import re
import time

PORT_RE = re.compile(r"^(/dev/tty[\w.-]+|/dev/cu\.[\w.-]+|COM\d{1,3})$")
BAUDS = {9600, 19200, 38400, 57600, 74880, 115200, 230400, 460800, 921600}
MAX_SECONDS = 30
MAX_LINES = 60


class SerialUnavailable(Exception):
    pass


def _serial():
    try:
        import serial  # type: ignore[import-not-found]
    except ImportError:
        raise SerialUnavailable("pyserial is not installed") from None
    return serial


def available() -> bool:
    try:
        _serial()
        return True
    except SerialUnavailable:
        return False


def check_expectations(lines: list[str], expect: list[str]) -> tuple[bool, str]:
    """Each expected text must appear, in order, across the captured lines."""
    i = 0
    for line in lines:
        if i < len(expect) and expect[i] in line:
            i += 1
    if i == len(expect):
        return True, "all expected lines seen"
    return False, f"expected serial '{expect[i]}' not seen"


def read(port: str, baud: int = 115200, seconds: float = 5, until_text: str = "",
         opener=None) -> list[str]:
    """Read lines for up to ``seconds`` (max 30), stopping early at ``until_text``."""
    seconds = max(0.5, min(float(seconds), MAX_SECONDS))
    open_ = opener or _serial().Serial
    lines: list[str] = []
    deadline = time.monotonic() + seconds
    with open_(port, baud, timeout=0.2) as conn:
        buf = b""
        while time.monotonic() < deadline:
            chunk = conn.read(512)
            if not chunk:
                continue
            buf += chunk
            *done, buf = buf.split(b"\n")
            for raw in done:
                line = raw.decode("utf-8", errors="replace").rstrip("\r")
                if line.strip():
                    lines.append(line[:200])
            if until_text and any(until_text in ln for ln in lines):
                break
        if buf.strip():
            lines.append(buf.decode("utf-8", errors="replace").rstrip("\r")[:200])
    return lines[-MAX_LINES:]


def write(port: str, baud: int, text: str, opener=None) -> int:
    open_ = opener or _serial().Serial
    data = (text + "\n").encode("utf-8")
    with open_(port, baud, timeout=1, write_timeout=2) as conn:
        n = conn.write(data)
        conn.flush()
    return int(n or 0)
