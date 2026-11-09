"""``/mcu`` slash command: status, projects, history, doctor."""
from __future__ import annotations

import json

from . import config, projects, tools, usage

HELP = """BoardLoop
/mcu                  status: tools, workspace, Wokwi minutes, last verify per project
/mcu projects         list projects
/mcu history <name>   recent compile/test/verify runs for a project
/mcu doctor           full environment check"""


def _status() -> str:
    settings = tools.RUNTIME.settings()
    store = tools.RUNTIME.store(settings)
    meter = usage.status(store, settings.wokwi_minutes_limit)
    a, w = config.arduino_cli(settings), config.wokwi_cli(settings)
    lines = ["BoardLoop status",
             f"  arduino-cli   {'found' if a else 'MISSING (run /mcu doctor)'}",
             f"  wokwi-cli     {'found' if w else 'MISSING (run /mcu doctor)'}",
             f"  Wokwi token   {'set' if config.get_token() else 'NOT SET'}",
             f"  workspace     {settings.workspace_dir}",
             f"  Wokwi minutes {meter['used']:.1f} / {meter['limit']:g} (last 30 days, estimate)"]
    if "warning" in meter:
        lines.append(f"  ⚠ {meter['warning']}")
    names = projects.list_projects(settings.workspace_dir)
    if names:
        lines.append("Projects")
        for n in names[:20]:
            last = store.last_verify(n)
            lines.append(f"  {n:<24} {last['status'] + ' ' + last['at'] if last else 'not verified yet'}")
    else:
        lines.append("No projects yet. Ask: \"create an ESP32 project called demo1 from the thermostat template\".")
    return "\n".join(lines)


def _projects() -> str:
    settings = tools.RUNTIME.settings()
    names = projects.list_projects(settings.workspace_dir)
    return "\n".join(["Projects in " + str(settings.workspace_dir)] + [f"  {n}" for n in names]) if names \
        else "No projects in " + str(settings.workspace_dir)


def _history(name: str) -> str:
    settings = tools.RUNTIME.settings()
    try:
        projects.validate_name(name)
    except projects.ProjectError as exc:
        return exc.message
    rows = tools.RUNTIME.store(settings).history(name, 25)
    if not rows:
        return f"No history for '{name}'."
    out = [f"History for {name} (newest first)"]
    for r in rows:
        out.append(f"  {r['at']}  {r['stage']:<8} {r['result']:<4} {r['reason'][:90]}")
    return "\n".join(out)


def _doctor() -> str:
    data = json.loads(tools.mcu_doctor({}))
    if not data.get("ok"):
        return data.get("message", "doctor failed")
    out = ["BoardLoop doctor" + (" — ready" if data["ready"] else " — needs setup")]
    for c in data["checks"]:
        mark = "✓" if c["ok"] else "✗"
        out.append(f"  {mark} {c['name']}" + (f": {c['detail']}" if c.get("detail") else ""))
        if not c["ok"] and c.get("fix"):
            out.append(f"      fix: {c['fix']}")
    m = data["wokwi_minutes_30d"]
    out.append(f"  Wokwi minutes: {m['used']:.1f} / {m['limit']:g}")
    return "\n".join(out)


def handle(raw: str = "", **kwargs) -> str:
    """Entry point for ``/mcu``. Never raises; returns the text to show."""
    parts = (raw or "").strip().split()
    try:
        if not parts or parts[0] == "status":
            return _status()
        if parts[0] == "projects":
            return _projects()
        if parts[0] == "history":
            return _history(parts[1]) if len(parts) > 1 else "Usage: /mcu history <project>"
        if parts[0] == "doctor":
            return _doctor()
        return HELP
    except Exception as exc:  # a slash command must not crash the session
        return f"BoardLoop error: {type(exc).__name__}: {exc}"
