# 08: Build plan (Nov 9 evening → Nov 11, 9 PM IST)

Deadline Nov 12, 3:30 AM IST. Our target is 9 PM IST on Nov 11, leaving 6.5 hours of buffer.
Prompts for each phase are in `09-claude-code-prompts.md`.

| When (IST) | Phase | Done when |
|---|---|---|
| Nov 9, 18:00–20:00 | Setup + toolchain smoke test | Kit README Step 2 passes; Wokwi outputs saved as fixtures |
| Nov 9, 20:00–24:00 | 0 + 1: core modules + fakes | pytest green on pure logic: scenario, parser, classification, projects |
| Nov 10, 09:00–13:00 | 2: plugin skeleton + doctor, project, libraries, compile | Hermes loads the plugin; `mcu_compile` reports the buggy error |
| Nov 10, 14:00–19:00 | 3: simulate + test runner + usage meter | `mcu_test` passes 3/3 on the thermostat in real Wokwi |
| Nov 10, 20:00–24:00 | 4: verify loop, history, /mcu, skill | **Hermes fixes thermostat-buggy end to end** (the demo works) |
| Nov 11, 08:00–11:00 | 5: real board + wiring check (P1) | Flash + serial read with approval (skip if no board; do wiring check only) |
| Nov 11, 11:00–15:00 | 6: polish, README, assets, validate | `hermes plugins validate` green; README complete |
| Nov 11, 15:00–16:00 | 7: Desktop pane (P2), only if ahead | Otherwise skip |
| Nov 11, 16:00–19:00 | Demo | Rehearse twice, record, edit to < 90 s |
| Nov 11, 19:00–21:00 | 8: release + submit | PR open, X post live, form submitted |

---

## Setup (before any code)
- Install everything (docs/06), run the smoke test, and save real Wokwi outputs:
  pass, timeout, fail-text, expect-pin failure → `tests/fixtures/wokwi/*.txt` with exit codes.
- Answer the VERIFY list in docs/07 → `tests/fixtures/wokwi/NOTES.md`.
- **Checkpoint:** `arduino-cli compile` and `wokwi-cli --expect-text "BOOT OK"` both work on the
  thermostat sample.

## Phase 0: Orientation (20 min)
Claude reads the kit, checks tools, lists the files and the VERIFY answers, and confirms the plan.

## Phase 1: Core modules without Hermes (3–4 h)
`config.py`, `procs.py`, `projects.py` (yaml load/validate, templates, path safety, parts/wiring),
`scenario.py`, `compiler.py` (argv building + GCC parser + hints), `simulator.py` (argv +
classification), `usage.py`, `storage.py` (works with plain sqlite3 when Hermes isn't present),
`tests/fakes/fake_arduino_cli.py`, `tests/fakes/fake_wokwi_cli.py`, unit tests.
**Checkpoint:** `python -m pytest -q` green in under 10 s, with no network.

## Phase 2: Plugin skeleton + first tools (3–4 h)
`plugin.yaml`, `__init__.py`, `schemas.py`, `tools.py` with `mcu_doctor`, `mcu_project_new`,
`mcu_project_info`, `mcu_libraries`, `mcu_compile`; `templates/` from `examples/`; skill stub.
**Checkpoints:**
- `hermes plugins doctor . --ci` green; Hermes lists the tools.
- In Hermes: "check my BoardLoop setup" → doctor checklist.
- "Create a project called demo1 from the thermostat template and compile it" → succeeds.
- Copy `examples/thermostat-buggy` into the workspace; "compile thermostat-buggy" → 1 error at
  line 24 with the semicolon hint.

## Phase 3: Simulation + tests (4–5 h)
`mcu_simulate`, `testrunner.py`, `mcu_test`, usage meter wired in, run-dir cleanup.
**Checkpoints (real Wokwi, uses about 1–2 min of quota):**
- `mcu_simulate thermostat` → passed, `BOOT OK` in the tail.
- `mcu_test thermostat` → 3/3 passed, two OLED screenshots that look right.
- Make the buggy sample compile (add the `;` by hand), run `mcu_test` → "hot" and "cool" fail with
  clear reasons; then `git checkout` the file to restore the bug.

## Phase 4: The loop (3–4 h)
`loop.py` + `mcu_verify`, history rows, `/mcu`, the full SKILL.md.
**Checkpoint (the demo):** fresh Hermes session: *"The thermostat-buggy project is broken. Make it
pass its tests."* → Hermes calls `mcu_verify`, fixes the semicolon, verifies again, fixes the
reversed condition, verifies again → `verified`, 3/3. Then *"Now add a buzzer that beeps above
35 °C and test it"* works on a copy.

## Phase 5: Real board + wiring check (P1, 2–3 h)
`mcu_ports`, `mcu_upload` (approval), `mcu_serial_read`, `mcu_serial_write` (approval),
`mcu_wiring_check`. If you have no board: build `mcu_wiring_check`, unit-test the serial tools with
a fake port, and **leave the real-board tools out of plugin.yaml** unless they're tested on hardware
(or say "untested on hardware" in the README).

## Phase 6: Polish and compliance (3–4 h)
README (docs/12 outline), `assets/banner.png` (1200x600), 3–6 screenshots (test table, OLED,
doctor, verify), LICENSE (MIT), `.gitignore`, plugin.yaml lists exactly the registered tools,
`requires_hermes` set, version 0.1.0. Run `hermes plugins validate . --install-deps`; fix failures;
review warnings. Fresh-install test from the README.

## Phase 7: Desktop Workbench pane (P2)
Only if Phase 6 is finished by 15:00 on Nov 11. Read the SDK first. Otherwise skip.

## Phase 8: Release and submit
Push, note the 40-char SHA, tag v0.1.0, add the catalog entry in your fork of hermes-agent, open the
PR (docs/12 template), post the demo on X, submit the form, screenshot the confirmation.

## If you fall behind, cut in this order
Desktop pane → real-board tools → wiring check → `/mcu history` → libraries search (keep install).
**Never cut:** compile with parsed errors, mcu_test, mcu_verify budgets, the skill, the README
disclosures, validate green, the buggy-sample demo.
