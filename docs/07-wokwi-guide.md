# 07: Wokwi guide (verified formats + VERIFY list)

Verified against docs.wokwi.com on Nov 9, 2026 unless marked VERIFY.

## wokwi-cli flags BoardLoop uses
| Flag | Meaning |
|---|---|
| `wokwi-cli <project-dir>` | Run the project in that folder (reads `wokwi.toml`, `diagram.json`) |
| `--timeout <ms>` | Simulated-time timeout (default 30000). **Always set it.** |
| `--timeout-exit-code <n>` | Exit code on timeout (default **42**) |
| `--expect-text <s>` | Pass when the text appears on serial |
| `--fail-text <s>` | Fail when the text appears |
| `--serial-log-file <path>` | Save serial output |
| `--scenario <path>` | Automation scenario YAML, **relative to the project root** |
| `--screenshot-part <id>` / `--screenshot-time <ms>` / `--screenshot-file <name>` | Screenshot a part (default `screenshot.png`) |
| `--diagram-file <path>` | Use another diagram file (default `diagram.json`) |
| `--elf <path>` | Override the ELF from wokwi.toml |
| `--quiet` / `-q` | Hide version and status messages |
| `--vcd-file <path>` | Logic-analyzer export (not needed) |
| `--heap-min-free <bytes>` | Fail if free heap drops below (needs ELF; optional P2 test) |
| `wokwi-cli init` / `wokwi-cli lint` | Create config / validate `diagram.json` |

Token: env `WOKWI_CLI_TOKEN` (`wok_…`, 44 chars).

## wokwi.toml
```toml
[wokwi]
version = 1
firmware = 'build/<sketch>.ino.bin'   # ESP32 via arduino-cli --output-dir build (AVR: .ino.hex)
elf = 'build/<sketch>.ino.elf'        # optional, can speed up the simulation
```
Paths are relative, with forward slashes. A plain `.bin` is application-only; Wokwi adds its own
bootloader and default partition table (4 MB flash), which is fine for our projects.

## diagram.json
Top level: `version` (1), `author`, `editor` ("wokwi"), `parts[]`, `connections[]`.
Part: `{type, id, top, left, rotate?, attrs?}`. Connection: `["part:pin", "part:pin", "color", [routing hints]]`.
Serial monitor links: `["esp:TX", "$serialMonitor:RX", "", []]` and `["esp:RX", "$serialMonitor:TX", "", []]`.

Parts used by the examples:
| Part | type | Pins / attrs |
|---|---|---|
| ESP32 DevKitC V4 | `board-esp32-devkit-c-v4` | GPIO pins by number (`esp:21`, `esp:22`, `esp:4`, `esp:26`); `esp:3V3`, `esp:5V`, `esp:GND.1`… `esp:TX`/`esp:RX` |
| SSD1306 OLED 128x64 | `board-ssd1306` | `GND VCC SCL SDA`; attr `i2cAddress` default `0x3c` |
| DHT22 | `wokwi-dht22` | `VCC SDA NC GND`; attrs `temperature` (default "24"), `humidity` (default "40"). On ESP32 use **"DHT sensor library for ESPx"** (Wokwi says other DHT libraries may be unreliable) |
| LED | `wokwi-led` | `A` (anode), `C` (cathode); attr `color` |
| Resistor | `wokwi-resistor` | `1`, `2`; attr `value` (ohms) |
| Pushbutton | `wokwi-pushbutton` | `1.l 1.r 2.l 2.r`; supports automation controls (VERIFY the control name) |
| Arduino Uno | `wokwi-arduino-uno` | pins by number (`uno:13`), `uno:GND.1`… |

Other ESP32 boards: `board-esp32-s3-devkitc-1`, `board-esp32-c3-devkitm-1`, `board-esp32-c6-devkitc-1`,
`board-xiao-esp32-c3`, `board-xiao-esp32-s3` and more. **VERIFY pin names** for any new board with
`wokwi-cli lint` or by hovering pins on wokwi.com.

## Automation scenarios (Wokwi marks these **alpha**)
Top level: `name`, `version: 1`, `author`, `steps[]`. Steps:
| Step | Fields |
|---|---|
| `wait-serial: "<text>"` | waits for serial text (the docs table says `text`, the examples pass a plain string) |
| `write-serial` | `value`: string or array of numbers |
| `delay: 500ms` | units required |
| `set-control` | `part-id`, `name` (older CLI: `control`), `value` |
| `expect-pin` | `part-id`, `name` (older CLI: `pin`), `value` |
| `take-screenshot` | `part-id`, `save-to` and/or `compare-with` |
| `touch`, `touch-press`, `touch-move`, `touch-release` | touch displays |

Parts with documented automation controls: potentiometer, pushbutton, MPU6050, analog joystick,
HX711, photoresistor. **The DHT22 has no documented control**, so BoardLoop sets its temperature and
humidity through `diagram.json` attrs in a per-test copy. That's reliable and also faster (no
mid-run changes).

## VERIFY list (check during Phase 0/1; record the answers in `tests/fixtures/wokwi/NOTES.md`)
1. Exit code and message when `--expect-text` is found (expect 0) and when it times out (expect 42).
2. Exit code and message when `--fail-text` appears.
3. Exit code and exact message when an `expect-pin` step fails (needed for the
   `expected led1:A = 1, got 0` reason).
4. Does the CLI exit as soon as the scenario's last step finishes? (Otherwise every test burns the full timeout.)
5. Is `take-screenshot` `save-to` relative to the project root? Does the SSD1306 screenshot work?
6. `set-control` / `expect-pin` key names for your CLI version (`name` vs `control`/`pin`).
7. Pushbutton control name and values (`pressed` 1/0?). See the Wokwi parts docs for `wokwi-pushbutton`.
8. Does the CLI print simulated time used? (Use it for the minutes meter if so.)
9. Does `wokwi-cli lint` take a path argument?
10. What does an invalid or missing token look like (message and exit code)?

## Saving Wokwi minutes (free plan = 50 simulated min / rolling 30 days)
- Unit tests use the **fake wokwi-cli** (docs/11). Real runs only for checkpoints and the demo.
- Short timeouts: boot (~1–2 s) + `run_ms` 2000–3000 is enough for most tests.
- Stop early: `--expect-text`, and scenarios that end when the last step completes.
- Run only the failing tests while fixing (`mcu_test only=[...]`), and all tests for the final verify.
- Rough budget: 3 tests × ~6 s = ~0.3 min per full verify → about 150 full verifies on the free plan.

## Making the simulation visible in the demo
The CLI has no live picture, so:
1. Show **OLED screenshots** from tests in Hermes's replies, in the Desktop pane (P2) and in the README.
2. For a live circuit view, paste `diagram.json` and the sketch into a new project on **wokwi.com**
   (browser, free) and press play, or open the folder in the **Wokwi VS Code extension** (same
   `wokwi.toml`; VERIFY the extension's licence terms). Record that window next to Hermes.
3. Optional real board at the end: flash the same build and film the LED.
