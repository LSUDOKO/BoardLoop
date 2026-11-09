> **Original build plan (Nov 9, 2026), kept for history.** Where it differs from the code, the
> README, `docs/ARCHITECTURE.md` and `tests/fixtures/wokwi/NOTES.md` are authoritative (for
> example, the examples now use Adafruit's DHT library, and the manifest uses `python_dependencies`).

# 03: Features

Priorities: **P0 = must have** (the demo depends on it) · **P1 = should have** · **P2 = stretch**.
Build all of P0 first, then P1, and P2 only if P1 is done by Nov 11 noon IST.
Every tool's exact inputs and outputs are in `04-architecture.md`.

## P0: Simulation loop (the core)

### F1. `mcu_doctor`: environment check
Checks arduino-cli (version), installed cores (`esp32:esp32`, `arduino:avr`), required libraries,
wokwi-cli (version), whether the Wokwi token is set (never print it), workspace path, pyserial
availability, and this month's Wokwi usage. Returns a checklist with a fix hint for each missing item.
- **Accept:** on a fresh machine, every missing piece is named with the exact install command.

### F2. `mcu_project_new`: create a project from a template
Args: `name`, `template` (`esp32-blank` | `esp32-thermostat` | `uno-blink`), optional `board`.
Creates `<workspace>/<name>/` with `<name>.ino`, `diagram.json`, `wokwi.toml`, `boardloop.yaml`.
Templates come from the plugin's `templates/` folder (copies of `examples/`, renamed consistently:
sketch file, wokwi.toml paths and yaml `sketch:` all match the new name).
- **Accept:** the new project compiles and passes its template tests without edits.

### F3. `mcu_project_info`: understand a project
Returns the project config, the file list, a **parts list** (id, type, attrs) and a **wiring table**
from `diagram.json` (e.g. `dht1:SDA → esp:4`), plus the test names. The agent reads this before
editing so its code matches the wiring.
- **Accept:** for the thermostat it lists 5 parts and 10 wires (excluding the serial monitor links).

### F4. `mcu_libraries`: find and install Arduino libraries
Args: `action` (`search` | `install` | `list`), `name`. Wraps `arduino-cli lib search/install/list`.
`install` also appends the library to `boardloop.yaml` `libraries:`.
- **Accept:** `install "DHT sensor library for ESPx"` succeeds or explains why not.

### F5. `mcu_compile`: compile with readable errors
Args: `project`, optional `fqbn`, `clean`. Runs
`arduino-cli compile --fqbn <fqbn> --output-dir build <project>` with a timeout (default 300 s; the
first ESP32 build is slow). Parses GCC output into at most 10 errors: `file`, `line`, `col`,
`message`, 2 lines of source context. Detects common causes and adds hints (missing library →
"use mcu_libraries install …", `was not declared in this scope`, missing semicolon, wrong FQBN).
Returns flash/RAM usage when shown.
- **Accept:** the buggy sample returns one error at the right line with a "missing ';'" hint.

### F6. `mcu_simulate`: one Wokwi run
Args: `project`, `timeout_ms` (default 6000, max 20000), `expect_text`, `fail_text`,
`screenshot_part`, `screenshot_time_ms`. Runs `wokwi-cli` in the project folder, captures serial to a
log file, returns pass/fail, the exit reason (expected text seen / fail text seen / timeout /
error), the last 60 serial lines, and the screenshot path.
- **Accept:** the thermostat prints `BOOT OK` and returns `passed: true`.

### F7. `mcu_test`: automated behaviour tests (the star feature)
Args: `project`, optional `tests` (inline list; default: the tests in `boardloop.yaml`), optional
`only` (test names). For each test it:
1. copies the project into a temp run folder,
2. patches `diagram.json` part attrs from `sensors:` (e.g. DHT22 temperature 35),
3. generates a Wokwi scenario: wait for `boot_text`, `set-control` steps from `controls:`, `delay`
   `run_ms`, `wait-serial` for each `expect_serial`, `expect-pin` for each `expect_pins`,
   `take-screenshot` for `screenshot`,
4. runs `wokwi-cli` with `--scenario`, `--timeout`, `--fail-text`, `--serial-log-file`,
5. records pass/fail with a reason, plus the serial tail and screenshot.
Returns a results table, `passed`/`failed` counts and one-line reasons
(e.g. `"expected led1:A = 1, got 0"`).
- **Accept:** the thermostat passes 3/3; the buggy one (after fixing the compile error) fails
  "hot room" and "cool room" with clear reasons.

