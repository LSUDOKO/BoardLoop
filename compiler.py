"""arduino-cli wrapper: compile, parse GCC errors into short fixable items, add hints."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import procs
from .config import ESP32_CORE_URL

MAX_ERRORS = 10

ERROR_RE = re.compile(
    r"^(?P<file>(?:[A-Za-z]:)?[^:\n]+?):(?P<line>\d+):(?P<col>\d+): (?P<kind>fatal error|error): (?P<msg>.+)$")
SIZE_FLASH_RE = re.compile(r"Sketch uses (\d+) bytes \((\d+)%\) of program storage space")
SIZE_RAM_RE = re.compile(r"Global variables use (\d+) bytes \((\d+)%\) of dynamic memory")
PLATFORM_RE = re.compile(r"Platform '([\w.-]+:[\w.-]+)' not found")
MISSING_HEADER_RE = re.compile(r"([\w./-]+\.h(?:pp)?): No such file or directory")

# header → arduino-cli library name (the libraries a model usually means)
HEADER_LIBRARIES = {
    "DHTesp.h": "DHT sensor library for ESPx",
    "DHT.h": "DHT sensor library",
    "Adafruit_SSD1306.h": "Adafruit SSD1306",
    "Adafruit_GFX.h": "Adafruit GFX Library",
    "Adafruit_Sensor.h": "Adafruit Unified Sensor",
    "Adafruit_NeoPixel.h": "Adafruit NeoPixel",
    "Adafruit_BMP280.h": "Adafruit BMP280 Library",
    "Adafruit_MPU6050.h": "Adafruit MPU6050",
    "U8g2lib.h": "U8g2",
    "LiquidCrystal_I2C.h": "LiquidCrystal I2C",
    "ESP32Servo.h": "ESP32Servo",
    "Servo.h": "Servo",
    "OneWire.h": "OneWire",
    "DallasTemperature.h": "DallasTemperature",
    "PubSubClient.h": "PubSubClient",
    "ArduinoJson.h": "ArduinoJson",
    "HX711.h": "HX711",
    "RTClib.h": "RTClib",
    "FastLED.h": "FastLED",
    "Keypad.h": "Keypad",
    "IRremote.h": "IRremote",
    "MFRC522.h": "MFRC522",
}


@dataclass
class CompileError:
    file: str
    line: int
    col: int
    message: str
    context: list[str] = field(default_factory=list)
    hint: str = ""

    def as_dict(self) -> dict:
        d = {"file": self.file, "line": self.line, "col": self.col, "message": self.message,
             "context": self.context}
        if self.hint:
            d["hint"] = self.hint
        return d


def library_for_header(header: str) -> str:
    base = Path(header).name
    return HEADER_LIBRARIES.get(base, Path(base).stem.replace("_", " "))


def hint_for(message: str) -> str:
    m = message.lower()
    header = MISSING_HEADER_RE.search(message)
    if header:
        if Path(header.group(1)).name == "DHTesp.h":
            return ("DHTesp times out on every read with ESP32 core 3.x in Wokwi. Use #include <DHT.h> "
                    "(DHT dht(PIN, DHT22); dht.begin(); dht.readTemperature()) and install \"DHT sensor library\" "
                    "and \"Adafruit Unified Sensor\" with mcu_libraries.")
        lib = library_for_header(header.group(1))
        return (f"Library missing: install it with mcu_libraries action=install name=\"{lib}\" "
                f"(or action=search name=\"{lib}\" if unsure).")
    if "expected ',' or ';'" in m or "expected ';'" in m:
        return "A statement just above this line is missing a ';'."
    if "was not declared in this scope" in m:
        if "did you mean" in m:
            return "Typo: use the suggested name."
        return "Undeclared name: check for a typo, a missing #include, or a variable declared later or in another function."
    if "invalid conversion" in m or "cannot convert" in m:
        return "Type mismatch: cast the value or change the variable's type."
    if "expected '}'" in m or "expected declaration" in m or "expected unqualified-id" in m:
        return "Unbalanced braces or a stray token: check the '{' '}' pairs above this line."
    if "redefinition of" in m or "multiple definition" in m:
        return "The same name is defined twice; remove or rename one."
    if "no matching function for call" in m:
        return "Wrong arguments for this function: check the library's examples for the right signature."
    if "has no member named" in m:
        return "This object has no such method in the installed library version; check its API."
    if "too few arguments" in m or "too many arguments" in m:
        return "Wrong number of arguments for this function."
    return ""


def _rel(file: str, project_dir: Path | None) -> str:
    if project_dir is not None:
        try:
            return str(Path(file).resolve().relative_to(project_dir.resolve()))
        except (ValueError, OSError):
            pass
    return Path(file).name


def _context(project_dir: Path | None, rel: str, line: int) -> list[str]:
    if project_dir is None:
        return []
    path = project_dir / rel
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    if not 1 <= line <= len(lines):
        return []
    out = [f"{line}: {lines[line - 1].rstrip()[:160]}"]
    # the previous non-blank line: a missing ';' or '}' is usually there, not on the error line
    for n in range(line - 1, max(0, line - 4), -1):
        if lines[n - 1].strip():
            out.insert(0, f"{n}: {lines[n - 1].rstrip()[:160]}")
            break
    return out


def parse_errors(output: str, project_dir: Path | None = None) -> list[CompileError]:
    """Parse GCC ``file:line:col: error: msg`` lines; dedupe, cap at 10, strip build paths."""
    seen: set[tuple] = set()
    errors: list[CompileError] = []
    for raw in output.splitlines():
        m = ERROR_RE.match(raw.strip())
        if not m:
            continue
        rel = _rel(m["file"], project_dir)
        key = (rel, m["line"], m["msg"])
        if key in seen:
            continue
        seen.add(key)
        line = int(m["line"])
        errors.append(CompileError(rel, line, int(m["col"]), m["msg"].strip()[:300],
                                   _context(project_dir, rel, line), hint_for(m["msg"])))
        if len(errors) >= MAX_ERRORS:
            break
    return errors


def parse_size(output: str) -> dict:
    out: dict = {}
    if m := SIZE_FLASH_RE.search(output):
        out["flash_bytes"], out["flash_used"] = int(m[1]), f"{m[2]}%"
    if m := SIZE_RAM_RE.search(output):
        out["ram_bytes"], out["ram_used"] = int(m[1]), f"{m[2]}%"
    return out


def core_install_command(platform: str) -> str:
    if platform.startswith("esp32:"):
        return f"arduino-cli core install {platform} --additional-urls {ESP32_CORE_URL}"
    return f"arduino-cli core install {platform}"


def classify_failure(output: str, project_dir: Path | None) -> dict:
    """Turn a failed compile into the tool's error payload."""
    if m := PLATFORM_RE.search(output):
        return {"error": "tool_missing", "message": f"Board core {m[1]} is not installed.",
                "hint": f"Run: {core_install_command(m[1])}"}
    if "Invalid FQBN" in output or "invalid FQBN" in output:
        return {"error": "bad_args", "message": "Invalid board FQBN.",
                "hint": "Use a full FQBN such as esp32:esp32:esp32 or arduino:avr:uno, or a board alias. Run mcu_doctor."}
    errors = parse_errors(output, project_dir)
    if not errors:
        tail = [ln for ln in output.strip().splitlines() if ln.strip()][-5:]
        return {"error": "compile_failed", "message": "Compilation failed.", "errors": [],
                "error_count": 0, "raw_tail": tail,
                "hint": "No file:line errors were printed; read raw_tail."}
    payload = {"error": "compile_failed",
               "message": f"{len(errors)} compile error(s); fix the first one first.",
               "errors": [e.as_dict() for e in errors], "error_count": len(errors)}
    if len(errors) > 1:
        payload["hint"] = "Later errors are often caused by the first one; fix it and compile again."
    return payload


