import shutil

import pytest

from boardloop import compiler
from conftest import EXAMPLES, FIXTURES

GCC = FIXTURES / "gcc"


@pytest.fixture
def buggy(tmp_path):
    d = tmp_path / "thermostat-buggy"
    shutil.copytree(EXAMPLES / "thermostat-buggy", d)
    return d


def _fixture_for(project_dir, name):
    # the recorded paths point at another machine; re-root them on this project
    text = (GCC / name).read_text()
    return text.replace("/home/maker/.hermes/plugin-data/boardloop/projects/thermostat-buggy", str(project_dir))


def test_buggy_sample_first_error_is_the_semicolon(buggy):
    errors = compiler.parse_errors(_fixture_for(buggy, "buggy.txt"), buggy)
    first = errors[0]
    assert (first.file, first.line, first.col) == ("thermostat-buggy.ino", 24, 1)
    assert "missing a ';'" in first.hint
    assert first.context == ["22: const float THRESHOLD_C = 30.0", "24: Adafruit_SSD1306 display(128, 64, &Wire, -1);"]


def test_buggy_payload_says_fix_first_error(buggy):
    p = compiler.classify_failure(_fixture_for(buggy, "buggy.txt"), buggy)
    assert p["error"] == "compile_failed" and p["error_count"] == 3
    assert "first" in p["hint"]


def test_missing_header_suggests_library():
    errors = compiler.parse_errors((GCC / "missing_header.txt").read_text())
    assert len(errors) == 1 and errors[0].line == 16
    assert "DHT sensor library" in errors[0].hint and "times out" in errors[0].hint


def test_undeclared_with_suggestion():
    e = compiler.parse_errors((GCC / "undeclared.txt").read_text())[0]
    assert e.file == "blink.ino" and "LED_PN" in e.message and "Typo" in e.hint


def test_platform_missing_is_tool_missing():
    p = compiler.classify_failure((GCC / "platform_missing.txt").read_text(), None)
    assert p["error"] == "tool_missing"
    assert "arduino-cli core install esp32:esp32 --additional-urls" in p["hint"]


def test_invalid_fqbn():
    assert compiler.classify_failure((GCC / "invalid_fqbn.txt").read_text(), None)["error"] == "bad_args"


def test_at_most_ten_errors():
    assert len(compiler.parse_errors((GCC / "many_errors.txt").read_text())) == compiler.MAX_ERRORS


def test_duplicates_removed():
    line = "/x/a.ino:3:1: error: 'x' was not declared in this scope"
    assert len(compiler.parse_errors("\n".join([line] * 4))) == 1


def test_windows_paths():
    e = compiler.parse_errors(r"C:\Users\me\proj\proj.ino:7:2: error: expected ';' before '}' token")[0]
    assert e.line == 7 and e.file.endswith("proj.ino")


def test_unparseable_failure_returns_tail():
    p = compiler.classify_failure("something odd\nexit status 1", None)
    assert p["error_count"] == 0 and p["raw_tail"][-1] == "exit status 1"


def test_size_summary():
    s = compiler.parse_size((GCC / "success_esp32.txt").read_text())
    assert s == {"flash_bytes": 284437, "flash_used": "21%", "ram_bytes": 21272, "ram_used": "6%"}


def test_argv_is_fixed_template(tmp_path):
    argv = compiler.compile_argv(["arduino-cli"], "esp32:esp32:esp32", tmp_path, clean=True)
    assert argv == ["arduino-cli", "compile", "--fqbn", "esp32:esp32:esp32", "--output-dir",
                    str(tmp_path / "build"), "--clean", str(tmp_path)]


@pytest.mark.parametrize("header,lib", [("U8g2lib.h", "U8g2"), ("Some_Thing.h", "Some Thing")])
def test_library_guess(header, lib):
    assert compiler.library_for_header(header) == lib
