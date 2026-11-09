#!/usr/bin/env python3
"""Fake wokwi-cli for tests. Exit codes and messages copy the real CLI (tests/fixtures/wokwi).

It "runs" the firmware written by fake_arduino_cli.py (the sketch source) with small behaviour
models, so tests are meaningful:

* thermostat: reads the DHT22 attrs from the diagram, applies the sketch's comparison
  (``temperature > THRESHOLD_C`` or a reversed one) and prints ``T=.. H=.. LED=ON|OFF`` each second;
* blink: LED toggles every 500 ms, holding ``btn1`` (set-control pressed=1) keeps it on;
* anything else: prints the string literals of the sketch's ``Serial.println`` calls.

Scenario steps (wait-serial, set-control, delay, expect-pin, take-screenshot) run on a simulated
clock; ``--expect-text``, ``--fail-text`` and ``--timeout`` behave like the real tool.
WOKWI_CLI_TOKEN missing → the real "Missing WOKWI_CLI_TOKEN" error; ``wok_bad`` → API Error.
"""
import json
import os
import re
import struct
import sys
import tomllib
import zlib
from pathlib import Path

import yaml


class Timeout(Exception):
    pass


class Fail(Exception):
    pass


def png_bytes(w=128, h=64):
    raw = b"".join(b"\x00" + b"\x00" * w for _ in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class Model:
    """Serial output and pin states over simulated time (ms)."""

    def __init__(self, src, diagram):
        self.src, self.diagram = src, diagram
        self.controls = []          # (t, part, name, value)
        self.boot_ms = 400
        if "THRESHOLD_C" in src and "DHTesp" in src:
            self.kind = "thermostat"
        elif "BUTTON_PIN" in src and "LED_PIN" in src:
            self.kind = "blink"
        else:
            self.kind = "generic"

    def part(self, type_):
        return next((p for p in self.diagram.get("parts", []) if p.get("type") == type_), {})

    def button_down(self, t):
        state = 0
        for ct, part, name, value in self.controls:
            if ct <= t and name == "pressed":
                state = int(value)
        return bool(state)

    def led_on(self, t):
        if self.kind == "thermostat":
            attrs = self.part("wokwi-dht22").get("attrs", {})
            temp = float(attrs.get("temperature", "24"))
            th = float(re.search(r"THRESHOLD_C = ([\d.]+)", self.src).group(1))
            m = re.search(r"data\.temperature\s*(>=|<=|>|<)\s*THRESHOLD_C", self.src)
            op = m.group(1) if m else ">"
            return {">": temp > th, "<": temp < th, ">=": temp >= th, "<=": temp <= th}[op]
        if self.kind == "blink":
            return self.button_down(t) or int((t - self.boot_ms) // 500) % 2 == 0
        return False

    def lines(self, until):
        """[(t, line)] printed up to ``until`` ms."""
        out = []
        if 'println("BOOT OK")' in self.src:
            out.append((self.boot_ms, "BOOT OK"))
        if self.kind == "thermostat":
            attrs = self.part("wokwi-dht22").get("attrs", {})
            t = self.boot_ms + 50
            while t <= until:
                led = "ON" if self.led_on(t) else "OFF"
                out.append((t, f"T={float(attrs.get('temperature', '24')):.1f} "
                               f"H={float(attrs.get('humidity', '40')):.1f} LED={led}"))
                t += 1000
        elif self.kind == "blink":
            t = self.boot_ms + 10
            while t <= until:
                if self.button_down(t):
                    out.append((t, "BUTTON=DOWN LED=ON"))
                    t += 100
                else:
                    on = int((t - self.boot_ms) // 500) % 2 == 0
                    out.append((t, "LED=ON" if on else "LED=OFF"))
                    t += 500
        else:
            body = self.src.split("void loop()", 1)
            setup_lits = re.findall(r'Serial\.println\("([^"]*)"\)', body[0])
            loop_lits = re.findall(r'Serial\.print(?:ln)?\("([^"]*)"\)', body[1]) if len(body) > 1 else []
            t = self.boot_ms
            for s in setup_lits:
                if s != "BOOT OK":
                    out.append((t, s))
            t += 10
            while loop_lits and t <= until:
                out.append((t, "".join(loop_lits) + "0"))
                t += 500
        return sorted(out, key=lambda x: x[0])

    def pin(self, part_id, pin, t):
        led = next((p for p in self.diagram.get("parts", []) if p.get("id") == part_id), {})
        if led.get("type") == "wokwi-led" and pin == "A":
            return 1 if self.led_on(t) else 0
        return 0


def opt(args, name, default=None):
    if name in args:
        i = args.index(name)
        return args[i + 1]
    return default


def main(argv):
    if argv[:1] in (["--version"], ["--help"]):
        print("Wokwi CLI v0.26.1 (fake)")
        return 0
    if argv[:1] == ["lint"]:
        print("No issues found")
        return 0
    token = os.environ.get("WOKWI_CLI_TOKEN", "")
    if not token:
        print("Error: Missing WOKWI_CLI_TOKEN environment variable. Please set it to your Wokwi token.\n"
              "Get your token at https://wokwi.com/dashboard/ci.", file=sys.stderr)
        return 1
    project = Path(argv[0]).resolve()
    timeout = int(opt(argv, "--timeout", "30000"))
    timeout_code = int(opt(argv, "--timeout-exit-code", "42"))
    expect_text, fail_text = opt(argv, "--expect-text"), opt(argv, "--fail-text")
    scenario_path = opt(argv, "--scenario")
    serial_log = opt(argv, "--serial-log-file")
    diagram_file = opt(argv, "--diagram-file", "diagram.json")
    shot_part, shot_file = opt(argv, "--screenshot-part"), opt(argv, "--screenshot-file", "screenshot.png")
    if token == "wok_bad":
        print("API Error: Unauthorized", file=sys.stderr)
        return 1
    cfg = tomllib.loads((project / "wokwi.toml").read_text())["wokwi"]
    fw = project / cfg["firmware"]
    if not fw.is_file():
        print(f"Error: firmware file not found: {fw}.\nPlease check the firmware path in your wokwi.toml "
              "configuration file.", file=sys.stderr)
        return 1
    diagram = json.loads((project / diagram_file).read_text())
    src = fw.read_text().split("\n", 1)[1]
    model = Model(src, diagram)

    printed = []
    log = []

    def emit_until(t):
        for when, line in model.lines(t):
            if (when, line) not in printed and when <= t:
                printed.append((when, line))
                sys.stdout.write(line + "\n")
                log.append(line)
                if fail_text and fail_text in line:
                    raise Fail(f'Unexpected text found: "{fail_text}"')

    def finish(code):
        if serial_log:
            Path(serial_log).write_text("\n".join(log) + ("\n" if log else ""))
        return code

    try:
        if scenario_path:
            sc = yaml.safe_load((project / scenario_path).read_text())
            name = sc["name"]
            t, cursor = 0, 0
            for step in sc["steps"]:
                (key, val), = step.items()
                if key == "wait-serial":
                    events = [e for e in model.lines(timeout) if e[0] >= cursor and val in e[1]]
                    if not events:
                        emit_until(timeout)
                        raise Timeout()
                    t = cursor = events[0][0]
                    emit_until(t)
                    cursor = t + 1
                    print(f'[{name}] Expected text matched: "{val}"')
                elif key == "delay":
                    t += int(str(val).removesuffix("ms"))
                    if t > timeout:
                        emit_until(timeout)
                        raise Timeout()
                    emit_until(t)
                elif key == "set-control":
                    model.controls.append((t, val["part-id"], val.get("name", val.get("control")), val["value"]))
                elif key == "expect-pin":
                    got = model.pin(val["part-id"], val.get("name", val.get("pin")), t)
                    print(f"[{name}] expect-pin {val['part-id']}:{val.get('name')} == {val['value']}")
                    if got != val["value"]:
                        print(f"Error: [{t * 1_000_000}ns] GPIO {val['part-id']}:{val.get('name')} "
                              f"expected to be {val['value']} but was {got}\n    at TestScenario.fail (fake)",
                              file=sys.stderr)
                        return finish(1)
                elif key == "take-screenshot":
                    (project / Path(scenario_path).parent / val["save-to"]).write_bytes(png_bytes())
                else:
                    print(f"Error: Invalid scenario step key: {key}", file=sys.stderr)
                    return finish(1)
            print(f"[{name}] Scenario completed successfully")
            return finish(0)
        if expect_text:
            hit = next((e for e in model.lines(timeout) if expect_text in e[1]), None)
            if hit:
                emit_until(hit[0])
                return finish(0)
        emit_until(timeout)
        if shot_part:
            Path(shot_file).write_bytes(png_bytes())
        raise Timeout()
    except Timeout:
        print(f"\nTimeout: simulation did not finish in {timeout}ms", file=sys.stderr)
        return finish(timeout_code)
    except Fail as exc:
        print(f"\n\nError: {exc}\nTEST FAILED.", file=sys.stderr)
        return finish(1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
