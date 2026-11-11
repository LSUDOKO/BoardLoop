import sys
import time

import pytest

from boardloop import procs


def test_success_captures_output():
    r = procs.run([sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr)"])
    assert r.ok and r.code == 0
    assert r.stdout.strip() == "out" and r.stderr.strip() == "err"


def test_nonzero_exit():
    r = procs.run([sys.executable, "-c", "raise SystemExit(42)"])
    assert r.code == 42 and not r.ok


def test_missing_program():
    r = procs.run(["definitely-not-a-program-xyz"])
    assert r.not_found and r.code is None


def test_timeout_kills_child_tree(tmp_path):
    marker = tmp_path / "grandchild-alive"
    # parent spawns a grandchild that would write the marker after 3 s; both must die at 1 s
    code = (
        "import subprocess, sys, time;"
        f"subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(3); open(r\"{marker}\", \"w\")']);"
        "time.sleep(30)"
    )
    started = time.monotonic()
    r = procs.run([sys.executable, "-c", code], timeout=1)
    assert r.timed_out and r.code is None
    assert time.monotonic() - started < 10
    time.sleep(3.5)
    assert not marker.exists()


def test_output_is_truncated_to_tail():
    r = procs.run([sys.executable, "-c", f"print('x' * {procs.MAX_CAPTURE * 2}, end=''); print('END')"])
    assert len(r.stdout) <= procs.MAX_CAPTURE + 10
    assert r.stdout.rstrip().endswith("END")


def test_rejects_shell_strings():
    with pytest.raises(ValueError):
        procs.run("echo hi")  # type: ignore[arg-type]


ENV_DUMP = "import json, os; print(json.dumps(dict(os.environ)))"


def test_children_do_not_inherit_secrets(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    monkeypatch.setenv("WOKWI_CLI_TOKEN", "wok_secret")
    monkeypatch.setenv("ARDUINO_DIRECTORIES_DATA", "/tmp/a15")
    monkeypatch.setenv("LANG", "C.UTF-8")
    import json
    env = json.loads(procs.run([sys.executable, "-c", ENV_DUMP]).stdout)
    assert "OPENAI_API_KEY" not in env and "WOKWI_CLI_TOKEN" not in env
    assert env["ARDUINO_DIRECTORIES_DATA"] == "/tmp/a15" and env["LANG"] == "C.UTF-8"


def test_minimal_env_extra_only_where_given(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
    env = procs.minimal_env({"WOKWI_CLI_TOKEN": "wok_t"})
    assert env["WOKWI_CLI_TOKEN"] == "wok_t" and "ANTHROPIC_API_KEY" not in env
    assert "WOKWI_CLI_TOKEN" not in procs.minimal_env()
