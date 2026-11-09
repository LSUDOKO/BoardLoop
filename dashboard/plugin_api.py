"""BoardLoop Workbench backend: read-only JSON for the Desktop pane.

Mounted by Hermes under ``/api/plugins/boardloop/`` (it runs in the gateway process). It only
reads BoardLoop's own plugin data folder: the SQLite history and the screenshots of the latest
test run. Self-contained on purpose: it is imported by file path, not as part of the package.
"""
from __future__ import annotations

import base64
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
MAX_SHOT_BYTES = 200_000
WINDOW_S = 30 * 24 * 3600


def _connect(data_dir: Path) -> sqlite3.Connection | None:
    db = data_dir / "data.db"
    if not db.is_file():
        return None
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2)


def _iso(ts: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _shot(data_dir: Path, path: str) -> str | None:
    """A data URL for a screenshot BoardLoop wrote under its runs folder; anything else is refused."""
    try:
        p = Path(path).resolve()
        runs = (data_dir / "runs").resolve()
        if runs not in p.parents or p.suffix != ".png" or not p.is_file() or p.stat().st_size > MAX_SHOT_BYTES:
            return None
        return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()
    except OSError:
        return None


def overview(data_dir: Path, workspace: Path, minutes_limit: float = 50, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    names = sorted(p.name for p in workspace.iterdir()
                   if p.is_dir() and not p.is_symlink() and (p / "boardloop.yaml").is_file()) \
        if workspace.is_dir() else []
    used, last = 0.0, {}
    conn = _connect(data_dir)
    if conn is not None:
        with conn:
            row = conn.execute("SELECT COALESCE(SUM(sim_ms),0) FROM runs WHERE kind IN ('simulate','test') "
                               "AND started_ts > ?", (int(now - WINDOW_S),)).fetchone()
            used = round(row[0] / 60_000, 2)
            for project, ts, status, summary in conn.execute(
                    "SELECT project, ts, status, summary FROM verifies v WHERE ts = "
                    "(SELECT MAX(ts) FROM verifies WHERE project = v.project)"):
                last[project] = {"status": status, "summary": summary, "at": _iso(ts)}
        conn.close()
    return {"minutes": {"used": used, "limit": minutes_limit},
            "projects": [{"name": n, "last_verify": last.get(n)} for n in names]}


def project_detail(data_dir: Path, name: str) -> dict:
    if not NAME_RE.match(name or ""):
        return {"error": "bad project name"}
    out: dict[str, Any] = {"name": name, "tests": None, "real": None, "history": []}
    conn = _connect(data_dir)
    if conn is None:
        return out
    import json

    with conn:
        for kind, key in (("test", "tests"), ("test_real", "real")):
            row = conn.execute("SELECT ts, data FROM latest WHERE project=? AND kind=?", (name, kind)).fetchone()
            if row:
                data = json.loads(row[1])
                results = []
                for r in data.get("results", [])[:20]:
                    item = {k: r.get(k) for k in ("name", "passed", "reason", "skipped") if k in r}
                    if r.get("serial_tail"):
                        item["serial_tail"] = r["serial_tail"][-8:]
                    if r.get("screenshot"):
                        item["image"] = _shot(data_dir, r["screenshot"])
                    results.append(item)
                out[key] = {"at": _iso(row[0]), "passed": data.get("passed"), "failed": data.get("failed"),
                            "total": data.get("total"), "results": results}
        rows = conn.execute(
            "SELECT started_ts, kind, passed, reason FROM runs WHERE project=? "
            "UNION ALL SELECT ts, 'verify', CASE status WHEN 'verified' THEN 1 ELSE 0 END, status FROM verifies "
            "WHERE project=? ORDER BY 1 DESC LIMIT 15", (name, name)).fetchall()
        out["history"] = [{"at": _iso(ts), "stage": kind, "ok": None if ok is None else bool(ok),
                           "reason": (reason or "")[:120]} for ts, kind, ok, reason in rows]
    conn.close()
    return out


# --- Hermes mount (FastAPI is provided by the gateway) --------------------------------------------

def _paths() -> tuple[Path, Path, float]:
    from hermes_cli.config import load_config_readonly
    from plugins.plugin_storage import plugin_data_dir

    data_dir = Path(plugin_data_dir("boardloop"))
    settings = ((load_config_readonly().get("plugins") or {}).get("entries") or {}).get("boardloop", {}) \
        .get("settings") or {}
    ws = str(settings.get("workspace_dir") or "").strip()
    try:
        limit = float(settings.get("wokwi_minutes_limit") or 50)
    except (TypeError, ValueError):
        limit = 50.0
    return data_dir, (Path(ws).expanduser() if ws else data_dir / "projects"), limit


try:
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/overview")
    async def get_overview() -> dict:
        data_dir, workspace, limit = _paths()
        return overview(data_dir, workspace, limit)

    @router.get("/project/{name}")
    async def get_project(name: str) -> dict:
        data_dir, _, _ = _paths()
        return project_detail(data_dir, name)
except ImportError:  # outside the gateway (tests): the pure functions above still work
    router = None
