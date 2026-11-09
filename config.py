"""Settings, tool discovery and the few Hermes host services BoardLoop uses.

Everything Hermes-specific (settings, secrets, the plugin data folder) is reached through this
module, behind lazy imports, so every other module stays plain Python and testable without Hermes.
"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

PLUGIN_NAME = "boardloop"
TOKEN_ENV = "WOKWI_CLI_TOKEN"

BOARD_ALIASES: dict[str, str] = {
    "esp32": "esp32:esp32:esp32",
    "esp32s3": "esp32:esp32:esp32s3",
    "esp32c3": "esp32:esp32:esp32c3",
    "uno": "arduino:avr:uno",
    "nano": "arduino:avr:nano",
    "mega": "arduino:avr:mega",
}

# Wokwi board part for each alias (used by templates and the wiring check).
WOKWI_BOARD_PARTS: dict[str, str] = {
    "esp32": "board-esp32-devkit-c-v4",
    "esp32s3": "board-esp32-s3-devkitc-1",
    "esp32c3": "board-esp32-c3-devkitm-1",
    "uno": "wokwi-arduino-uno",
    "nano": "wokwi-arduino-nano",
    "mega": "wokwi-arduino-mega",
}

ESP32_CORE_URL = "https://espressif.github.io/arduino-esp32/package_esp32_index.json"

# Hard caps that settings can lower but never raise.
MAX_SIM_TIMEOUT_MS = 20_000
MAX_COMPILE_TIMEOUT_S = 900

Getter = Callable[[str, Any], Any]


def _int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _float(value: Any, default: float, lo: float, hi: float) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


@dataclass(frozen=True)
class Settings:
    """Validated plugin settings. Build it with :meth:`from_getter`."""

    data_dir: Path
    workspace_dir: Path
    default_board: str = "esp32"
    wokwi_minutes_limit: float = 50.0
    sim_timeout_ms: int = 6000
    compile_timeout_s: int = 300
    compile_budget: int = 3
    test_budget: int = 5
    arduino_cli_path: str = ""
    wokwi_cli_path: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @classmethod
    def from_getter(cls, get: Getter, data_dir: Path) -> "Settings":
        """Read every setting through ``get(key, default)`` (``ctx.get_config`` in Hermes)."""
        data_dir = Path(data_dir)
        ws = str(get("workspace_dir", "") or "").strip()
        workspace = Path(ws).expanduser() if ws else data_dir / "projects"
        board = str(get("default_board", "esp32") or "esp32").strip().lower()
        if board not in BOARD_ALIASES:
            board = "esp32"
        return cls(
            data_dir=data_dir,
            workspace_dir=workspace,
            default_board=board,
            wokwi_minutes_limit=_float(get("wokwi_minutes_limit", 50), 50.0, 1.0, 100_000.0),
            sim_timeout_ms=_int(get("sim_timeout_ms", 6000), 6000, 1000, MAX_SIM_TIMEOUT_MS),
            compile_timeout_s=_int(get("compile_timeout_s", 300), 300, 10, MAX_COMPILE_TIMEOUT_S),
            compile_budget=_int(get("compile_budget", 3), 3, 1, 10),
            test_budget=_int(get("test_budget", 5), 5, 1, 20),
            arduino_cli_path=str(get("arduino_cli_path", "") or "").strip(),
            wokwi_cli_path=str(get("wokwi_cli_path", "") or "").strip(),
        )

    @classmethod
    def from_dict(cls, values: dict, data_dir: Path) -> "Settings":
        return cls.from_getter(lambda k, d=None: values.get(k, d), data_dir)


def resolve_tool(override: str, name: str) -> list[str] | None:
    """Return the argv prefix for an external tool, or ``None`` if it can't be found.

    ``override`` may point at an executable, or at a ``.py`` script (used for the test fakes),
    which is run with the current interpreter. Nothing is ever downloaded.
    """
    if override:
        p = Path(override).expanduser()
        if p.suffix == ".py" and p.is_file():
            return [sys.executable, str(p)]
        if p.is_file() and os.access(p, os.X_OK):
            return [str(p)]
        found = shutil.which(override)
        return [found] if found else None
    found = shutil.which(name)
    return [found] if found else None


def arduino_cli(settings: Settings) -> list[str] | None:
    return resolve_tool(settings.arduino_cli_path, "arduino-cli")


def wokwi_cli(settings: Settings) -> list[str] | None:
    return resolve_tool(settings.wokwi_cli_path, "wokwi-cli")


# --- Hermes host services (lazy, with standalone fallbacks) --------------------------------------

def host_data_dir() -> Path:
    """``<HERMES_HOME>/plugin-data/boardloop`` inside Hermes; ``$BOARDLOOP_DATA_DIR`` or
    ``~/.boardloop`` when running standalone (tests, scripts)."""
    override = os.environ.get("BOARDLOOP_DATA_DIR")
    if override:
        p = Path(override)
        p.mkdir(parents=True, exist_ok=True)
        return p
    try:
        from plugins.plugin_storage import plugin_data_dir  # type: ignore[import-not-found]

        return Path(plugin_data_dir(PLUGIN_NAME))
    except ImportError:
        p = Path.home() / ".boardloop"
        p.mkdir(parents=True, exist_ok=True)
        return p


def get_token() -> str | None:
    """The Wokwi CI token, through Hermes's secret scope. Never logged, never returned to the model.

    Outside Hermes (no ``agent.secret_scope``) it falls back to the process environment so the
    standalone test suite and scripts work.
    """
    try:
        from agent.secret_scope import get_secret  # type: ignore[import-not-found]
    except ImportError:
        value = os.environ.get(TOKEN_ENV)
        return value or None
    try:
        value = get_secret(TOKEN_ENV)
    except Exception:  # UnscopedSecretError and friends: treat as "not available"
        return None
    return value or None


def redact(text: str, token: str | None = None) -> str:
    """Remove anything that looks like a Wokwi token from text shown to the model or stored."""
    import re

    if token:
        text = text.replace(token, "wok_***")
    return re.sub(r"wok_[A-Za-z0-9_\-]{8,}", "wok_***", text)
