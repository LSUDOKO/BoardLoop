import json

import pytest

from boardloop import approvals, tools
from test_tools import call, env, new  # noqa: F401  (fixture reuse)


def test_hardware_tools_need_approval():
    for name in ("mcu_upload", "mcu_serial_write"):
        d = approvals.on_pre_tool_call(tool_name=name, args={"port": "COM3", "text": "hi"}, task_id="t")
        assert d["action"] == "approve" and d["rule_key"] == name and d["message"]


def test_everything_else_passes_through():
    for name, _, _ in tools.TOOLS:
        if name not in approvals.NEEDS_APPROVAL:
            assert approvals.on_pre_tool_call(tool_name=name, args={}) is None
    assert approvals.on_pre_tool_call(tool_name="terminal", args={"command": "ls"}) is None


def test_guard_every_risky_tool_is_gated():
    """Fails if someone adds a flash/write/erase tool without putting it behind approval."""
    risky = [n for n, _, _ in tools.TOOLS if any(w in n for w in ("upload", "write", "flash", "erase", "burn"))]
    assert risky and set(risky) <= approvals.NEEDS_APPROVAL


def test_no_auto_approve_path():
    import inspect
    src = inspect.getsource(approvals)
    assert '"action": "allow"' not in src and "auto_approve" not in src


def test_upload_message_warns_when_untested(env):
    new()
    call("mcu_compile", project="demo1")
    msg = approvals.describe("mcu_upload", {"project": "demo1", "port": "/dev/ttyUSB0"})
    assert '"demo1" (esp32:esp32:esp32,' in msg and "/dev/ttyUSB0" in msg and "NOT passed" in msg
    assert call("mcu_verify", project="demo1")["status"] == "verified"
    msg = approvals.describe("mcu_upload", {"project": "demo1", "port": "/dev/ttyUSB0"})
    assert "3/3 tests passed in simulation" in msg


def test_describe_never_raises_on_garbage():
    assert "could not read" in approvals.describe("mcu_upload", {"project": "../../x", "port": 5})
    assert approvals.on_pre_tool_call(tool_name="mcu_serial_write", args=None)["action"] == "approve"
