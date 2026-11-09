"""wokwi-cli wrapper: build the argv for one run and turn its exit code + output into a verdict.

Message formats come from the wokwi-cli source (tests/fixtures/wokwi/NOTES.md).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

TIMEOUT_EXIT = 42
SERIAL_TAIL = 60

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
PIN_FAIL_RE = re.compile(r"GPIO (?P<part>[\w-]+):(?P<pin>[\w.+-]+) expected to be (?P<want>\d) but was (?P<got>\d)")
NANOS_RE = re.compile(r"\[(\d+)ns\]")
FAIL_TEXT_RE = re.compile(r'Unexpected text found: "(?P<text>.*)"')
MATCHED_RE = re.compile(r"Expected text matched: ")


@dataclass
class SimResult:
    passed: bool
    reason: str
    kind: str                       # passed | expectation | fail_text | timeout | error
    raw_reason: str = ""
    sim_ms: int = 0
    error: str = ""                 # tool error code when the run itself couldn't happen
    hint: str = ""
    serial_tail: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = {"passed": self.passed, "reason": self.reason, "sim_ms": self.sim_ms,
             "serial_tail": self.serial_tail}
        if self.raw_reason and self.raw_reason != self.reason:
            d["raw_reason"] = self.raw_reason
        if self.hint:
            d["hint"] = self.hint
        return d


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def build_argv(cli: list[str], project_dir: Path, *, timeout_ms: int, serial_log: Path,
               expect_text: str = "", fail_text: str = "", scenario: Path | None = None,
               diagram_file: str = "", screenshot_part: str = "", screenshot_time_ms: int = 0,
               screenshot_file: Path | None = None) -> list[str]:
    argv = [*cli, str(project_dir), "--timeout", str(int(timeout_ms)),
            "--timeout-exit-code", str(TIMEOUT_EXIT), "--serial-log-file", str(serial_log), "--quiet"]
    if expect_text:
        argv += ["--expect-text", expect_text]
    if fail_text:
        argv += ["--fail-text", fail_text]
    if scenario is not None:
        argv += ["--scenario", str(scenario)]
    if diagram_file:
        argv += ["--diagram-file", diagram_file]
    if screenshot_part:
        argv += ["--screenshot-part", screenshot_part, "--screenshot-time",
                 str(int(screenshot_time_ms or timeout_ms))]
        if screenshot_file is not None:
            argv += ["--screenshot-file", str(screenshot_file)]
    return argv


def _unglue(line: str, waits: list[str]) -> list[str]:
    """wokwi-cli drops the newline right after text a ``wait-serial`` step matched (its scenario
    log line takes the newline's place), so "BOOT OK" and the next line arrive glued together.
    Split them again at the end of the first waited-for text found mid-line."""
    for w in waits:
        i = line.find(w) if w else -1
        if i >= 0 and i + len(w) < len(line):
            head, rest = line[:i + len(w)], line[i + len(w):]
            return [head, *_unglue(rest, waits)]
    return [line]


def serial_tail(log_text: str, n: int = SERIAL_TAIL, waits: list[str] | None = None) -> list[str]:
    lines = [ln.rstrip("\r") for ln in strip_ansi(log_text).splitlines() if ln.strip()]
    if waits:
        lines = [part for ln in lines for part in _unglue(ln, waits) if part.strip()]
    return [ln[:200] for ln in lines[-n:]]


def _last_error_line(text: str) -> str:
    for line in reversed(text.splitlines()):
        s = line.strip()
        if s and not s.startswith("at ") and s not in ("TEST FAILED.",):
            return s[:300]
    return ""


def classify(code: int | None, stdout: str, stderr: str, *, timeout_ms: int, expect_text: str = "",
             waits: list[str] | None = None, serial: str = "", wall_timed_out: bool = False) -> SimResult:
    """Classify one wokwi-cli run.

    ``waits`` is the ordered list of ``wait-serial`` texts in the scenario, used to say which
    expected line never appeared when the run times out.
    """
    out, err = strip_ansi(stdout), strip_ansi(stderr)
    both = out + "\n" + err
    tail = serial_tail(serial or out, waits=waits)
    nanos = NANOS_RE.findall(both)
    sim_ms = int(int(nanos[-1]) / 1_000_000) if nanos else timeout_ms

    def res(passed, reason, kind, raw="", **kw):
        return SimResult(passed, reason, kind, raw or reason, sim_ms, serial_tail=tail, **kw)

    if wall_timed_out:
        return res(False, "wokwi-cli did not answer in time (network or Wokwi service problem)",
                   "error", error="timeout", hint="Check your connection and retry; the run was stopped.")
    if "Missing WOKWI_CLI_TOKEN" in both:
        return res(False, "Wokwi token missing", "error", _last_error_line(err), error="token_missing",
                   hint="Set the 'Wokwi CI token' plugin setting (from https://wokwi.com/dashboard/ci).")
    if re.search(r"API Error:.*(unauthori[sz]ed|invalid token|forbidden|401|403)", both, re.I):
        return res(False, "Wokwi rejected the token", "error", _last_error_line(err), error="token_missing",
                   hint="Create a new token at https://wokwi.com/dashboard/ci and update the setting.")
    if "firmware file not found" in both or "ELF file not found" in both:
        return res(False, "firmware not built", "error", _last_error_line(err), error="bad_args",
                   hint="Run mcu_compile first.")

    if code == 0:
        if waits is not None:
            return res(True, "all scenario steps passed", "passed")
        if expect_text:
            return res(True, f"expected text seen: {expect_text}", "passed")
        return res(True, "simulation ran without errors", "passed")

    if code == TIMEOUT_EXIT:
        sim_ms = timeout_ms
        if waits is not None:
            matched = len(MATCHED_RE.findall(out))
            if matched < len(waits):
                missing = waits[matched]
                return SimResult(False, f"expected serial '{missing}' not seen", "expectation",
                                 _last_error_line(err), sim_ms, serial_tail=tail)
            return SimResult(False, f"timed out after {timeout_ms} ms", "timeout",
                             _last_error_line(err), sim_ms, serial_tail=tail)
        if expect_text:
            return SimResult(False, f"expected text never appeared: {expect_text}", "expectation",
                             _last_error_line(err), sim_ms, serial_tail=tail)
        # No expectation: running until the timeout is the normal end of a plain run.
        return SimResult(True, f"ran for {timeout_ms} ms (no expectation set)", "passed",
                         "", sim_ms, serial_tail=tail)

    if m := PIN_FAIL_RE.search(both):
        return res(False, f"expected {m['part']}:{m['pin']} = {m['want']}, got {m['got']}",
                   "expectation", _last_error_line(err))
    if m := FAIL_TEXT_RE.search(both):
        bad = next((ln for ln in reversed(tail) if m["text"] in ln), "")
        reason = f"fail text seen: {bad or m['text']}"
        return res(False, reason, "fail_text", _last_error_line(err))
    if "Screenshot mismatch" in both or "Comparison file" in both:
        return res(False, _last_error_line(err), "expectation")
    if "Invalid scenario step key" in both or "Unsupported scenario version" in both:
        return res(False, "BoardLoop generated a scenario this wokwi-cli does not accept", "error",
                   _last_error_line(err), error="wokwi_error",
                   hint="Update wokwi-cli (see mcu_doctor) and report the raw_reason.")
    line = _last_error_line(err) or _last_error_line(out) or f"wokwi-cli exited with code {code}"
    return res(False, line, "error", error="wokwi_error",
               hint="Run mcu_doctor; check the diagram with mcu_wiring_check.")
