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
