# How BoardLoop meets the judging criteria

Hackathon criteria: **usefulness, reliability, polish, creativity**, and favouring plugins that
**do more than a prompt or a skill could**. Each claim below links to the code or test that backs it.

## Check it yourself in two minutes

```bash
git clone https://github.com/LSUDOKO/BoardLoop && cd BoardLoop
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q                      # ~180 tests, no network, fake arduino-cli + wokwi-cli
.venv/bin/pytest -q -k demo_loop         # the demo: buggy sample → fix_compile → fix_behaviour → verified
hermes plugins validate . --install-deps # catalog admission check: passes, security scan "safe"
```

## More than a prompt

A prompt can only *suggest* firmware. BoardLoop **executes** it:

| Capability | Evidence |
|---|---|
| Real compiler with parsed, located errors and fix hints | [`compiler.py`](../compiler.py), [`tests/test_compiler.py`](../tests/test_compiler.py) |
| Runs firmware in a simulated circuit, changes sensor values, presses buttons, reads pin levels and screenshots the OLED | [`testrunner.py`](../testrunner.py), [`scenario.py`](../scenario.py), [`tests/test_testrunner.py`](../tests/test_testrunner.py) |
| Turns raw simulator output into one-line reasons (`expected led1:A = 1, got 0`) | [`simulator.py`](../simulator.py), real recordings in [`tests/fixtures/wokwi/`](../tests/fixtures/wokwi) |
| Keeps state across turns: attempt budgets, history, minutes meter | [`loop.py`](../loop.py), [`storage.py`](../storage.py), [`usage.py`](../usage.py) |
| Talks to real boards: list, flash (approval), read/write serial | [`tools.py`](../tools.py) `mcu_upload`, [`serialmon.py`](../serialmon.py) |

## Usefulness

- Research says AI firmware fails without hardware feedback (EmbedAgent: 55.6% best pass rate)
  and succeeds with it (EmbedGenius: 95.7%; UW study: beginners 25% → 100%). The README cites all three.
- Works with **no hardware at all** (simulation), and on real boards when you have one.
- Users: students and teachers (tests as auto-grading), makers, and engineers who want firmware
  regression tests. Boards: ESP32, ESP32-S3, ESP32-C3, Uno, Nano, Mega.
- `mcu_doctor` turns a broken setup into exact install commands ([`tests/test_tools.py::test_doctor_names_fixes_on_a_bare_machine`](../tests/test_tools.py)).

## Reliability

- **Verified against the real tools**, not assumptions: Wokwi formats read from the wokwi-cli source
  and then recorded from real runs ([`NOTES.md`](../tests/fixtures/wokwi/NOTES.md)); real-tool tests
  in [`tests/test_real.py`](../tests/test_real.py).
- **Fakes that behave like the tools** ([`tests/fakes/`](../tests/fakes)) make ~180 tests run in
  about 15 s with no network, on CI for Linux and macOS ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)).
- **Bounded everything:** subprocess timeouts with process-tree kill ([`test_procs.py`](../tests/test_procs.py)),
  attempt budgets ([`test_loop.py`](../tests/test_loop.py)), output caps, ≤20 tests per project.
- **Handlers never raise**: malformed arguments and internal errors come back as JSON with a hint
  ([`test_tools.py::test_internal_errors_become_json`](../tests/test_tools.py)).
- **Infrastructure failures don't cost attempts**: missing token or core → `blocked`, not a fix
  attempt ([`test_loop.py::test_infra_errors_do_not_spend_attempts`](../tests/test_loop.py)).
- **Exercised through Hermes itself:** [`scripts/hermes_e2e.py`](../scripts/hermes_e2e.py) loads the
  plugin with Hermes's plugin manager in a throwaway `HERMES_HOME` and drives the buggy sample to
  `verified` through `model_tools.handle_function_call`, the same path a model's tool call takes.
  It then shows that `mcu_upload` with nobody to approve it is **blocked fail-closed** by Hermes,
  with BoardLoop's approval message (*Flash "thermostat-buggy" (esp32:esp32:esp32, 2 KB) to
  /dev/ttyUSB0. Tests: 3/3 tests passed in simulation.*).
- **A real model, through real Hermes, on real Wokwi:** with BoardLoop installed from GitHub
  (`hermes plugins install LSUDOKO/BoardLoop`), one prompt (*"create thermostat-buggy from the
  demo template, it's broken, make it pass its tests"*) led the agent to fix the missing `;` and
  the reversed comparison and reach **verified 3/3**, reporting the OLED screenshots as `MEDIA:`
  lines and offering to flash only if a board is connected. Along the way a test hit a real Wokwi
  network drop (`socket hang up`). BoardLoop reported it as `blocked`, spent no fix attempt, and
  now retries such a run once by itself.
- **Catalog compliance is tested**: declared tools = registered tools = `TOOLS` table
  ([`test_registration.py`](../tests/test_registration.py)); `hermes plugins validate` passes with a
  `safe` security scan.

## Polish

- One status per `mcu_verify` with the next step spelled out; failures carry a suggestion that
  names the GPIO wired to the failing pin, found by tracing the circuit ([`wiring.py`](../wiring.py)).
- Compile errors show the error line *and* the line above it, where a missing `;` actually is.
- `/mcu` status with the Wokwi minutes meter; `/mcu history` of every attempt.
- The approval prompt says what will be flashed, and warns loudly if the tests haven't passed.
- A bundled skill teaches the workflow and test writing ([`SKILL.md`](../skills/boardloop/SKILL.md)).

## Creativity

- The agent **proves** its hardware code works: it sets a simulated DHT22 to 35 °C, checks the LED
  pin, and screenshots the OLED, by itself.
- Tests in `boardloop.yaml` become Wokwi automation scenarios automatically; each test runs in its
  own patched copy of the circuit, so the user's project is never modified.
- Wiring is checked like code: input-only pins, missing resistors, strapping-pin buttons.

## Safety (catalog rules 11–13, 17)

See [SECURITY.md](../SECURITY.md): every risk is mapped to the code and the test that covers it.
Approvals for flashing and serial writes, token only through `get_secret` and redacted everywhere,
no shell, no telemetry, no self-update, no binaries ([`scripts/check_repo.py`](../scripts/check_repo.py)).

## Honest limits

Simulation differs from real hardware, Wokwi needs a network connection and a plan, and the
real-board tools (including `mcu_test target="real"`) have been tested with fakes but not yet on
a physical board, and the Desktop pane has been tested with real React and a live backend but not
yet inside the Desktop window. See the README's
*Limitations* section.
