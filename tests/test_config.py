import sys
from pathlib import Path

from boardloop import config


def test_defaults(tmp_path):
    s = config.Settings.from_dict({}, tmp_path)
    assert s.workspace_dir == tmp_path / "projects"
    assert s.default_board == "esp32"
    assert (s.sim_timeout_ms, s.compile_budget, s.test_budget) == (6000, 3, 5)


def test_values_are_clamped_and_parsed(tmp_path):
    s = config.Settings.from_dict(
        {"sim_timeout_ms": "999999", "compile_budget": "0", "wokwi_minutes_limit": "200",
         "default_board": "nonsense", "workspace_dir": str(tmp_path / "ws")},
        tmp_path,
    )
    assert s.sim_timeout_ms == config.MAX_SIM_TIMEOUT_MS
    assert s.compile_budget == 1
    assert s.wokwi_minutes_limit == 200.0
    assert s.default_board == "esp32"
    assert s.workspace_dir == tmp_path / "ws"


def test_bad_numbers_fall_back(tmp_path):
    s = config.Settings.from_dict({"sim_timeout_ms": "fast"}, tmp_path)
    assert s.sim_timeout_ms == 6000


def test_resolve_tool_runs_python_scripts_with_current_interpreter(tmp_path):
    script = tmp_path / "fake.py"
    script.write_text("print('hi')")
    assert config.resolve_tool(str(script), "x") == [sys.executable, str(script)]


def test_resolve_tool_missing(tmp_path):
    assert config.resolve_tool(str(tmp_path / "nope"), "definitely-not-a-tool-xyz") is None
    assert config.resolve_tool("", "definitely-not-a-tool-xyz") is None


def test_redact_hides_tokens():
    tok = "wok_" + "a" * 40
    assert tok not in config.redact(f"bad token {tok}")
    assert config.redact("secret here", token="secret") == "wok_*** here"


def test_get_token_standalone_uses_env(monkeypatch):
    monkeypatch.setenv(config.TOKEN_ENV, "wok_testtoken123")
    assert config.get_token() == "wok_testtoken123"
    monkeypatch.delenv(config.TOKEN_ENV)
    assert config.get_token() is None


def test_host_data_dir_override(monkeypatch, tmp_path):
    monkeypatch.setenv("BOARDLOOP_DATA_DIR", str(tmp_path / "d"))
    assert config.host_data_dir() == tmp_path / "d"
    assert (tmp_path / "d").is_dir()
