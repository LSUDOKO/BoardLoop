#!/usr/bin/env python3
"""Fake arduino-cli for tests. Output formats mirror the real tool (tests/fixtures/gcc, arduino).

compile: fails with real GCC output when the sketch has the thermostat's missing ';', the marker
FAKE_COMPILE_ERROR, or ``#include <MissingLib.h>``; otherwise writes text "firmware" (the sketch
source itself, so the fake wokwi-cli can model it) to ``<output-dir>/<sketch>.ino.bin|hex|elf``.
Environment: FAKE_ARDUINO_NO_ESP32=1 pretends the esp32 core isn't installed.
"""
import json
import os
import re
import sys
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"


def opt(args, name, default=None):
    if name in args:
        i = args.index(name)
        return args[i + 1] if i + 1 < len(args) else default
    return default


def compile_(args):
    fqbn = opt(args, "--fqbn", "")
    out_dir = Path(opt(args, "--output-dir", "build"))
    sketch_dir = Path(args[-1]).resolve()
    if not re.match(r"^[\w.-]+:[\w.-]+:[\w.-]+", fqbn):
        print(f"Error during build: Invalid FQBN: not an FQBN: {fqbn}", file=sys.stderr)
        return 1
    if fqbn.startswith("esp32:") and os.environ.get("FAKE_ARDUINO_NO_ESP32") == "1":
        print("Error during build: Platform 'esp32:esp32' not found: platform not installed\n"
              "Try running `arduino-cli core install esp32:esp32`", file=sys.stderr)
        return 1
    ino = sketch_dir / f"{sketch_dir.name}.ino"
    if not ino.is_file():
        print(f"Error opening sketch: main file missing from sketch: {ino}", file=sys.stderr)
        return 1
    src = ino.read_text()
    if "FAKE_COMPILE_ERROR" in src or re.search(r"const float THRESHOLD_C = [\d.]+\s*\n", src):
        text = (FIX / "gcc" / "buggy.txt").read_text()
        text = text.replace("/home/maker/.hermes/plugin-data/boardloop/projects/thermostat-buggy/thermostat-buggy.ino", str(ino))
        print(text, file=sys.stderr, end="")
        return 1
    m = re.search(r"#include <MissingLib\.h>", src)
    if m:
        line = src[:m.start()].count("\n") + 1
        print(f"{ino}:{line}:10: fatal error: MissingLib.h: No such file or directory\n"
              "compilation terminated.\nexit status 1", file=sys.stderr)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = "bin" if fqbn.startswith("esp32:") else "hex"
    payload = "FAKEFW\n" + src
    (out_dir / f"{ino.name}.{ext}").write_text(payload)
    (out_dir / f"{ino.name}.elf").write_text(payload)
    print((FIX / "gcc" / "success_esp32.txt").read_text(), end="")
    return 0


def lib(args):
    sub = args[1] if len(args) > 1 else ""
    if sub == "search":
        q = " ".join(a for a in args[2:] if not a.startswith("-") and a != "json").lower()
        data = json.loads((FIX / "arduino" / "lib_search.json").read_text())
        words = q.split()
        data["libraries"] = [l for l in data["libraries"] if all(w in l["name"].lower() for w in words)]
        print(json.dumps(data))
        return 0
    if sub == "install":
        name = args[2]
        if name.lower().startswith("nonexistent"):
            print(f"Error installing {name}: Library '{name}' not found", file=sys.stderr)
            return 1
        print(f"Downloading {name}@1.0.0...\nInstalling {name}@1.0.0...\nInstalled {name}@1.0.0")
        return 0
    if sub == "list":
        print((FIX / "arduino" / "lib_list.json").read_text())
        return 0
    return 2


def main(argv):
    if not argv:
        return 2
    cmd = argv[0]
    if cmd == "version":
        print("arduino-cli  Version: 1.3.1 Commit: fake0000 Date: 2026-01-01T00:00:00Z")
        return 0
    if cmd == "compile":
        return compile_(argv)
    if cmd == "lib":
        return lib(argv)
    if cmd == "core" and argv[1:2] == ["list"]:
        data = json.loads((FIX / "arduino" / "core_list.json").read_text())
        if os.environ.get("FAKE_ARDUINO_NO_ESP32") == "1":
            data["platforms"] = [p for p in data["platforms"] if p["id"] != "esp32:esp32"]
        print(json.dumps(data))
        return 0
    if cmd == "board" and argv[1:2] == ["list"]:
        print((FIX / "arduino" / "board_list.json").read_text())
        return 0
    if cmd == "upload":
        port = opt(argv, "-p", "")
        print(f"Connecting...\nWriting at 0x00010000... (100 %)\nHard resetting via RTS pin... ({port})")
        return 0
    print(f"Error: unknown command \"{cmd}\" for \"arduino-cli\"", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
