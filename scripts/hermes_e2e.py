#!/usr/bin/env python3
"""Smoke-test BoardLoop through Hermes's real plugin loader and tool dispatcher, no LLM.

Runs in a throwaway HERMES_HOME (your Hermes config is untouched): links this checkout in as
plugins/boardloop, enables it, then calls tools via model_tools.handle_function_call, the same
path a model's tool call takes (hooks, arg coercion, registry, signature-filtered kwargs).

    <hermes python> scripts/hermes_e2e.py /path/to/hermes-agent [--real]

Without --real it points the settings at the fake tools (no network). With --real it uses the
installed arduino-cli and wokwi-cli and WOKWI_CLI_TOKEN from the environment (uses Wokwi minutes).
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    hermes_src, real = Path(sys.argv[1]), "--real" in sys.argv
    home = Path(tempfile.mkdtemp(prefix="boardloop-hermes-"))
    (home / "plugins").mkdir()
    (home / "plugins" / "boardloop").symlink_to(ROOT)
    settings = {} if real else {
        "arduino_cli_path": str(ROOT / "tests/fakes/fake_arduino_cli.py"),
        "wokwi_cli_path": str(ROOT / "tests/fakes/fake_wokwi_cli.py")}
    import yaml  # noqa: F401  (needs the plugin deps installed in this interpreter)
    (home / "config.yaml").write_text(json.dumps(
        {"plugins": {"enabled": ["boardloop"], "entries": {"boardloop": {"settings": settings}}}}))
    if not real and not os.environ.get("WOKWI_CLI_TOKEN"):
        os.environ["WOKWI_CLI_TOKEN"] = "wok_" + "f" * 40
    os.environ["HERMES_HOME"] = str(home)
    sys.path.insert(0, str(hermes_src))

    from hermes_cli.plugins import discover_plugins, get_plugin_manager
    discover_plugins(force=True)
    from model_tools import handle_function_call

    def call(_tool, **args):
        out = json.loads(handle_function_call(_tool, args, task_id="e2e", session_id="e2e"))
        print(f"→ {_tool} {args}\n  {json.dumps(out)[:300]}")
        return out

    tools = sorted(n for n in get_plugin_manager()._plugin_tool_names if n.startswith("mcu_"))
    print(f"loaded {len(tools)} BoardLoop tools from {home}")
    assert len(tools) == 14, tools
    assert call("mcu_doctor")["ok"]
    r = call("mcu_project_new", name="thermostat-buggy", template="demo-thermostat-buggy")
    ino = Path(r["path"]) / "thermostat-buggy.ino"
    assert call("mcu_verify", project="thermostat-buggy")["status"] == "fix_compile"
    src = ino.read_text().replace("THRESHOLD_C = 30.0\n", "THRESHOLD_C = 30.0;\n")
    ino.write_text(src)
    assert call("mcu_verify", project="thermostat-buggy")["status"] == "fix_behaviour"
    ino.write_text(src.replace("t < THRESHOLD_C", "t > THRESHOLD_C"))
    v = call("mcu_verify", project="thermostat-buggy")
    assert v["status"] == "verified", v
    print("OK: Hermes dispatched the full loop to verified")
    # Nobody is here to answer the approval prompt: flashing must be refused, not hang or run.
    up = call("mcu_upload", project="thermostat-buggy", port="/dev/ttyUSB0")
    assert not up.get("ok") and "flashed" not in up, up
    print("OK: mcu_upload was not run without approval")
    return 0


if __name__ == "__main__":
    sys.exit(main())