def compile_argv(cli: list[str], fqbn: str, project_dir: Path, clean: bool = False) -> list[str]:
    argv = [*cli, "compile", "--fqbn", fqbn, "--output-dir", str(project_dir / "build")]
    if clean:
        argv.append("--clean")
    return [*argv, str(project_dir)]


def compile_project(cli: list[str], fqbn: str, project_dir: Path, *, firmware_rel: str,
                    timeout_s: int, clean: bool = False) -> dict:
    """Compile and return the tool payload (``ok`` true/false)."""
    res = procs.run(compile_argv(cli, fqbn, project_dir, clean), cwd=project_dir, timeout=timeout_s)
    if res.not_found:
        return {"ok": False, "error": "tool_missing", "message": "arduino-cli could not be started.",
                "hint": "Install arduino-cli or set arduino_cli_path; run mcu_doctor."}
    if res.timed_out:
        return {"ok": False, "error": "timeout",
                "message": f"Compile did not finish in {timeout_s} s.",
                "hint": "The first ESP32 build can take minutes; raise compile_timeout_s and retry."}
    if res.code != 0:
        return {"ok": False, **classify_failure(res.output, project_dir), "seconds": res.seconds}
    firmware = project_dir / firmware_rel
    if not firmware.is_file():
        return {"ok": False, "error": "internal",
                "message": f"Compile succeeded but {firmware_rel} was not produced.",
                "hint": "Check the board FQBN matches the project's board."}
    return {"ok": True, "firmware": firmware_rel, "firmware_bytes": firmware.stat().st_size,
            **parse_size(res.output), "seconds": res.seconds}
