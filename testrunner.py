"""Run BoardLoop tests on Wokwi: one isolated run folder per test.

Each folder holds a copy of ``wokwi.toml``, the firmware it references, a ``diagram.json`` with
the test's sensor values patched in, and the generated ``scenario.yaml``. The project itself is
never modified.
"""
from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
import json
import os
import shutil
import time
import tomllib
import uuid
from dataclasses import dataclass
from pathlib import Path

from . import procs, scenario, simulator
from .projects import Project, ProjectError
from .storage import Store

RUN_MAX_AGE_S = 24 * 3600
# Network blips seen on real runs ("Error connecting to wss://wokwi.com/...: socket hang up").
TRANSIENT = ("socket hang up", "Error connecting to wss://", "ECONNRESET", "ETIMEDOUT", "EAI_AGAIN")


@dataclass
class Runner:
    wokwi_cli: list[str]
    runs_dir: Path
    store: Store
    token: str | None
    default_timeout_ms: int = 6000
    parallel: int = 1

    # ------------------------------------------------------------------------------------------
    def _env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.pop("WOKWI_CLI_TOKEN", None)
        if self.token:
            env["WOKWI_CLI_TOKEN"] = self.token
        return env

    def _run(self, argv: list[str], cwd: Path, timeout_ms: int) -> procs.ProcResult:
        # ESP32 simulation in the Wokwi cloud runs several times slower than real time (measured:
        # 9 s simulated took 40-90 s wall), so the guard is generous, but always bounded.
        return procs.run(argv, cwd=cwd, timeout=wall_timeout_s(timeout_ms), env=self._env())

    def new_run_dir(self, project: str) -> tuple[str, Path]:
        run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
        path = self.runs_dir / project / run_id
        path.mkdir(parents=True)
        return run_id, path

    # ------------------------------------------------------------------------------------------
    def stage(self, project: Project, dest: Path, diagram: dict | None = None) -> None:
        """Copy what wokwi-cli needs into ``dest`` (wokwi.toml + firmware + diagram)."""
        toml_text = (project.path / "wokwi.toml").read_text(encoding="utf-8")
        try:
            cfg = tomllib.loads(toml_text).get("wokwi", {})
        except tomllib.TOMLDecodeError as exc:
            raise ProjectError("bad_args", f"wokwi.toml is invalid: {exc}") from None
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "wokwi.toml").write_text(toml_text, encoding="utf-8")
        for key in ("firmware", "elf"):
            rel = cfg.get(key)
            if not rel:
                continue
            src = (project.path / rel).resolve()
            if project.path.resolve() not in src.parents:
                raise ProjectError("path_outside_workspace", f"wokwi.toml {key} points outside the project.")
            if not src.is_file():
                raise ProjectError("bad_args", f"Firmware {rel} not found.", "Run mcu_compile first.")
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
        (dest / "diagram.json").write_text(json.dumps(diagram or project.diagram, indent=1), encoding="utf-8")

    @staticmethod
    def patched_diagram(project: Project, sensors: dict[str, dict[str, str]]) -> dict:
        diagram = copy.deepcopy(project.diagram)
        for part in diagram.get("parts", []):
            if part.get("id") in sensors:
                attrs = dict(part.get("attrs") or {})
                attrs.update({k: str(v) for k, v in sensors[part["id"]].items()})
                part["attrs"] = attrs
        return diagram

    # ------------------------------------------------------------------------------------------
    def simulate(self, project: Project, *, timeout_ms: int, expect_text: str = "", fail_text: str = "",
                 screenshot_part: str = "", screenshot_time_ms: int = 0) -> dict:
        """One plain run (``mcu_simulate``)."""
        run_id, run_dir = self.new_run_dir(project.name)
        self.stage(project, run_dir)
        shot = run_dir / f"{screenshot_part}.png" if screenshot_part else None
        if screenshot_part and not screenshot_time_ms:
            screenshot_time_ms = max(100, timeout_ms - 200)
        argv = simulator.build_argv(
            self.wokwi_cli, run_dir, timeout_ms=timeout_ms, serial_log=run_dir / "serial.log",
            expect_text=expect_text, fail_text=fail_text or project.fail_text,
            screenshot_part=screenshot_part, screenshot_time_ms=min(screenshot_time_ms, timeout_ms),
            screenshot_file=shot)
        res = self._run(argv, run_dir, timeout_ms)
        verdict = simulator.classify(
            res.code, res.stdout, res.stderr, timeout_ms=timeout_ms, expect_text=expect_text,
            serial=_read(run_dir / "serial.log"), wall_timed_out=res.timed_out)
        self.store.record_run(project.name, "simulate", sim_ms=verdict.sim_ms, passed=verdict.passed,
                              reason=verdict.reason)
        out = {"run_id": run_id, **verdict.as_dict()}
        if verdict.error:
            out["error"] = verdict.error
        if shot is not None and shot.is_file():
            out["screenshot"] = str(shot)
        return out

    def run_test(self, project: Project, test: dict, run_dir: Path) -> dict:
        tdir = run_dir / scenario.slug(test["name"])
        self.stage(project, tdir, self.patched_diagram(project, test.get("sensors", {})))
        (tdir / "scenario.yaml").write_text(scenario.build(test, project.boot_text), encoding="utf-8")
        timeout_ms = scenario.timeout_ms(test)
        argv = simulator.build_argv(
            self.wokwi_cli, tdir, timeout_ms=timeout_ms, serial_log=tdir / "serial.log",
            fail_text=project.fail_text, scenario=tdir / "scenario.yaml")
        for attempt in (1, 2):
            res = self._run(argv, tdir, timeout_ms)
            verdict = simulator.classify(
                res.code, res.stdout, res.stderr, timeout_ms=timeout_ms,
                waits=scenario.waits(test, project.boot_text), serial=_read(tdir / "serial.log"),
                wall_timed_out=res.timed_out)
            # one automatic retry for a dropped connection: not the firmware's fault
            if not (verdict.error == "wokwi_error" and any(t in verdict.raw_reason for t in TRANSIENT)):
                break
        self.store.record_run(project.name, "test", sim_ms=verdict.sim_ms, passed=verdict.passed,
                              reason=f"{test['name']}: {verdict.reason}")
        result = {"name": test["name"], **verdict.as_dict()}
        if verdict.error:
            result["error"] = verdict.error
        shot = tdir / scenario.screenshot_name(test) if test.get("screenshot") else None
        if shot is not None and shot.is_file():
            result["screenshot"] = str(shot)
        if verdict.passed:
            result.pop("serial_tail", None)  # keep passing results small; failures keep their tail
        else:
            result["serial_tail"] = result["serial_tail"][-15:]
        return result

    def run_tests(self, project: Project, tests: list[dict]) -> dict:
        run_id, run_dir = self.new_run_dir(project.name)
        # The first test runs alone: a missing token or firmware fails it immediately, and every
        # other test would fail the same way, so nothing more is started.
        results = [self.run_test(project, tests[0], run_dir)] if tests else []
        if results and results[0].get("error") not in ("token_missing", "bad_args"):
            rest = tests[1:]
            if self.parallel > 1 and len(rest) > 1:
                # ESP32 simulation runs slower than real time in the cloud; independent tests
                # in parallel cut a verify's wall time roughly by the pool size.
                with ThreadPoolExecutor(max_workers=self.parallel) as pool:
                    results += list(pool.map(lambda t: self.run_test(project, t, run_dir), rest))
            else:
                results += [self.run_test(project, t, run_dir) for t in rest]
        passed = sum(1 for r in results if r["passed"])
        summary = {"run_id": run_id, "passed": passed, "failed": len(results) - passed,
                   "total": len(tests), "results": results}
        self.store.save_latest(project.name, "test", summary)
        return summary


def wall_timeout_s(timeout_ms: int) -> float:
    """Wall-clock limit for one wokwi-cli run: 10x the simulated time plus 90 s of startup."""
    return timeout_ms / 1000 * 10 + 90


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def cleanup_runs(runs_dir: Path, now: float | None = None) -> int:
    """Delete run folders older than 24 h, but always keep each project's newest run (its
    screenshots back the latest results). Returns the number removed."""
    now = time.time() if now is None else now
    removed = 0
    if not runs_dir.is_dir():
        return 0
    for project_dir in runs_dir.iterdir():
        if not project_dir.is_dir() or project_dir.is_symlink():
            continue
        runs = sorted((p for p in project_dir.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime)
        for run in runs[:-1]:
            if now - run.stat().st_mtime > RUN_MAX_AGE_S:
                shutil.rmtree(run, ignore_errors=True)
                removed += 1
    return removed


def firmware_is_stale(project: Project) -> bool:
    fw = project.path / project.firmware_rel
    if not fw.is_file():
        return True
    newest_src = max((p.stat().st_mtime for p in project.path.iterdir()
                      if p.suffix in (".ino", ".h", ".cpp", ".c")), default=0)
    return newest_src > fw.stat().st_mtime
