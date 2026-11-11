"""BoardLoop: Hermes writes ESP32/Arduino code, then proves it works.

Compile with arduino-cli, run behaviour tests in the Wokwi simulator, fix within bounded
attempts, and flash real boards with the user's approval.
"""
from __future__ import annotations

from pathlib import Path

__version__ = "0.2.3"

SKILL_PATH = Path(__file__).resolve().parent / "skills" / "boardloop" / "SKILL.md"
SERIAL_TOOLS = {"mcu_serial_read", "mcu_serial_write"}


def register(ctx) -> None:
    """Called once by Hermes. Registers the mcu_* tools, the approval hook, /mcu and the skill."""
    from . import approvals, commands, serialmon, tools

    tools.RUNTIME.configure(lambda key, default=None: ctx.get_config(key, default=default))
    for name, schema, handler in tools.TOOLS:
        ctx.register_tool(
            name=name, toolset="boardloop", schema=schema, handler=handler,
            check_fn=serialmon.available if name in SERIAL_TOOLS else None,
            emoji="🔌",
        )
    ctx.register_hook("pre_tool_call", approvals.on_pre_tool_call)
    ctx.register_command("mcu", commands.handle,
                         description="BoardLoop: status, projects, history <name>, doctor",
                         args_hint="[projects|history <name>|doctor]")
    ctx.register_skill("boardloop", SKILL_PATH,
                       description="Build, test and flash ESP32/Arduino projects with BoardLoop")
