from boardloop import commands
from test_tools import call, env, new  # noqa: F401


def test_status_and_minutes(env):
    new()
    call("mcu_compile", project="demo1")
    call("mcu_test", project="demo1")
    out = commands.handle("")
    assert "arduino-cli   found" in out and "Wokwi token   set" in out
    assert "Wokwi minutes" in out and "0.0 /" not in out          # minutes recorded after a run
    assert "demo1" in out and "not verified yet" in out


def test_history_projects_doctor_help(env):
    new()
    call("mcu_verify", project="demo1")
    assert "verify" in commands.handle("history demo1") and "compile" in commands.handle("history demo1")
    assert "No history" in commands.handle("history ghost")
    assert "Invalid project name" in commands.handle("history ../x")
    assert "demo1" in commands.handle("projects")
    assert "✓ arduino-cli" in commands.handle("doctor")
    assert "/mcu history" in commands.handle("wat")
    assert commands.handle("history") == "Usage: /mcu history <project>"
