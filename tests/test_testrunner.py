import json
import os
import shutil
import sqlite3
import sys
import time

import pytest

from boardloop import compiler, projects, storage, testrunner
from conftest import EXAMPLES, FAKES

ARDUINO = [sys.executable, str(FAKES / "fake_arduino_cli.py")]
WOKWI = [sys.executable, str(FAKES / "fake_wokwi_cli.py")]
TOKEN = "wok_" + "t" * 40


@pytest.fixture
def env(tmp_path):
    ws = tmp_path / "ws"
    for name in ("thermostat", "thermostat-buggy", "blink-uno"):
        shutil.copytree(EXAMPLES / name, ws / name)
    store = storage.Store(sqlite3.connect(":memory:", check_same_thread=False))
    runner = testrunner.Runner(WOKWI, tmp_path / "runs", store, TOKEN)
    return ws, runner, store


def compiled(ws, name):
    p = projects.load(ws, name)
    r = compiler.compile_project(ARDUINO, p.fqbn, p.path, firmware_rel=p.firmware_rel, timeout_s=30)
    assert r["ok"], r
    return p


def test_thermostat_passes_all_three(env):
    ws, runner, store = env
    p = compiled(ws, "thermostat")
    out = runner.run_tests(p, p.tests)
    assert (out["passed"], out["failed"], out["total"]) == (3, 0, 3), out
    assert all(os.path.isfile(r["screenshot"]) for r in out["results"][:2])
    assert "serial_tail" not in out["results"][0]          # passing results stay small
    assert store.latest("thermostat", "test")["passed"] == 3
    assert store.sim_ms_since(0) > 0


def test_sensor_patch_only_touches_the_copy(env):
    ws, runner, _ = env
    p = compiled(ws, "thermostat")
    before = (p.path / "diagram.json").read_text()
    out = runner.run_tests(p, p.tests[:1])
    assert (p.path / "diagram.json").read_text() == before
    run_dir = runner.runs_dir / "thermostat" / out["run_id"] / "hot-room-turns-the-led-on"
    patched = json.loads((run_dir / "diagram.json").read_text())
    dht = next(x for x in patched["parts"] if x["id"] == "dht1")
    assert dht["attrs"] == {"temperature": "35", "humidity": "50"}
    assert (run_dir / "scenario.yaml").is_file() and (run_dir / "build" / "thermostat.ino.bin").is_file()


def test_buggy_logic_fails_hot_and_cool_with_reasons(env):
    ws, runner, _ = env
    ino = ws / "thermostat-buggy" / "thermostat-buggy.ino"
    ino.write_text(ino.read_text().replace("= 30.0\n", "= 30.0;\n"))   # fix only the compile bug
    p = compiled(ws, "thermostat-buggy")
    out = runner.run_tests(p, p.tests)
    by = {r["name"]: r for r in out["results"]}
    assert out["passed"] == 1 and out["failed"] == 2
    assert by["hot room turns the LED on"]["reason"] == "expected serial 'LED=ON' not seen"
    assert by["cool room keeps the LED off"]["reason"] == "expected serial 'LED=OFF' not seen"
    assert any("LED=ON" in line for line in by["cool room keeps the LED off"]["serial_tail"])


def test_missing_firmware(env):
    ws, runner, _ = env
    p = projects.load(ws, "thermostat")
    with pytest.raises(projects.ProjectError) as e:
        runner.run_tests(p, p.tests)
    assert "mcu_compile" in e.value.hint


def test_token_missing_stops_early(env):
    ws, runner, _ = env
    p = compiled(ws, "thermostat")
    runner.token = None
    os.environ.pop("WOKWI_CLI_TOKEN", None)
    out = runner.run_tests(p, p.tests)
    assert len(out["results"]) == 1 and out["results"][0]["error"] == "token_missing"


def test_simulate_once(env):
    ws, runner, _ = env
    p = compiled(ws, "thermostat")
    r = runner.simulate(p, timeout_ms=4000, expect_text="BOOT OK")
    assert r["passed"] and "BOOT OK" in r["serial_tail"]
    r = runner.simulate(p, timeout_ms=3000, screenshot_part="oled1")
    assert r["passed"] and os.path.isfile(r["screenshot"])


def test_uno_button_test(env):
    ws, runner, _ = env
    p = compiled(ws, "blink-uno")
    out = runner.run_tests(p, p.tests)
    assert out["passed"] == 2, out


def test_cleanup_keeps_newest_run(tmp_path):
    runs = tmp_path / "runs" / "p"
    old = [runs / f"r{i}" for i in range(3)]
    for i, d in enumerate(old):
        d.mkdir(parents=True)
        t = time.time() - 3 * 86400 + i
        os.utime(d, (t, t))
    assert testrunner.cleanup_runs(tmp_path / "runs") == 2
    assert [d.name for d in runs.iterdir()] == ["r2"]


def test_stale_firmware(env):
    ws, _, _ = env
    p = compiled(ws, "thermostat")
    assert not testrunner.firmware_is_stale(p)
    later = time.time() + 5
    os.utime(p.path / "thermostat.ino", (later, later))
    assert testrunner.firmware_is_stale(p)


def test_parallel_matches_sequential(env):
    ws, runner, _ = env
    p = compiled(ws, "thermostat")
    runner.parallel = 3
    out = runner.run_tests(p, p.tests)
    assert [r["name"] for r in out["results"]] == [t["name"] for t in p.tests]   # order kept
    assert out["passed"] == 3


def test_transient_network_error_is_retried_once(env, monkeypatch, tmp_path):
    ws, runner, store = env
    p = compiled(ws, "thermostat")
    monkeypatch.setenv("FAKE_WOKWI_FLAKY_FILE", str(tmp_path / "flaky"))
    out = runner.run_tests(p, p.tests[:1])
    assert out["passed"] == 1, out
    assert (tmp_path / "flaky").exists()
