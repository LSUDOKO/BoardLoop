import shutil
import sqlite3

import pytest

from boardloop import loop, projects, storage
from conftest import EXAMPLES

FAIL = {"ok": False, "error": "compile_failed", "errors": [{"line": 24, "message": "expected ';'"}], "error_count": 1}
OK = {"ok": True, "firmware": "build/x.bin", "flash_used": "21%"}


@pytest.fixture
def setup(tmp_path):
    shutil.copytree(EXAMPLES / "thermostat", tmp_path / "thermostat")
    p = projects.load(tmp_path, "thermostat")
    return p, storage.Store(sqlite3.connect(":memory:", check_same_thread=False))


def fake_results(passed_names, project):
    results = []
    for t in project.tests:
        if t["name"] in passed_names:
            results.append({"name": t["name"], "passed": True, "reason": "ok"})
        else:
            results.append({"name": t["name"], "passed": False, "reason": "expected led1:A = 1, got 0",
                            "serial_tail": ["T=35.0 H=50.0 LED=OFF"]})
    return {"passed": len(passed_names), "total": len(project.tests), "results": results}


def run(p, store, comp=OK, passed=None, **kw):
    passed = [t["name"] for t in p.tests] if passed is None else passed
    return loop.verify(p, store, compile_fn=lambda: comp, test_fn=lambda tests: fake_results(passed, p), **kw)


def test_compile_failures_count_then_need_human(setup):
    p, store = setup
    for n in (1, 2, 3):
        r = run(p, store, comp=FAIL)
        assert r["status"] == "fix_compile" and r["attempt"] == f"{n}/3"
    r = run(p, store, comp=FAIL)
    assert r["status"] == "needs_human" and r["stage"] == "compile"
    assert store.last_verify("thermostat")["status"] == "needs_human"


def test_behaviour_failures_then_verified_resets(setup):
    p, store = setup
    r = run(p, store, passed=[])
    assert r["status"] == "fix_behaviour" and r["attempt"] == "1/5" and len(r["failures"]) == 3
    assert "esp:26" in r["failures"][0]["suggestion"]
    r = run(p, store)
    assert r["status"] == "verified" and r["tests"] == "3/3"
    assert store.attempts("thermostat", "test") == 0
    r = run(p, store, passed=[])
    assert r["attempt"] == "1/5"


def test_behaviour_budget(setup):
    p, store = setup
    for _ in range(5):
        assert run(p, store, passed=[])["status"] == "fix_behaviour"
    r = run(p, store, passed=[])
    assert r["status"] == "needs_human" and "reset=true" in r["next"]
    assert any(h["stage"] == "compile" for h in r["history"])


def test_reset_flag(setup):
    p, store = setup
    for _ in range(3):
        run(p, store, comp=FAIL)
    assert run(p, store, comp=FAIL, reset=True)["attempt"] == "1/3"


def test_needs_tests(setup):
    p, store = setup
    p.tests = []
    r = run(p, store)
    assert r["status"] == "needs_tests" and "edge case" in r["next"]


def test_infra_errors_do_not_spend_attempts(setup):
    p, store = setup
    r = run(p, store, comp={"ok": False, "error": "tool_missing", "message": "core missing", "hint": "install"})
    assert r["status"] == "blocked" and store.attempts("thermostat", "compile") == 0
    blocked = lambda tests: {"passed": 0, "total": 3, "results": [
        {"name": "x", "passed": False, "reason": "Wokwi token missing", "error": "token_missing", "hint": "set it"}]}
    r = loop.verify(p, store, compile_fn=lambda: OK, test_fn=blocked)
    assert r["status"] == "blocked" and r["error"] == "token_missing" and store.attempts("thermostat", "test") == 0


def test_custom_budgets(setup):
    p, store = setup
    assert run(p, store, comp=FAIL, compile_budget=1)["attempt"] == "1/1"
    assert run(p, store, comp=FAIL, compile_budget=1)["status"] == "needs_human"


def test_serial_suggestion(setup):
    p, _ = setup
    s = loop.suggestion(p, {"reason": "expected serial 'LED=ON' not seen", "serial_tail": ["T=35.0 LED=OFF"]})
    assert "'LED=ON' never appeared" in s and "T=35.0 LED=OFF" in s


def test_dht_failure_suggestion(setup):
    p, _ = setup
    s = loop.suggestion(p, {"reason": "fail text seen: ERROR: DHT read failed"})
    assert "2 s" in s and "DHTesp" in s
