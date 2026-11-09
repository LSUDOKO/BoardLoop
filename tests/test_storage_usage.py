import sqlite3
import time

import pytest

from boardloop import storage, usage


@pytest.fixture
def store():
    return storage.Store(sqlite3.connect(":memory:", check_same_thread=False))


def test_attempt_counters(store):
    assert store.attempts("p", "compile") == 0
    assert store.bump_attempt("p", "compile") == 1
    assert store.bump_attempt("p", "compile") == 2
    assert store.bump_attempt("p", "test") == 1
    store.reset_attempts("p")
    assert store.attempts("p", "compile") == 0 and store.attempts("p", "test") == 0


def test_verify_and_history(store):
    store.record_run("p", "compile", passed=False, reason="1 error", ts=100)
    store.record_run("p", "test", sim_ms=4000, passed=True, reason="3/3", ts=200)
    store.record_verify("p", "verified", "3/3 tests", ts=300)
    assert store.last_verify("p")["status"] == "verified"
    h = store.history("p")
    assert [x["stage"] for x in h] == ["verify", "test", "compile"]
    assert h[2]["result"] == "fail" and h[0]["reason"] == "verified: 3/3 tests"
    assert store.history("other") == []
    assert store.projects_with_activity() == ["p"]


def test_unknown_kind_rejected(store):
    with pytest.raises(ValueError):
        store.record_run("p", "nonsense")


def test_latest_round_trip(store):
    store.save_latest("p", "test", {"passed": 1})
    store.save_latest("p", "test", {"passed": 2})
    assert store.latest("p", "test") == {"passed": 2} and store.latest("p", "x") is None


def test_minutes_window(store):
    now = time.time()
    store.record_run("p", "test", sim_ms=60_000, ts=int(now - 10))
    store.record_run("p", "simulate", sim_ms=30_000, ts=int(now - 10))
    store.record_run("p", "compile", sim_ms=999_999, ts=int(now - 10))       # not Wokwi time
    store.record_run("p", "test", sim_ms=600_000, ts=int(now - 31 * 86400))  # outside window
    assert usage.minutes_30d(store, now) == 1.5


def test_usage_warnings(store):
    now = time.time()
    assert "warning" not in usage.status(store, 50, now)
    store.record_run("p", "test", sim_ms=41 * 60_000, ts=int(now))
    assert "rerun just the failing" in usage.status(store, 50, now)["warning"]
    store.record_run("p", "test", sim_ms=10 * 60_000, ts=int(now))
    assert "over your 50-minute" in usage.status(store, 50, now)["warning"]
