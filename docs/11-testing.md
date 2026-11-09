# 11: Testing

## Layers
1. **Unit tests (default `pytest`):** pure modules (scenario, compiler parser, simulator
   classification, projects, usage, loop, wiring, approvals), no network, under 10 s.
2. **Integration with fakes:** tool handlers run end to end against `tests/fakes/fake_arduino_cli.py`
   and `tests/fakes/fake_wokwi_cli.py` (set through the `arduino_cli_path` / `wokwi_cli_path`
   settings, invoked as `[sys.executable, fake_path, ...]`).
3. **Real-tool tests (`-m real`, `BOARDLOOP_REAL=1`):** compile the three examples; run thermostat
   tests on Wokwi. They use Wokwi minutes, so run them only at checkpoints.
4. **Hermes checks:** `hermes plugins doctor . --ci`, `hermes plugins validate . --install-deps`.
5. **Manual checklist** (below).

## Fake arduino-cli (`tests/fakes/fake_arduino_cli.py`)
- `version` → prints a version line.
- `compile --fqbn F --output-dir build <dir>`:
  - if the sketch contains the marker `FAKE_COMPILE_ERROR` *or* `const float THRESHOLD_C = 30.0\n`
    (missing `;`), print the real GCC error from `tests/fixtures/gcc/buggy.txt` to stderr and exit 1;
  - if it contains `#include <MissingLib.h>`, print a "No such file or directory" fatal error;
  - else create `build/<name>.ino.bin` and `.elf` (tiny text files, **never committed**), print a
    size summary like the real tool, exit 0.
- `lib search/install/list`, `board list --json`, `core list` → canned JSON from `tests/fixtures/arduino/`.

## Fake wokwi-cli (`tests/fakes/fake_wokwi_cli.py`)
Simulates the thermostat logic so tests are meaningful:
- Reads `diagram.json` (DHT22 attrs) and the sketch next to `wokwi.toml`.
- Decides LED state from the threshold and comparison in the sketch (regex for `> THRESHOLD_C` vs
  `< THRESHOLD_C`), prints `BOOT OK` then `T=.. H=.. LED=ON|OFF` lines to stdout and to
  `--serial-log-file`.
- Executes scenario steps: `wait-serial` (fail with the timeout code if the text never appears),
  `expect-pin` (compare with the computed LED state; on mismatch print the same message format
  recorded in `tests/fixtures/wokwi/expect_pin_fail.txt` and exit with that code), `take-screenshot`
  (write a 1x1 PNG).
- Honours `--expect-text`, `--fail-text`, `--timeout`, `--timeout-exit-code`.
- Exits with "token" error output if `WOKWI_CLI_TOKEN` is missing (to test `token_missing`).
Exit codes and messages **must match the real recordings** in `tests/fixtures/wokwi/`.

## Must-have unit tests
| Area | Cases |
|---|---|
| scenario.py | boot wait; controls; delay units (`3000ms`); multiple expect_serial in order; expect_pins key names; screenshot path; YAML round-trip; a weird test name (quotes, colon) is escaped safely |
| compiler.py | buggy sample → 1 error at line 24 with the semicolon hint; missing header → library suggestion; undeclared identifier; "Platform not found" → tool_missing; ≤ 10 errors; build-path prefixes stripped |
| simulator.py | pass / timeout (42) / fail-text / expect-pin failure / token error → correct classification |
| projects.py | name rules; path escape blocked (`../x`, absolute, symlink); template rename keeps folder, .ino, wokwi.toml and yaml consistent; wiring table excludes `$serialMonitor` links; unknown part id in a test → error |
| testrunner.py | sensors patch produces string attrs in the copy only (original untouched); run dirs created and cleaned; results aggregated |
| loop.py | compile fail increments the counter; 4th compile failure → needs_human; tests fail → fix_behaviour; all pass → verified and counters reset; no tests → needs_tests; reset flag |
| usage.py | 30-day window; minutes math; warning at 80% |
| approvals.py | upload/serial_write → approve dict; others → None; guard test for risky names |
| registration | the TOOLS table, register() and plugin.yaml provides_tools are identical |

## Manual checklist (real tools)
- [ ] `mcu_doctor` on a machine missing wokwi-cli → clear install command
- [ ] Wrong or missing Wokwi token → `token_missing` with a hint (not a stack trace)
- [ ] `mcu_project_new demo1 esp32-thermostat` → compiles and passes its tests
- [ ] `mcu_compile thermostat-buggy` → one error, line 24, semicolon hint
- [ ] `mcu_test thermostat` → 3/3, OLED screenshots show the right temperature
- [ ] Buggy sample through Hermes → verified within budgets; `/mcu history thermostat-buggy` shows the attempts
- [ ] Add a test that can't pass (e.g. expect `LED=BLUE`) → after 5 attempts `needs_human`, no endless loop
- [ ] `/mcu` shows the Wokwi minutes used
- [ ] Kill the network mid-simulation → clear error, Hermes continues
- [ ] (Real board) `mcu_upload` shows the approval with port and verify status; deny → nothing flashed
- [ ] (Real board) `mcu_serial_read` shows `T=… LED=…` lines
