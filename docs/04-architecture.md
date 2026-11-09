# 04: Architecture (source of truth)

```
Hermes Agent ── boardloop plugin ───────────────────────────────────────────────────────────
  tools (mcu_*) ─► projects.py ─► <workspace>/<project>/{sketch.ino, diagram.json, wokwi.toml, boardloop.yaml, build/}
                ─► compiler.py ─► arduino-cli compile / upload / lib / board list   (local subprocess)
                ─► simulator.py ─► wokwi-cli <run-dir> --scenario … (uploads firmware to Wokwi cloud)
                ─► testrunner.py: boardloop.yaml tests → patched diagram + generated scenario per test
                ─► loop.py: mcu_verify attempt budgets
                ─► serialmon.py ─► pyserial (real boards)
  pre_tool_call hook ─► approvals.py (mcu_upload, mcu_serial_write)
  storage.py ─► plugin_db("boardloop"): runs, attempts, history
  /mcu command, skills/boardloop/SKILL.md, (P2) desktop/ pane
```

Principles: **small model-facing output**, **everything bounded** (timeouts, budgets, list
lengths), **pure-Python logic separated from subprocess calls** so it can be unit-tested with fakes.

## Repository layout (repo root = plugin root)
```
boardloop/
├── plugin.yaml
├── __init__.py            # register(ctx)
├── schemas.py             # JSON schemas for every tool
├── tools.py               # thin handlers: validate args → call modules → JSON string
├── config.py              # settings, tool paths, workspace resolution
├── procs.py               # run(argv, cwd, timeout, env) with process-group kill; returns code/stdout/stderr
├── projects.py            # load/save boardloop.yaml, templates, path safety, parts/wiring table
├── compiler.py            # arduino-cli wrapper + GCC error parser + hints
├── simulator.py           # wokwi-cli wrapper (single run) + result classification
├── testrunner.py          # tests → run dirs → scenarios → results
├── scenario.py            # pure function: test dict → scenario YAML text
├── wiring.py              # diagram.json checks (P1)
├── loop.py                # mcu_verify state machine + budgets
├── serialmon.py           # pyserial read/write (lazy import)
├── usage.py               # Wokwi minutes meter
├── storage.py             # plugin_db tables
├── approvals.py           # pre_tool_call
├── commands.py            # /mcu
├── templates/             # esp32-blank, esp32-thermostat, uno-blink (from examples/)
├── skills/boardloop/SKILL.md
├── desktop/               # P2 only
├── examples/              # thermostat, thermostat-buggy, blink-uno (kept for users and tests)
├── tests/
│   ├── fakes/fake_arduino_cli.py, fake_wokwi_cli.py
│   ├── fixtures/          # gcc error samples, wokwi outputs, diagrams
│   └── test_*.py
├── assets/                # banner.png 1200x600, screenshots
├── README.md
└── LICENSE
```
`.gitignore`: `build/`, `__pycache__/`, `*.pyc`, `.env`, `screenshots/`, `*.db`, `.boardloop-runs/`.

## Project file: `boardloop.yaml`
```yaml
name: thermostat                 # must match the folder and the sketch file name (arduino-cli rule)
board: esp32                     # alias; see BOARD_ALIASES
fqbn: esp32:esp32:esp32          # optional; overrides the alias
sketch: thermostat.ino
libraries: ["Adafruit SSD1306", "Adafruit GFX Library", "DHT sensor library for ESPx"]
boot_text: "BOOT OK"             # optional; every test waits for it first
fail_text: "ERROR:"              # optional; any run printing it fails
tests:
  - name: hot room turns the LED on
    sensors:                     # diagram.json attrs to set before the run (values become strings)
      dht1: { temperature: 35, humidity: 50 }
    controls:                    # optional Wokwi set-control steps, applied after boot_text
      - { part: btn1, control: pressed, value: 1 }
    run_ms: 3000                 # simulated time to wait after boot (and after controls)
    expect_serial: ["LED=ON"]    # each must appear (in order) after boot
    expect_pins:                 # checked at the end
      - { part: led1, pin: A, value: 1 }
    screenshot: oled1            # part id to screenshot at the end (optional)
```
Validation (projects.py): name `^[a-z0-9][a-z0-9-]{0,40}$`; at most 20 tests; `run_ms` 100–15000;
at most 10 items per list; strings at most 200 chars; part ids must exist in `diagram.json`.

