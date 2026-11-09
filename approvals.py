"""``pre_tool_call`` hook: touching real hardware always goes through Hermes's approval prompt.

The hook only *escalates* (``{"action": "approve", ...}``); there is no code path that approves
on the user's behalf. Under cron or the gateway with nobody to answer, Hermes's own approval
policy applies and the call is refused, so nothing is flashed unattended.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

NEEDS_APPROVAL = frozenset({"mcu_upload", "mcu_serial_write"})


def _upload_message(args: dict) -> str:
    from . import config, projects, tools

    name = str(args.get("project", ""))[:41]
    port = str(args.get("port", ""))[:64]
    try:
        settings = tools.RUNTIME.settings()
        p = projects.load(settings.workspace_dir, name)
        fw = p.path / p.firmware_rel
        size = f"{fw.stat().st_size / 1024:.0f} KB" if fw.is_file() else "not built"
        board = args.get("fqbn") or p.fqbn
        last = tools.RUNTIME.store(settings).last_verify(p.name)
    except Exception:  # describing the action must never block the approval itself
        log.debug("could not describe upload", exc_info=True)
        return f'Flash project "{name}" to {port}. (BoardLoop could not read the project details.)'
    msg = f'Flash "{p.name}" ({board}, {size}) to {port}.'
    if last and last["status"] == "verified":
        msg += f" Tests: {last['summary'] or 'passed'} in simulation."
    else:
        msg += " ⚠ Tests have NOT passed for this build" + (f" (last verify: {last['status']})." if last else ".")
    return config.redact(msg)


def describe(tool_name: str, args: dict) -> str:
    if tool_name == "mcu_upload":
        return _upload_message(args)
    if tool_name == "mcu_test":
        return _upload_message(args) + " Then reset the board and read its serial output to run the tests."
    if tool_name == "mcu_serial_write":
        text = str(args.get("text", ""))[:200]
        return f'Send "{text}" to the board on {str(args.get("port", ""))[:64]} (serial write).'
    return f"BoardLoop wants to run {tool_name}."


def needs_approval(tool_name: str, args: dict) -> bool:
    """Hardware writes always; mcu_test only when it targets a real board (it flashes first)."""
    if tool_name in NEEDS_APPROVAL:
        return True
    return tool_name == "mcu_test" and str(args.get("target", "")).strip().lower() == "real"


def on_pre_tool_call(tool_name: str = "", args: dict | None = None, task_id: str = "", **kwargs) -> dict | None:
    """Escalate hardware-touching BoardLoop tools to the human approval gate."""
    args = args if isinstance(args, dict) else {}
    if not needs_approval(tool_name, args):
        return None
    rule = "mcu_test:real" if tool_name == "mcu_test" else tool_name
    return {"action": "approve", "message": describe(tool_name, args), "rule_key": rule}
