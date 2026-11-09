"""Real arduino-cli + wokwi-cli. Run: BOARDLOOP_REAL=1 pytest -m real  (uses Wokwi minutes)."""
import json
import os
import shutil

import pytest

from boardloop import tools

pytestmark = pytest.mark.real


@pytest.fixture
def real(tmp_path, monkeypatch):
    if not (shutil.which("arduino-cli") and shutil.which("wokwi-cli") and os.environ.get("WOKWI_CLI_TOKEN")):
        pytest.skip("needs arduino-cli, wokwi-cli and WOKWI_CLI_TOKEN")
    monkeypatch.setenv("BOARDLOOP_DATA_DIR", str(tmp_path / "data"))
    tools.RUNTIME.configure(lambda k, d=None: {"compile_timeout_s": 900}.get(k, d))
    tools.RUNTIME._store = None
    yield
    tools.RUNTIME._store = None


def call(_tool, **args):
    return json.loads(dict((n, h) for n, _, h in tools.TOOLS)[_tool](args))


def test_real_uno_template_verifies(real):
    assert call("mcu_project_new", name="uno1", template="uno-blink")["ok"]
    v = call("mcu_verify", project="uno1")
    assert v["status"] == "verified", v


def test_real_thermostat_template_verifies(real):
    assert call("mcu_project_new", name="thermo1", template="esp32-thermostat")["ok"]
    v = call("mcu_verify", project="thermo1")
    assert v["status"] == "verified" and v["tests"] == "3/3", v
    assert len(v["screenshots"]) == 2


def test_real_buggy_sample_compile_error_then_logic_failures(real):
    r = call("mcu_project_new", name="thermostat-buggy", template="demo-thermostat-buggy")
    v = call("mcu_verify", project="thermostat-buggy")
    assert v["status"] == "fix_compile" and v["errors"][0]["line"] == 24, v
    assert "missing a ';'" in v["errors"][0]["hint"]
    ino = os.path.join(r["path"], "thermostat-buggy.ino")
    src = open(ino).read().replace("THRESHOLD_C = 30.0\n", "THRESHOLD_C = 30.0;\n")
    open(ino, "w").write(src)
    v = call("mcu_verify", project="thermostat-buggy")
    assert v["status"] == "fix_behaviour" and v["tests"] == "1/3 passed", v
    open(ino, "w").write(src.replace("t < THRESHOLD_C", "t > THRESHOLD_C"))
    v = call("mcu_verify", project="thermostat-buggy")
    assert v["status"] == "verified", v