`BOARD_ALIASES` = `{"esp32": "esp32:esp32:esp32", "esp32s3": "esp32:esp32:esp32s3",
"esp32c3": "esp32:esp32:esp32c3", "uno": "arduino:avr:uno", "nano": "arduino:avr:nano",
"mega": "arduino:avr:mega"}`. The template diagram picks the matching Wokwi board part
(`board-esp32-devkit-c-v4`, `board-esp32-s3-devkitc-1`, `board-esp32-c3-devkitm-1`,
`wokwi-arduino-uno`, `wokwi-arduino-nano`, `wokwi-arduino-mega`).

`wokwi.toml` firmware path per platform (arduino-cli `--output-dir build`):
ESP32 → `build/<name>.ino.bin` + `elf = build/<name>.ino.elf`; AVR → `build/<name>.ino.hex` + elf.
`projects.py` rewrites `wokwi.toml` whenever `name` or `board` changes.

## Tools: inputs and outputs
All return JSON strings. Common failure shape:
`{"ok": false, "error": "<code>", "message": "...", "hint": "..."}`.
Error codes: `tool_missing`, `token_missing`, `bad_args`, `project_not_found`, `path_outside_workspace`,
`compile_failed`, `timeout`, `wokwi_error`, `port_not_found`, `serial_unavailable`, `budget_exhausted`,
`internal`.

### mcu_doctor `{}`
```json
{"ok": true, "checks": [
  {"name": "arduino-cli", "ok": true, "detail": "1.x.y"},
  {"name": "core esp32:esp32", "ok": false, "fix": "arduino-cli core install esp32:esp32 --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json"},
  {"name": "wokwi-cli", "ok": true, "detail": "0.x"},
  {"name": "WOKWI_CLI_TOKEN", "ok": true, "detail": "set"},
  {"name": "pyserial", "ok": false, "fix": "pip install 'pyserial>=3.5,<4' (only for real boards)"}],
 "workspace": "/…/plugin-data/boardloop/projects",
 "wokwi_minutes_30d": {"used": 3.4, "limit": 50}}
```

### mcu_project_new `{name, template, board?}` → `{"ok": true, "project": "thermostat2", "path": "…", "files": [...], "next": "Edit the sketch, then call mcu_verify"}`

### mcu_project_info `{project}`
```json
{"ok": true, "project": "thermostat", "board": "esp32", "fqbn": "esp32:esp32:esp32",
 "files": ["thermostat.ino", "diagram.json", "wokwi.toml", "boardloop.yaml"],
 "parts": [{"id": "dht1", "type": "wokwi-dht22", "attrs": {"temperature": "24"}}, "..."],
 "wiring": ["oled1:SDA → esp:21", "oled1:SCL → esp:22", "dht1:SDA → esp:4", "esp:26 → r1:1", "..."],
 "tests": ["hot room turns the LED on", "cool room keeps the LED off", "exactly 30 C is not too hot"],
 "last_verify": {"status": "verified", "at": "2026-11-10T14:03:00Z"}}
```
The agent edits files with Hermes's normal file tools; BoardLoop tools never take whole file contents.

### mcu_libraries `{action, name?}` → search: up to 8 `{name, latest, sentence}`; install: `{ok, installed, version}`.

### mcu_compile `{project, fqbn?, clean?}`
```json
{"ok": false, "error": "compile_failed",
 "errors": [{"file": "thermostat-buggy.ino", "line": 24, "col": 1,
   "message": "expected ',' or ';' before 'Adafruit_SSD1306'",
   "context": ["22: const float THRESHOLD_C = 30.0", "24: Adafruit_SSD1306 display(128, 64, &Wire, -1);"],
   "hint": "A statement just above this line is missing a ';'."}],
 "error_count": 1, "attempt": "1/3"}
```
Success: `{"ok": true, "firmware": "build/thermostat.ino.bin", "flash_used": "28%", "ram_used": "6%", "seconds": 41.2}`.

