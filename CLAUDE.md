# CLAUDE.md: BoardLoop (Hermes Agent plugin)

You are helping build **BoardLoop**, a Hermes Agent plugin for the Hermes Agent Plugin Hackathon.
**Hard deadline: Nov 11, 2026, 5 PM EST = Nov 12, 3:30 AM IST. Target: submitted by Nov 11, 9 PM IST.**
Time is short (about 2.5 days). Prefer working, tested, simple code over clever code.

## What BoardLoop is
BoardLoop lets Hermes **write, compile, simulate, test, flash and fix** microcontroller code
(ESP32 and Arduino) until the hardware actually works. It closes the loop that research says AI
coding needs for hardware:

```
write sketch → mcu_compile ──errors──► fix (max 3 tries)
                    │ ok
                    ▼
            mcu_test (Wokwi simulation: set sensors, check pins/serial, OLED screenshot)
                    │ fail ──► fix (max 5 tries)
                    ▼ pass
            mcu_upload to a real board (approval) → mcu_serial_read to confirm
```

Simulation uses the **Wokwi CLI** (`wokwi-cli`, cloud simulator, needs `WOKWI_CLI_TOKEN`).
Compiling and flashing use **arduino-cli**. Both are installed by the user, never bundled.

## Read these before working
- `docs/kit/03-features.md`: features, priorities (P0/P1/P2), acceptance criteria
- `docs/kit/04-architecture.md`: **source of truth** for repo layout, tool specs, project file
  format, test runner, data model, errors
- `docs/kit/05-hermes-plugin-reference.md`: Hermes plugin APIs + catalog admission rules (**must follow**)
- `docs/kit/07-wokwi-guide.md`: verified Wokwi formats and flags; items marked VERIFY
- `docs/kit/10-security-and-disclosure.md`: safety rules (**non-negotiable**)
- `docs/kit/11-testing.md`: how to test without Wokwi/arduino-cli (fakes) and with them
- `examples/`: working sample projects (thermostat, thermostat-buggy, blink-uno). Use them as
  fixtures and as templates.

## Non-negotiable rules
1. **Hermes catalog rules** (docs/kit/05): public plugin surfaces only (no monkey-patching), declared
   `provides_tools`/`provides_hooks` must equal what `register()` registers, no self-updating code,
   no binaries/.pyc/archives in the repo, secrets only via `agent.secret_scope.get_secret()`,
   never read `.env`/`auth.json` yourself, respect approvals, fail cleanly when unattended,
   disclose risky behaviour (network, subprocess, serial access, cloud upload of firmware).
2. **Tool prefix is `mcu_`** (the catalog plugin `hermes-board` already uses `board_*`). Toolset name:
   `boardloop`.
3. **Approvals:** `mcu_upload` and `mcu_serial_write` must trigger Hermes's approval prompt via the
   `pre_tool_call` hook (return `{"action": "approve", "message": ..., "rule_key": ...}`). No
   auto-approve path. Simulation never needs approval.
4. **Subprocess safety:** `subprocess.run([...], shell=False)` only; fixed argv templates; timeouts on
   everything; kill the whole process tree on timeout; never interpolate user strings into a shell.
5. **Path safety:** all project paths resolve inside the configured workspace
   (`workspace_dir` setting, default `<HERMES_HOME>/plugin-data/boardloop/projects`). Reject `..`,
   absolute paths outside it, and symlinks that escape it.
6. **Tool handlers never raise.** `def handler(args: dict, **kwargs) -> str` returning a JSON string
   with `"ok": true|false`; include short, actionable `hint`s on failure.
7. **Keep model-facing output small.** Compiler output → parsed list of at most 10 errors
   (`file:line:col: message` + 2 lines of context). Serial logs → last 60 lines. Never dump
   megabytes into the context.
8. **Standard library first.** Allowed deps: `pyyaml` (YAML project files) and `pyserial` (real
   boards). Both with floor and upper bound (e.g. `"pyyaml>=6.0,<7"`, `"pyserial>=3.5,<4"`).
   Import `serial` lazily so the plugin loads without it.
9. **Everything must be testable without network or tools.** Use the fake `wokwi-cli` and fake
   `arduino-cli` scripts in `tests/fakes/` (see docs/kit/11). Real-tool tests are marked
   `@pytest.mark.real` and skipped unless `BOARDLOOP_REAL=1`.
10. **VERIFY items:** if a doc marks something VERIFY, check it (run `--help`, read the docs URL given,
    or run the sample project) before relying on it. If you can't, implement defensively and tell
    the user.

## Commands
```bash
python -m pytest -q                              # fast tests with fakes
BOARDLOOP_REAL=1 python -m pytest -q -m real     # real arduino-cli + wokwi-cli (uses Wokwi minutes!)
hermes plugins doctor . --ci
hermes plugins validate . --install-deps
HERMES_PLUGINS_DEBUG=1 hermes plugins list

# Manual end-to-end on the sample
cd examples/thermostat
arduino-cli compile --fqbn esp32:esp32:esp32 --output-dir build .
wokwi-cli . --timeout 5000 --expect-text "BOOT OK"
```

## Conventions
- Python 3.11+, type hints, small modules, docstrings on public functions.
- Relative imports inside the plugin package.
- Every Wokwi run passes `--timeout` (default 6000 ms, max 20000) and is recorded in the usage
  meter (simulated ms) so the user can see their monthly Wokwi minutes.
- After each phase: run tests, run `hermes plugins doctor . --ci` if Hermes is installed,
  summarise changes and give the user a 3-to-5-step manual check.
- Commit after each phase with a clear message.

## Definition of done
- P0 features (docs/kit/03) work end to end on Wokwi with the thermostat sample, and the buggy sample
  is fixed by Hermes through the loop.
- `pytest` green; `hermes plugins doctor . --ci` green; `hermes plugins validate . --install-deps`
  green, warnings reviewed.
- README with install, setup, features, screenshots, the disclosure section and limitations.
- `plugin.yaml` capabilities, `requires_hermes`, version accurate.
