"""``mcu_verify``: compile → test → verdict, with attempt budgets so the agent can't loop forever.

Budgets follow EmbedGenius (arXiv 2412.09058): up to 3 compile fixes and 5 behaviour fixes.

    compile ── fail ─► fix_compile   (attempt n/3; the 4th failure → needs_human)
       │ ok
       ▼
    tests ──── fail ─► fix_behaviour (attempt m/5; the 6th failure → needs_human)
       │ all pass
       ▼
    verified (counters reset)

Infrastructure problems (no token, Wokwi down, missing core) return ``blocked`` and don't spend
an attempt: they aren't the code's fault.
"""
from __future__ import annotations

import re
from typing import Callable

from . import wiring
from .projects import Project
from .storage import Store

INFRA_ERRORS = {"tool_missing", "token_missing", "timeout", "wokwi_error", "internal"}
SERIAL_RE = re.compile(r"expected serial '(?P<text>.*)' not seen")
PIN_RE = re.compile(r"expected (?P<part>[\w-]+):(?P<pin>[\w.+-]+) = (?P<want>\d), got (?P<got>\d)")


def suggestion(project: Project, failure: dict) -> str:
    """One concrete next step for a failed test, using the wiring when it helps."""
    reason = failure.get("reason", "")
    if m := PIN_RE.search(reason):
        endpoint = f"{m['part']}:{m['pin']}"
        pins = wiring.trace_to_board(project.diagram, endpoint)
        where = f" ({endpoint} is wired to {', '.join(pins)})" if pins else ""
        return (f"The firmware drives {endpoint} {'LOW' if m['want'] == '1' else 'HIGH'} when the test "
                f"expects {m['want']}{where}. Check the condition and the digitalWrite for that GPIO.")
    if m := SERIAL_RE.search(reason):
        tail = failure.get("serial_tail") or []
        seen = f" The firmware printed: {tail[-1]!r}." if tail else " Nothing was printed: check Serial.begin and the boot line."
        return f"'{m['text']}' never appeared on serial.{seen} Compare the logic that prints it with the test's sensor values."
    if reason.startswith("fail text seen"):
        return "The firmware printed the project's fail_text: read that line in serial_tail and fix its cause."
    if reason.startswith("timed out"):
        return "All expected lines appeared but the run didn't finish: lower run_ms or check for a hang."
    return "Read reason and serial_tail, fix the logic, then call mcu_verify again."


def verify(project: Project, store: Store, *, compile_fn: Callable[[], dict],
           test_fn: Callable[[list[dict]], dict], compile_budget: int = 3, test_budget: int = 5,
           reset: bool = False, goal: str = "") -> dict:
    """Run one verify step and return the tool payload."""
    name = project.name
    if reset:
        store.reset_attempts(name)

    comp = compile_fn()
    store.record_run(name, "compile", passed=bool(comp.get("ok")),
                     reason=comp.get("message", "ok") if not comp.get("ok") else "ok")
    if not comp.get("ok"):
        if comp.get("error") in INFRA_ERRORS:
            return {"ok": False, "status": "blocked", "stage": "compile", **_err(comp),
                    "next": "Fix the environment (see hint, mcu_doctor) and call mcu_verify again."}
        n = store.bump_attempt(name, "compile")
        if n > compile_budget:
            return _needs_human(store, name, "compile", compile_budget, comp.get("errors", [])[:3], goal)
        return {"ok": True, "status": "fix_compile", "stage": "compile", "attempt": f"{n}/{compile_budget}",
                "errors": comp.get("errors", []), "error_count": comp.get("error_count", 0),
                **({"hint": comp["hint"]} if comp.get("hint") else {}),
                "next": "Fix only the reported errors (start with the first), then call mcu_verify again."}

    if not project.tests:
        store.record_verify(name, "needs_tests", "compiles; no tests defined")
        return {"ok": True, "status": "needs_tests", "stage": "test", "compile": _size(comp),
                "next": ("It compiles, but nothing proves it works. Add tests to boardloop.yaml that "
                         "match the goal: a normal case, an edge case and the opposite case (see the "
                         "boardloop skill), then call mcu_verify again.")}

    tests = test_fn(project.tests)
    infra = next((r for r in tests["results"] if r.get("error") in INFRA_ERRORS | {"bad_args"}), None)
    if infra:
        return {"ok": False, "status": "blocked", "stage": "test", "error": infra["error"],
                "message": infra.get("reason", ""), "hint": infra.get("hint", ""),
                "next": "Fix the environment and call mcu_verify again; no attempt was used."}

    failures = [r for r in tests["results"] if not r["passed"]]
    if failures:
        m = store.bump_attempt(name, "test")
        brief = [{"name": f["name"], "reason": f["reason"], "suggestion": suggestion(project, f),
                  **({"serial_tail": f["serial_tail"]} if f.get("serial_tail") else {}),
                  **({"screenshot": f["screenshot"]} if f.get("screenshot") else {})}
                 for f in failures]
        if m > test_budget:
            return _needs_human(store, name, "test", test_budget, brief, goal)
        return {"ok": True, "status": "fix_behaviour", "stage": "test", "attempt": f"{m}/{test_budget}",
                "tests": f"{tests['passed']}/{tests['total']} passed", "failures": brief,
                "next": ("Fix the logic, rerun just these with mcu_test only=[...] while iterating, then "
                         "call mcu_verify for the final check.")}

    store.reset_attempts(name)
    summary = f"{tests['passed']}/{tests['total']} tests passed"
    store.record_verify(name, "verified", summary + (f" · goal: {goal[:120]}" if goal else ""))
    shots = [r["screenshot"] for r in tests["results"] if r.get("screenshot")]
    return {"ok": True, "status": "verified", "stage": "done", "tests": f"{tests['passed']}/{tests['total']}",
            "summary": summary, "compile": _size(comp), "screenshots": shots,
            "next": "Show the user the results and screenshots. If they have a board, offer mcu_upload."}


def _needs_human(store: Store, name: str, stage: str, budget: int, last: list, goal: str) -> dict:
    store.record_verify(name, "needs_human", f"{stage} budget of {budget} used up")
    return {"ok": True, "status": "needs_human", "stage": stage,
            "message": f"The {stage} fix budget ({budget} attempts) is used up.",
            "last_problems": last,
            "history": [h for h in store.history(name, 12) if h["stage"] in ("compile", "test", "verify")],
            "next": ("Stop editing. Explain to the user what was tried and what still fails, and ask how "
                     "to proceed. mcu_verify reset=true starts a fresh budget if they want you to continue.")}


def _err(payload: dict) -> dict:
    return {k: payload[k] for k in ("error", "message", "hint") if k in payload}


def _size(comp: dict) -> dict:
    return {k: comp[k] for k in ("firmware", "flash_used", "ram_used", "seconds") if k in comp}
