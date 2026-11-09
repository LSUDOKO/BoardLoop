"""Tool handlers end to end against the fake arduino-cli and wokwi-cli."""
import json
import os

import pytest

from boardloop import tools
from conftest import FAKES

TOKEN = "wok_" + "z" * 40


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("BOARDLOOP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("WOKWI_CLI_TOKEN", TOKEN)
    settings = {"arduino_cli_path": str(FAKES / "fake_arduino_cli.py"),
                "wokwi_cli_path": str(FAKES / "fake_wokwi_cli.py")}
    tools.RUNTIME.configure(lambda k, d=None: settings.get(k, d))
    tools.RUNTIME._store = None
    yield settings
    tools.RUNTIME.configure(lambda k, d=None: d)
    tools.RUNTIME._store = None


def call(_tool, **args):
    handler = dict((n, h) for n, _, h in tools.TOOLS)[_tool]
    out = handler(args, task_id="t1", session_id="s1")
    assert isinstance(out, str)
    return json.loads(out)


def new(name="demo1", template="esp32-thermostat"):
    r = call("mcu_project_new", name=name, template=template)
    assert r["ok"], r
    return r


def test_doctor_ready_with_fakes(env):
    r = call("mcu_doctor")
    names = {c["name"]: c for c in r["checks"]}
    assert names["arduino-cli"]["ok"] and names["core esp32:esp32"]["ok"] and names["wokwi-cli"]["ok"]
    assert names["WOKWI_CLI_TOKEN"]["detail"] == "set"
    assert TOKEN not in json.dumps(r)
    assert "used" in r["wokwi_minutes_30d"]


def test_doctor_names_fixes_on_a_bare_machine(env, monkeypatch):
    env.update(arduino_cli_path="/nonexistent/arduino-cli", wokwi_cli_path="/nonexistent/wokwi-cli")
    monkeypatch.delenv("WOKWI_CLI_TOKEN")
    monkeypatch.setenv("PATH", "")
    r = call("mcu_doctor")
    assert r["ready"] is False
    fixes = {c["name"]: c.get("fix", "") for c in r["checks"]}
    assert "arduino-cli" in fixes["arduino-cli"] and "wokwi" in fixes["wokwi-cli"]
    assert "wokwi.com/dashboard/ci" in fixes["WOKWI_CLI_TOKEN"]


def test_doctor_missing_core(env, monkeypatch):
    monkeypatch.setenv("FAKE_ARDUINO_NO_ESP32", "1")
    r = call("mcu_doctor")
    core = next(c for c in r["checks"] if c["name"] == "core esp32:esp32")
    assert not core["ok"] and "--additional-urls" in core["fix"]


def test_new_info_compile_test_simulate(env):
    new()
    info = call("mcu_project_info", project="demo1")
    assert len(info["parts"]) == 5 and len(info["wiring"]) == 10 and info["built"] is False
    assert call("mcu_compile", project="demo1")["ok"]
    t = call("mcu_test", project="demo1")
    assert (t["passed"], t["total"]) == (3, 3) and t["wokwi_minutes_30d"] > 0
    s = call("mcu_simulate", project="demo1", expect_text="BOOT OK", screenshot_part="oled1")
    assert s["ok"] and s["passed"]


def test_only_and_inline_tests(env):
    new()
    call("mcu_compile", project="demo1")
    r = call("mcu_test", project="demo1", only=["cool room keeps the LED off"])
    assert r["total"] == 1 and r["passed"] == 1
    inline = [{"name": "boots", "run_ms": 500, "expect_serial": ["T="]}]
    assert call("mcu_test", project="demo1", tests=inline)["passed"] == 1
    bad = call("mcu_test", project="demo1", only=["nope"])
    assert bad["error"] == "bad_args" and "Available" in bad["hint"]
    bad = call("mcu_test", project="demo1", tests=[{"name": "x", "expect_pins": [{"part": "led7", "pin": "A", "value": 1}]}])
    assert bad["error"] == "bad_args" and "led7" in bad["message"]


def test_the_demo_loop_fixes_the_buggy_sample(env):
    """The demo, minus the model: verify → fix compile → verify → fix logic → verified."""
    r = call("mcu_project_new", name="thermostat-buggy", template="demo-thermostat-buggy")
    ino = os.path.join(r["path"], "thermostat-buggy.ino")
    v = call("mcu_verify", project="thermostat-buggy", goal="make it pass its tests")
    assert v["status"] == "fix_compile" and v["attempt"] == "1/3" and v["errors"][0]["line"] == 24
    src = open(ino).read().replace("THRESHOLD_C = 30.0\n", "THRESHOLD_C = 30.0;\n")
    open(ino, "w").write(src)
    v = call("mcu_verify", project="thermostat-buggy")
    assert v["status"] == "fix_behaviour" and v["attempt"] == "1/5" and v["tests"] == "1/3 passed"
    assert {f["name"] for f in v["failures"]} == {"hot room turns the LED on", "cool room keeps the LED off"}
    open(ino, "w").write(src.replace("t < THRESHOLD_C", "t > THRESHOLD_C"))
    v = call("mcu_verify", project="thermostat-buggy")
    assert v["status"] == "verified" and v["tests"] == "3/3" and len(v["screenshots"]) == 2
    hist = tools.RUNTIME._store.history("thermostat-buggy")
    assert [h["stage"] for h in hist].count("verify") == 1


def test_verify_blocked_without_token(env, monkeypatch):
    new()
    monkeypatch.delenv("WOKWI_CLI_TOKEN")
    v = call("mcu_verify", project="demo1")
    assert v["status"] == "blocked" and v["error"] == "token_missing"


def test_libraries(env):
    new()
    r = call("mcu_libraries", action="search", name="DHT ESPx")
    assert r["results"][0]["name"] == "DHT sensor library for ESPx"
    r = call("mcu_libraries", action="install", name="ESP32Servo", project="demo1")
    assert r["ok"] and r["version"] == "1.0.0"
    assert "ESP32Servo" in call("mcu_project_info", project="demo1")["libraries"]
    assert call("mcu_libraries", action="install", name="x; rm -rf /")["error"] == "bad_args"
    assert call("mcu_libraries", action="list")["count"] == 4


def test_ports_and_upload(env):
    new()
    assert call("mcu_ports")["ports"][0] == {"port": "/dev/ttyUSB0", "protocol": "serial",
                                             "board": "ESP32 Dev Module", "fqbn": "esp32:esp32:esp32"}
    assert call("mcu_upload", project="demo1", port="/dev/ttyUSB0")["error"] == "bad_args"   # not built
    call("mcu_compile", project="demo1")
    assert call("mcu_upload", project="demo1", port="/dev/ttyUSB9")["error"] == "port_not_found"
    assert call("mcu_upload", project="demo1", port="/dev/sda")["error"] == "bad_args"
    assert call("mcu_upload", project="demo1", port="/dev/ttyUSB0")["ok"]


def test_wiring_check_and_export(env):
    new()
    r = call("mcu_wiring_check", project="demo1")
    assert r["errors"] == 0 and r["wokwi_lint"]["ok"]
    e = call("mcu_export", project="demo1")
    assert sorted(os.listdir(e["folder"])) == ["diagram.json", "libraries.txt", "sketch.ino"]


@pytest.mark.parametrize("args", [{}, {"project": "../etc"}, {"project": "Nope"}, {"project": 5}])
def test_bad_project_args_never_raise(env, args):
    r = call("mcu_compile", **args)
    assert r["ok"] is False and r["error"] in ("bad_args", "path_outside_workspace", "project_not_found")


def test_handler_survives_non_dict_args(env):
    out = json.loads(tools.mcu_doctor(None))
    assert out["ok"]


def test_internal_errors_become_json(env, monkeypatch):
    monkeypatch.setattr(tools.projects, "list_projects", lambda ws: 1 / 0)
    r = call("mcu_doctor")
    assert r["error"] == "internal" and "ZeroDivisionError" in r["message"]
