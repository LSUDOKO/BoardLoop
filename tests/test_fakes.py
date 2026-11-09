"""The fakes must behave like the real tools, or every handler test proves nothing."""
import json
import shutil
import sys

import pytest

from boardloop import compiler, procs, scenario, simulator
from conftest import EXAMPLES, FAKES

ARDUINO = [sys.executable, str(FAKES / "fake_arduino_cli.py")]
WOKWI = [sys.executable, str(FAKES / "fake_wokwi_cli.py")]


@pytest.fixture
def proj(tmp_path):
    def make(name):
        d = tmp_path / name
        shutil.copytree(EXAMPLES / name, d)
        return d
    return make


def build(d, fqbn="esp32:esp32:esp32"):
    return compiler.compile_project(ARDUINO, fqbn, d, firmware_rel=f"build/{d.name}.ino.bin"
                                    if fqbn.startswith("esp32") else f"build/{d.name}.ino.hex", timeout_s=30)


def test_fake_compile_buggy_reports_line_24(proj):
    d = proj("thermostat-buggy")
    r = build(d)
    assert not r["ok"] and r["errors"][0]["line"] == 24


def test_fake_compile_ok(proj):
    r = build(proj("thermostat"))
    assert r["ok"] and r["flash_used"] == "21%"


def test_fake_compile_missing_core(proj, monkeypatch):
    monkeypatch.setenv("FAKE_ARDUINO_NO_ESP32", "1")
    r = build(proj("thermostat"))
    assert r["error"] == "tool_missing"


def run_sim(d, extra, env_token="wok_" + "x" * 40, timeout=5000, waits=None, expect=""):
    log = d / "serial.log"
    argv = simulator.build_argv(WOKWI, d, timeout_ms=timeout, serial_log=log, expect_text=expect, **extra)
    env = {"PATH": "", "WOKWI_CLI_TOKEN": env_token} if env_token else {"PATH": ""}
    r = procs.run(argv, cwd=d, timeout=30, env=env)
    serial = log.read_text() if log.exists() else ""
    return simulator.classify(r.code, r.stdout, r.stderr, timeout_ms=timeout, expect_text=expect,
                              waits=waits, serial=serial)


def test_fake_wokwi_expect_text(proj):
    d = proj("thermostat")
    build(d)
    r = run_sim(d, {}, expect="BOOT OK")
    assert r.passed and r.serial_tail == ["BOOT OK"]
    r = run_sim(d, {}, expect="NEVER")
    assert not r.passed and r.kind == "expectation"


def test_fake_wokwi_token_missing(proj):
    d = proj("thermostat")
    build(d)
    assert run_sim(d, {}, env_token="").error == "token_missing"


def scenario_for(d, test, boot="BOOT OK"):
    path = d / "scenario.yaml"
    path.write_text(scenario.build(test, boot))
    return path, scenario.waits(test, boot)


def hot_test():
    return {"name": "hot", "run_ms": 3000, "expect_serial": ["LED=ON"], "controls": [],
            "expect_pins": [{"part": "led1", "pin": "A", "value": 1}], "screenshot": "oled1"}


def test_fake_wokwi_scenario_pass_and_screenshot(proj):
    d = proj("thermostat")
    diagram = json.loads((d / "diagram.json").read_text())
    diagram["parts"][2]["attrs"]["temperature"] = "35"
    (d / "diagram.json").write_text(json.dumps(diagram))
    build(d)
    sc, waits = scenario_for(d, hot_test())
    r = run_sim(d, {"scenario": sc}, timeout=9000, waits=waits)
    assert r.passed, r
    assert (d / "hot-oled1.png").read_bytes().startswith(b"\x89PNG")


def test_fake_wokwi_reversed_logic_fails_pin(proj):
    d = proj("thermostat-buggy")
    ino = d / "thermostat-buggy.ino"
    ino.write_text(ino.read_text().replace("THRESHOLD_C = 30.0\n", "THRESHOLD_C = 30.0;\n"))
    diagram = json.loads((d / "diagram.json").read_text())
    diagram["parts"][2]["attrs"]["temperature"] = "35"
    (d / "diagram.json").write_text(json.dumps(diagram))
    assert build(d)["ok"]
    test = dict(hot_test(), expect_serial=[])
    sc, waits = scenario_for(d, test)
    r = run_sim(d, {"scenario": sc}, timeout=9000, waits=waits)
    assert r.reason == "expected led1:A = 1, got 0"
    sc, waits = scenario_for(d, hot_test())
    r = run_sim(d, {"scenario": sc}, timeout=9000, waits=waits)
    assert r.reason == "expected serial 'LED=ON' not seen"


def test_fake_wokwi_button_control(proj):
    d = proj("blink-uno")
    build(d, "arduino:avr:uno")
    test = {"name": "hold", "run_ms": 1500, "expect_serial": ["BUTTON=DOWN"],
            "controls": [{"part": "btn1", "control": "pressed", "value": 1}],
            "expect_pins": [{"part": "led1", "pin": "A", "value": 1}], "screenshot": ""}
    sc, waits = scenario_for(d, test)
    assert run_sim(d, {"scenario": sc}, timeout=9000, waits=waits).passed


def test_fake_wokwi_fail_text(proj):
    d = proj("blink-uno")
    build(d, "arduino:avr:uno")
    r = run_sim(d, {"fail_text": "LED=OFF"}, timeout=3000)
    assert r.kind == "fail_text" and r.reason == "fail text seen: LED=OFF"