**Error parsing:** regex over stderr lines
`^(?P<file>[^:\n]+):(?P<line>\d+):(?P<col>\d+): (?P<kind>fatal error|error): (?P<msg>.+)$`;
strip build-path prefixes so `file` is relative to the project; dedupe; at most 10 errors.
`fatal error: X.h: No such file or directory` → hint: `mcu_libraries search` with a guessed name
(map: `DHTesp.h → DHT sensor library for ESPx`, `DHT.h → DHT sensor library`,
`Adafruit_SSD1306.h → Adafruit SSD1306`, `Adafruit_GFX.h → Adafruit GFX Library`,
`U8g2lib.h → U8g2`, `LiquidCrystal_I2C.h → LiquidCrystal I2C`, `ESP32Servo.h → ESP32Servo`).
Other hints: "was not declared in this scope" → typo or missing include; "expected ';'" →
missing semicolon; "invalid conversion" → type mismatch; unknown FQBN → `mcu_doctor`.
Also handle "Platform 'esp32:esp32' not found" → `tool_missing` with the core-install command.

### mcu_simulate `{project, timeout_ms?, expect_text?, fail_text?, screenshot_part?, screenshot_time_ms?}`
```json
{"ok": true, "passed": true, "reason": "expected text seen: BOOT OK",
 "sim_ms": 1830, "serial_tail": ["BOOT OK", "T=24.0 H=40.0 LED=OFF"],
 "screenshot": "/…/runs/20261110-140301-ab12/oled1.png", "wokwi_minutes_30d": 3.5}
```
argv: `[wokwi_cli, <project_dir>, "--timeout", str(t), "--serial-log-file", <log>, "--quiet"]`
plus `--expect-text`, `--fail-text`, `--screenshot-part`, `--screenshot-time`, `--screenshot-file`.
Requires `build/` firmware; if missing, returns `bad_args` with "run mcu_compile first".

**Classification** (VERIFY against the real CLI and adjust): exit 0 → passed; exit 42
(`--timeout-exit-code` default) → `timeout` ("expected text never appeared" when `expect_text` is
set); other non-zero → failed, reason taken from the last error line of stdout/stderr (e.g. fail
text seen, scenario expectation failed, firmware not found, token invalid). Detect "token" /
"unauthorized" in output → `token_missing` with a hint.

### mcu_test `{project, tests?, only?}`
```json
{"ok": true, "passed": 1, "failed": 2, "total": 3,
 "results": [
   {"name": "hot room turns the LED on", "passed": false, "reason": "expected led1:A = 1, got 0",
    "serial_tail": ["BOOT OK", "T=35.0 H=50.0 LED=OFF"], "screenshot": "…/hot-room/oled1.png", "sim_ms": 4200},
   {"name": "cool room keeps the LED off", "passed": false, "reason": "expected serial 'LED=OFF' not seen", "serial_tail": ["T=20.0 H=45.0 LED=ON"]},
   {"name": "exactly 30 C is not too hot", "passed": true}],
 "wokwi_minutes_30d": 4.1}
```
**Run directory** per test: `<plugin-data>/boardloop/runs/<run-id>/<test-slug>/` containing
copies of `wokwi.toml`, the patched `diagram.json`, the `build/` firmware files referenced by
`wokwi.toml`, and `scenario.yaml`. Delete run dirs older than 24 h at startup (keep screenshots
of the latest run per project).

**Scenario generation** (`scenario.py`, a pure function, unit-tested):
```yaml
name: <test name>
version: 1
author: BoardLoop
steps:
  - wait-serial: "<boot_text>"               # if boot_text set
  - set-control:                             # one per controls[] item
      part-id: btn1
      control: pressed                       # VERIFY: newer CLI uses `name:`; emit the key that works
      value: 1
  - delay: <run_ms>ms
  - wait-serial: "<expect_serial[0]>"        # one per item, in order
  - expect-pin:                              # one per expect_pins[] item
      part-id: led1
      name: A                                # older CLI versions used `pin:`
      value: 1
  - take-screenshot:                         # if screenshot set
      part-id: oled1
      save-to: screenshots/<test-slug>.png
```
Wokwi timeout for a test = `boot allowance 3000 + run_ms + 1000 per expect_serial + 2000`, capped
at 20000. Pass `--fail-text <fail_text>` when set.
**Sensors** are applied by patching `diagram.json` attrs (string values) in the run copy, because
the DHT22 automation control isn't documented. If a sensor *must* change during a run, use
`controls` (for parts that document controls: potentiometer, pushbutton, MPU6050, HX711, joystick,
photoresistor).
**Failure reasons:** map wokwi-cli's expectation message to `expected <part>:<pin> = v, got w`;
a timeout while waiting → `expected serial '<text>' not seen` (use the step order to know which
text). Keep the raw last error line in `raw_reason` too.

