"""Circuit helpers over diagram.json: net tracing and wiring checks."""
from __future__ import annotations

import re
from collections import defaultdict

from .projects import connections

BOARD_TYPES = ("board-", "wokwi-arduino-", "wokwi-esp32", "wokwi-pi-pico")
PASSIVE_2PIN = {"wokwi-resistor": ("1", "2")}


def _board_ids(diagram: dict) -> set[str]:
    return {p["id"] for p in diagram.get("parts", [])
            if isinstance(p, dict) and str(p.get("type", "")).startswith(BOARD_TYPES)}


def _graph(diagram: dict) -> dict[str, set[str]]:
    g: dict[str, set[str]] = defaultdict(set)
    for a, b in connections(diagram):
        g[a].add(b)
        g[b].add(a)
    # a 2-pin passive (resistor) joins its two ends for tracing purposes
    for p in diagram.get("parts", []):
        pins = PASSIVE_2PIN.get(p.get("type"))
        if pins:
            x, y = f"{p['id']}:{pins[0]}", f"{p['id']}:{pins[1]}"
            g[x].add(y)
            g[y].add(x)
    return g


def trace_to_board(diagram: dict, endpoint: str) -> list[str]:
    """Board pins reachable from ``endpoint`` (e.g. ``led1:A`` → ``['esp:26']``), through wires
    and resistors."""
    boards = _board_ids(diagram)
    g = _graph(diagram)
    seen, stack, found = {endpoint}, [endpoint], []
    while stack:
        node = stack.pop()
        for nxt in g.get(node, ()):
            if nxt in seen:
                continue
            seen.add(nxt)
            if nxt.split(":", 1)[0] in boards:
                found.append(nxt)
            else:
                stack.append(nxt)
    return sorted(found)


def gpio_number(board_pin: str) -> int | None:
    pin = board_pin.split(":", 1)[1] if ":" in board_pin else board_pin
    m = re.fullmatch(r"(?:GPIO|D)?(\d{1,2})", pin)
    return int(m.group(1)) if m else None


ESP32_INPUT_ONLY = set(range(34, 40))
ESP32_STRAPPING = {0, 2, 5, 12, 15}
OUTPUT_PINS = {"wokwi-led": "A", "wokwi-buzzer": "2", "wokwi-relay-module": "IN"}
GROUNDED_TYPES = {"wokwi-led", "board-ssd1306", "wokwi-dht22", "wokwi-buzzer", "wokwi-relay-module",
                  "wokwi-servo", "wokwi-hc-sr04", "wokwi-lcd1602", "wokwi-potentiometer"}


def _is_esp32(diagram: dict, board_id: str) -> bool:
    part = next((p for p in diagram.get("parts", []) if p.get("id") == board_id), {})
    return "esp32" in str(part.get("type", ""))


def check(diagram: dict) -> list[dict]:
    """Wiring warnings: ``{rule, level, detail, fix}``. Pure function over diagram.json."""
    warnings: list[dict] = []
    parts = {p.get("id"): p for p in diagram.get("parts", []) if isinstance(p, dict)}
    boards = _board_ids(diagram)

    def warn(rule, detail, fix, level="warning"):
        warnings.append({"rule": rule, "level": level, "detail": detail, "fix": fix})

    for a, b in connections(diagram):
        for end in (a, b):
            pid = end.split(":", 1)[0]
            if pid not in parts:
                warn("unknown_part", f"connection {a} → {b} uses unknown part '{pid}'",
                     "Fix the part id or add the part to diagram.json.", "error")

    for pid, part in parts.items():
        ptype = part.get("type")
        out_pin = OUTPUT_PINS.get(ptype)
        if out_pin:
            for bp in trace_to_board(diagram, f"{pid}:{out_pin}"):
                n = gpio_number(bp)
                if n in ESP32_INPUT_ONLY and _is_esp32(diagram, bp.split(":")[0]):
                    warn("input_only_pin", f"{bp} drives {pid}:{out_pin}; GPIO34-39 are input-only on the ESP32",
                         "Move it to an output-capable pin such as GPIO 26 or 27.", "error")
        if ptype == "wokwi-led":
            for pin in ("A", "C"):
                direct = [b for x, b in _direct(diagram, f"{pid}:{pin}") if b.split(":")[0] in boards]
                if pin == "A" and any(gpio_number(d) is not None for d in direct):
                    warn("led_without_resistor", f"{pid}:A is wired straight to {direct[0]}",
                         "Put a 220 Ω wokwi-resistor between the GPIO and the LED anode.")
        if ptype == "wokwi-pushbutton":
            for pin in ("1.l", "1.r", "2.l", "2.r"):
                for bp in trace_to_board(diagram, f"{pid}:{pin}"):
                    n = gpio_number(bp)
                    if n in ESP32_STRAPPING and _is_esp32(diagram, bp.split(":")[0]):
                        warn("strapping_pin_button", f"{pid} is on {bp}, an ESP32 strapping pin",
                             "Strapping pins change how the chip boots; use GPIO 13, 14, 27 or 32.")
        if ptype in GROUNDED_TYPES and any(e.split(":")[0] == pid for c in connections(diagram) for e in c):
            reach = [bp for pin in _part_pins(diagram, pid) for bp in trace_to_board(diagram, pin)]
            if not any(bp.split(":", 1)[1].upper().startswith("GND") for bp in reach):
                warn("no_ground", f"{pid} ({ptype}) has no connection to GND",
                     f"Wire {pid}'s GND (or an LED's C) to a board GND pin.")
        if ptype == "board-ssd1306":
            for bp in trace_to_board(diagram, f"{pid}:VCC"):
                if bp.endswith(":5V"):
                    warn("oled_vcc_5v", f"{pid}:VCC is on {bp}",
                         "Fine in Wokwi and for most OLED modules; bare 3.3 V panels need 3V3.", "info")
    return warnings


def _direct(diagram: dict, endpoint: str) -> list[tuple[str, str]]:
    out = []
    for a, b in connections(diagram):
        if a == endpoint:
            out.append((a, b))
        elif b == endpoint:
            out.append((b, a))
    return out


def _part_pins(diagram: dict, pid: str) -> set[str]:
    return {e for c in connections(diagram) for e in c if e.split(":", 1)[0] == pid}
