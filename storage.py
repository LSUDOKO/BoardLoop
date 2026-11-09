"""Persistent state in ``plugin_db("boardloop")``: runs, attempt counters, verify results.

Takes a plain ``sqlite3.Connection`` so tests can use an in-memory database.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, project TEXT NOT NULL, kind TEXT NOT NULL,
  started_ts INTEGER NOT NULL, sim_ms INTEGER NOT NULL DEFAULT 0,
  passed INTEGER, reason TEXT);
CREATE INDEX IF NOT EXISTS runs_project_ts ON runs(project, started_ts);
CREATE TABLE IF NOT EXISTS attempts (
  project TEXT NOT NULL, stage TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (project, stage));
CREATE TABLE IF NOT EXISTS verifies (
  project TEXT NOT NULL, ts INTEGER NOT NULL, status TEXT NOT NULL, summary TEXT);
CREATE TABLE IF NOT EXISTS latest (
  project TEXT NOT NULL, kind TEXT NOT NULL, ts INTEGER NOT NULL, data TEXT NOT NULL,
  PRIMARY KEY (project, kind));
"""

RUN_KINDS = {"compile", "simulate", "test", "upload", "serial"}


class Store:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._lock = threading.Lock()
        with self._lock:
            conn.executescript(SCHEMA)
            conn.commit()

    def _write(self, sql: str, params: tuple = ()) -> None:
        with self._lock:
            self.conn.execute(sql, params)
            self.conn.commit()

    def _read(self, sql: str, params: tuple = ()) -> list[tuple]:
        with self._lock:
            return self.conn.execute(sql, params).fetchall()

    # runs -------------------------------------------------------------------------------------
    def record_run(self, project: str, kind: str, *, sim_ms: int = 0, passed: bool | None = None,
                   reason: str = "", ts: int | None = None) -> str:
        if kind not in RUN_KINDS:
            raise ValueError(f"unknown run kind {kind}")
        run_id = uuid.uuid4().hex[:12]
        self._write("INSERT INTO runs VALUES (?,?,?,?,?,?,?)",
                    (run_id, project, kind, int(ts if ts is not None else time.time()), int(sim_ms),
                     None if passed is None else int(passed), reason[:300]))
        return run_id

    def sim_ms_since(self, since_ts: int) -> int:
        row = self._read("SELECT COALESCE(SUM(sim_ms),0) FROM runs WHERE kind IN ('simulate','test') "
                         "AND started_ts > ?", (int(since_ts),))
        return int(row[0][0])

    # attempts ---------------------------------------------------------------------------------
    def attempts(self, project: str, stage: str) -> int:
        row = self._read("SELECT count FROM attempts WHERE project=? AND stage=?", (project, stage))
        return int(row[0][0]) if row else 0

    def bump_attempt(self, project: str, stage: str) -> int:
        self._write("INSERT INTO attempts VALUES (?,?,1) ON CONFLICT(project, stage) "
                    "DO UPDATE SET count = count + 1", (project, stage))
        return self.attempts(project, stage)

    def reset_attempts(self, project: str) -> None:
        self._write("DELETE FROM attempts WHERE project=?", (project,))

    # verifies ---------------------------------------------------------------------------------
    def record_verify(self, project: str, status: str, summary: str = "", ts: int | None = None) -> None:
        self._write("INSERT INTO verifies VALUES (?,?,?,?)",
                    (project, int(ts if ts is not None else time.time()), status, summary[:500]))

    def last_verify(self, project: str) -> dict | None:
        row = self._read("SELECT ts, status, summary FROM verifies WHERE project=? "
                         "ORDER BY ts DESC, rowid DESC LIMIT 1", (project,))
        if not row:
            return None
        ts, status, summary = row[0]
        return {"status": status, "summary": summary, "at": iso(ts)}

    # latest results (for /mcu and the Desktop pane) -------------------------------------------
    def save_latest(self, project: str, kind: str, data: dict) -> None:
        self._write("INSERT INTO latest VALUES (?,?,?,?) ON CONFLICT(project, kind) DO UPDATE SET "
                    "ts=excluded.ts, data=excluded.data", (project, kind, int(time.time()), json.dumps(data)))

    def latest(self, project: str, kind: str) -> dict | None:
        row = self._read("SELECT data FROM latest WHERE project=? AND kind=?", (project, kind))
        return json.loads(row[0][0]) if row else None

    # history ----------------------------------------------------------------------------------
    def history(self, project: str, limit: int = 20) -> list[dict]:
        rows = self._read(
            "SELECT started_ts, kind, passed, reason FROM runs WHERE project=? "
            "UNION ALL SELECT ts, 'verify', CASE status WHEN 'verified' THEN 1 ELSE 0 END, "
            "status || CASE WHEN summary <> '' THEN ': ' || summary ELSE '' END FROM verifies "
            "WHERE project=? ORDER BY 1 DESC LIMIT ?", (project, project, int(limit)))
        return [{"at": iso(ts), "stage": kind,
                 "result": "-" if passed is None else ("ok" if passed else "fail"), "reason": reason or ""}
                for ts, kind, passed, reason in rows]

    def projects_with_activity(self) -> list[str]:
        return [r[0] for r in self._read(
            "SELECT project FROM runs UNION SELECT project FROM verifies ORDER BY 1")]


def iso(ts: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