### mcu_verify `{project, goal?}`
State machine in `loop.py`:
```
compile ── fail ──► {status: "fix_compile", attempt: n/3, errors}        (n > 3 → needs_human)
   │ ok
   ▼
test (all) ── fail ──► {status: "fix_behaviour", attempt: m/5, failures} (m > 5 → needs_human)
   │ all pass
   ▼
{status: "verified", tests: "3/3", screenshots: [...], next: "Flash a real board with mcu_upload if you have one"}
```
Counters per project in table `attempts`; reset on `verified` or when the user says "start over"
(`reset: true`). Budgets come from settings (`compile_budget` 3, `test_budget` 5). Each call adds
one `history` row. With no tests defined it returns `status: "needs_tests"` with a suggestion to
add tests that match the goal (the skill explains how).

### mcu_ports `{}` → `[{"port": "/dev/ttyUSB0", "protocol": "serial", "board": "ESP32 Dev Module", "fqbn": "esp32:esp32:esp32"}]`
argv `[arduino_cli, "board", "list", "--json"]` (VERIFY flag name: `--json` in 1.x, `--format json` in older).

### mcu_upload `{project, port, fqbn?}` (approval)
argv `[arduino_cli, "upload", "-p", port, "--fqbn", fqbn, "--input-dir", "build", project_dir]`.
`port` validated against `mcu_ports` output (must be listed) and the pattern
`^(/dev/tty[\w.-]+|/dev/cu\.[\w.-]+|COM\d{1,3})$`.

### mcu_serial_read `{port, baud?, seconds?, until_text?, expect_serial?}` → `{lines: [...], passed?}`
### mcu_serial_write `{port, baud?, text}` (approval; text ≤ 200 chars, newline appended)
### mcu_wiring_check `{project}` → `{warnings: [{"rule": "input_only_pin", "detail": "esp:35 drives led1:A; GPIO34-39 are input-only", "fix": "move to GPIO 26"}]}`

## Process handling (`procs.py`)
- `subprocess.Popen(argv, cwd=…, stdout=PIPE, stderr=PIPE, env=env, start_new_session=True)` on
  POSIX; `creationflags=CREATE_NEW_PROCESS_GROUP` on Windows.
- Wall-clock timeout: compile = `compile_timeout_s`; Wokwi = `timeout_ms/1000 * 3 + 60` s (the cloud
  may run slower than real time). On timeout kill the group (`os.killpg` / `taskkill /T /F`).
- `env` = a copy of `os.environ` plus `WOKWI_CLI_TOKEN` from `get_secret` for Wokwi only. Never log env.
- Truncate captured output to 200 KB before parsing.

## Data model (`storage.py`, `plugin_db("boardloop")`)
```sql
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, project TEXT NOT NULL, kind TEXT NOT NULL,  -- compile | simulate | test | upload
  started_ts INTEGER NOT NULL, sim_ms INTEGER NOT NULL DEFAULT 0,
  passed INTEGER, reason TEXT);
CREATE TABLE IF NOT EXISTS attempts (
  project TEXT NOT NULL, stage TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (project, stage));
CREATE TABLE IF NOT EXISTS verifies (
  project TEXT NOT NULL, ts INTEGER NOT NULL, status TEXT NOT NULL, summary TEXT);
```
Wokwi minutes (30 days) = `SUM(sim_ms) WHERE kind IN ('simulate','test') AND started_ts > now-30d` / 60000.
For runs that end early, `sim_ms` = the configured timeout as an upper bound (Wokwi counts actual
time; we over-estimate on purpose). VERIFY whether wokwi-cli prints the simulated time and use it if so.

## Screenshots and images
Screenshots are saved to the run dir and their absolute paths returned. VERIFY whether Hermes lets
a tool attach an image to its result for vision models (check the plugin docs for image results, or
use Hermes's built-in vision tool on the path). If neither exists, return the path and describe it:
the Desktop pane (P2) and README screenshots still show them.