### F8. `mcu_verify`: the loop driver
Args: `project`, optional `goal` (the user's request in one line). Compile → if errors, return them
with `stage: "compile"` and `attempt: n/3`. If it compiles → run all tests → return
`stage: "test"`, `attempt: n/5`, failures and suggestions. When everything passes →
`status: "verified"` with a summary and screenshots. Attempt counters live per project in
plugin_db and reset when verified. When a budget is used up, return `status: "needs_human"` with a
summary of what was tried. **This is what stops endless loops and token waste.**
- **Accept:** on the buggy sample Hermes reaches `verified` within the budgets, and every attempt
  is recorded in history.

### F9. Wokwi usage meter
Every Wokwi run records the simulated ms used (from the timeout or the end of the run) in plugin_db.
`mcu_doctor` and `/mcu` show the minutes used in the last 30 days against the plan limit
(setting `wokwi_minutes_limit`, default 50). When over 80%, tool results include a warning; when
over 100%, runs still go ahead but warn (Wokwi itself enforces the real limit).
- **Accept:** after 3 test runs `/mcu` shows the minutes used.

### F10. `/mcu` slash command
`/mcu` = status (tools found, workspace, Wokwi minutes, last verify result per project) ·
`/mcu projects` · `/mcu history <project>` · `/mcu doctor`.

### F11. Bundled skill `skills/boardloop/SKILL.md`
Teaches the agent the workflow (project_info → write code → mcu_verify → fix → repeat), writing
**tests that match the user's request** (normal case, edge case, the opposite case), ESP32 wiring
rules (avoid strapping pins 0/2/5/12/15 for buttons, input-only pins 34–39, 3.3 V logic), library
picks (`DHT sensor library for ESPx` on ESP32, `Adafruit SSD1306` + `Adafruit GFX Library`),
machine-readable serial lines (`KEY=VALUE`), always printing a boot line, and asking before
flashing a real board.

### F12. Settings (`config_schema`)
`workspace_dir`, `default_board` (esp32), `wokwi_token` (secret, env `WOKWI_CLI_TOKEN`),
`wokwi_minutes_limit` (50), `sim_timeout_ms` (6000), `compile_timeout_s` (300),
`arduino_cli_path` and `wokwi_cli_path` (optional overrides).

## P1: Real hardware and safety

### F13. `mcu_ports`: list connected boards
Wraps `arduino-cli board list` (JSON); returns port, protocol, board name and FQBN if known.

### F14. `mcu_upload`: flash a real board (approval required)
Args: `project`, `port`, optional `fqbn`. Requires a successful compile. The `pre_tool_call` hook
shows: project, board, port, firmware size, and **whether the tests passed** (warn loudly if not).
Runs `arduino-cli upload -p <port> --fqbn <fqbn> --input-dir build <project>`.

### F15. `mcu_serial_read`: monitor a real board
Args: `port`, `baud` (115200), `seconds` (default 5, max 30), `until_text`. Uses pyserial, returns
the last 60 lines. Optional `expect_serial` list → pass/fail (a real-board check of the same test).

### F16. `mcu_serial_write` (approval required)
Args: `port`, `baud`, `text`. For sending commands to firmware that reads serial.

### F17. `mcu_wiring_check`: catch wiring mistakes before simulating
Runs `wokwi-cli lint` when available, plus our own rules on `diagram.json`: unknown part ids in
connections, ESP32 input-only pins (34–39) used as outputs, strapping pins used for buttons,
an OLED VCC on 5V vs 3V3 note, an LED without a resistor, parts with no GND. Returns warnings with fixes.

### F18. History
Every compile, test and verify is stored (project, stage, result, short reason, timestamp) and shown by
`/mcu history`.

## P2: Polish extras

### F19. Desktop "Workbench" pane
Read the Desktop SDK first. Shows the selected project's latest OLED screenshot, test results
table, serial tail and Wokwi minutes. Skip it if the SDK is unclear: the README screenshots matter more.

### F20. Real-board test mode
`mcu_test` with `target: "real"` and `port`: upload (approval) → read serial → check
`expect_serial` (pin checks are skipped on real boards).

### F21. Open in the browser
`mcu_export` writes a folder or zip with the sketch, `diagram.json` and `libraries.txt` and gives
step-by-step instructions to paste it into a new wokwi.com project. Gives the demo a visual circuit
view. (If built, add `mcu_export` to `provides_tools` in plugin.yaml.)

## Use cases (for README and narration)
- "Make a plant-watering alarm: soil sensor below 30% → buzzer beeps." (test dry vs wet)
- "Show the temperature on the OLED, LED on above 30°C." (the thermostat demo)
- "Fix my project, the LED never turns on." (the buggy sample)
- "Button toggles the relay; long press resets." (button controls in tests)
- Classroom: the teacher gives `boardloop.yaml` tests and students' code is checked automatically.
