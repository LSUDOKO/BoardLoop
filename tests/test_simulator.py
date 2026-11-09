import json
from pathlib import Path

import pytest

from boardloop import simulator
from conftest import FIXTURES


def fx(name):
    return json.loads((FIXTURES / "wokwi" / f"{name}.json").read_text())


def run(name, **kw):
    f = fx(name)
    return simulator.classify(f["exit_code"], f["stdout"], f["stderr"], timeout_ms=4000, **kw)


def test_expect_text_pass():
    r = run("pass_expect_text", expect_text="BOOT OK")
    assert r.passed and r.reason == "expected text seen: BOOT OK"


def test_expect_text_timeout():
    r = run("timeout", expect_text="NEVER")
    assert not r.passed and r.kind == "expectation" and "NEVER" in r.reason and r.sim_ms == 4000


def test_plain_run_to_timeout_is_a_pass():
    r = run("timeout")
    assert r.passed and "no expectation" in r.reason


def test_scenario_timeout_names_the_missing_line():
    f = fx("timeout")
    out = '[t] Expected text matched: "BOOT OK"\nT=20.0 H=45.0 LED=ON\n'
    r = simulator.classify(42, out, f["stderr"], timeout_ms=9000, waits=["BOOT OK", "LED=OFF"])
    assert r.reason == "expected serial 'LED=OFF' not seen" and r.kind == "expectation"


def test_scenario_boot_never_seen():
    r = simulator.classify(42, "garbage\n", "Timeout: x", timeout_ms=9000, waits=["BOOT OK", "LED=ON"])
    assert r.reason == "expected serial 'BOOT OK' not seen"


def test_expect_pin_failure_reason():
    r = run("expect_pin_fail", waits=["BOOT OK", "LED=OFF"])
    assert not r.passed and r.reason == "expected led1:A = 1, got 0"
    assert r.sim_ms == 4512 and "GPIO led1:A" in r.raw_reason


def test_scenario_pass():
    r = run("scenario_pass", waits=["BOOT OK", "LED=ON"])
    assert r.passed and r.kind == "passed"


def test_fail_text_shows_the_offending_line():
    r = run("fail_text")
    assert not r.passed and r.kind == "fail_text" and r.reason == "fail text seen: ERROR: OLED not found"


@pytest.mark.parametrize("name", ["token_missing", "token_rejected"])
def test_token_problems(name):
    r = run(name)
    assert r.error == "token_missing" and "wokwi.com/dashboard/ci" in r.hint


def test_firmware_missing():
    r = run("firmware_missing")
    assert r.error == "bad_args" and "mcu_compile" in r.hint


def test_wall_clock_timeout():
    r = simulator.classify(None, "", "", timeout_ms=6000, wall_timed_out=True)
    assert r.error == "timeout"


def test_unknown_error_uses_last_line():
    r = simulator.classify(1, "", "boom one\nboom two\n    at x (y)\n", timeout_ms=1)
    assert r.error == "wokwi_error" and r.reason == "boom two"


def test_ansi_stripped_and_tail_capped():
    serial = "\n".join(f"\x1b[32mline {i}\x1b[0m" for i in range(100))
    r = simulator.classify(0, "", "", timeout_ms=1, serial=serial)
    assert len(r.serial_tail) == simulator.SERIAL_TAIL and r.serial_tail[-1] == "line 99"


def test_argv(tmp_path):
    argv = simulator.build_argv(["wokwi-cli"], tmp_path, timeout_ms=6000, serial_log=tmp_path / "s.log",
                                expect_text="BOOT OK", fail_text="ERROR:", scenario=tmp_path / "sc.yaml",
                                diagram_file="diagram.run.json")
    assert argv[:2] == ["wokwi-cli", str(tmp_path)]
    for flag in ("--timeout", "--timeout-exit-code", "--serial-log-file", "--quiet", "--expect-text",
                 "--fail-text", "--scenario", "--diagram-file"):
        assert flag in argv
    assert argv[argv.index("--timeout") + 1] == "6000"


def test_argv_screenshot(tmp_path):
    argv = simulator.build_argv(["w"], tmp_path, timeout_ms=5000, serial_log=tmp_path / "s",
                                screenshot_part="oled1", screenshot_file=tmp_path / "o.png")
    assert argv[argv.index("--screenshot-time") + 1] == "5000"


# --- recorded from the real wokwi-cli 0.29.1 (tests/fixtures/wokwi/real_*.json) -------------------

def test_real_expect_pin_fail():
    r = run("real_expect_pin_fail", waits=["BOOT OK", "LED=OFF"])
    assert r.reason == "expected led1:A = 1, got 0" and r.sim_ms == 600


def test_real_button_scenario_pass():
    assert run("real_button_pass", waits=["BOOT OK", "BUTTON=DOWN"]).passed


def test_real_timeout_and_fail_text_and_token():
    assert run("real_timeout", expect_text="NEVER").reason == "expected text never appeared: NEVER"
    assert run("real_fail_text").reason == "fail text seen: LED=OFF"
    assert run("real_token_missing").error == "token_missing"


def test_glued_lines_after_wait_serial_are_split():
    log = "rst:0x1\nBOOT OKERROR: DHT TIMEOUT\nT=35.0 H=50.0 LED=ONT=35.0 H=50.0 LED=ON\n"
    tail = simulator.serial_tail(log, waits=["BOOT OK", "LED=ON"])
    assert tail == ["rst:0x1", "BOOT OK", "ERROR: DHT TIMEOUT", "T=35.0 H=50.0 LED=ON", "T=35.0 H=50.0 LED=ON"]
    r = simulator.classify(1, "", 'Error: Unexpected text found: "ERROR:"', timeout_ms=1,
                           serial=log, waits=["BOOT OK", "LED=ON"])
    assert r.reason == "fail text seen: ERROR: DHT TIMEOUT"
