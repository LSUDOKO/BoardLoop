"""Turn one BoardLoop test into a Wokwi automation scenario (pure functions, no I/O).

Step order (key names verified against the wokwi-cli source, see tests/fixtures/wokwi/NOTES.md):

1. ``wait-serial`` for the project's ``boot_text``
2. one ``set-control`` per ``controls`` item
3. one ``wait-serial`` per ``expect_serial`` item, in order
4. ``delay: <run_ms>ms`` so the firmware settles
5. one ``expect-pin`` per ``expect_pins`` item
6. ``take-screenshot`` of the ``screenshot`` part

wokwi-cli exits as soon as the last step finishes, so a passing test costs only the simulated
time it needs, not the full timeout.
"""
from __future__ import annotations

import re


BOOT_ALLOWANCE_MS = 3000
PER_SERIAL_MS = 1000
SLACK_MS = 2000
MAX_TIMEOUT_MS = 20_000


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s or "test")[:48]


def screenshot_name(test: dict) -> str:
    return f"{slug(test['name'])}-{test['screenshot']}.png" if test.get("screenshot") else ""


def steps(test: dict, boot_text: str = "") -> list[dict]:
    out: list[dict] = []
    if boot_text:
        out.append({"wait-serial": boot_text})
    for c in test.get("controls", []):
        out.append({"set-control": {"part-id": c["part"], "name": c["control"], "value": c["value"]}})
    for text in test.get("expect_serial", []):
        out.append({"wait-serial": text})
    out.append({"delay": f"{int(test.get('run_ms', 2000))}ms"})
    for p in test.get("expect_pins", []):
        out.append({"expect-pin": {"part-id": p["part"], "name": p["pin"], "value": p["value"]}})
    if test.get("screenshot"):
        out.append({"take-screenshot": {"part-id": test["screenshot"], "save-to": screenshot_name(test)}})
    return out


def build(test: dict, boot_text: str = "") -> str:
    """Scenario YAML for ``test``. yaml.safe_dump quotes names with colons, quotes, etc."""
    import yaml  # lazy: lets Hermes load the plugin before its deps are installed

    doc = {"name": test["name"], "version": 1, "author": "BoardLoop", "steps": steps(test, boot_text)}
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=1000)


def timeout_ms(test: dict) -> int:
    """Simulated-time budget for one test (boot + run + per-text allowance + slack), capped."""
    t = BOOT_ALLOWANCE_MS + int(test.get("run_ms", 2000)) + PER_SERIAL_MS * len(test.get("expect_serial", [])) + SLACK_MS
    return min(t, MAX_TIMEOUT_MS)


def waits(test: dict, boot_text: str = "") -> list[str]:
    """The serial texts the scenario waits for, in order (used to explain a timeout)."""
    return ([boot_text] if boot_text else []) + list(test.get("expect_serial", []))
