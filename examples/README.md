# Example projects

| Folder | Board | What it shows |
|---|---|---|
| `thermostat/` | ESP32 DevKitC V4 | DHT22 → OLED readout; red LED on above 30 °C. 3 tests (hot, cool, exactly 30 °C). `scenario-hot.yaml` is a hand-written raw Wokwi scenario for checking your CLI. |
| `thermostat-buggy/` | ESP32 | The same project with **two planted bugs**: a missing `;` (compile error at line 24) and a reversed comparison (`<` instead of `>`), which fails the hot and cool tests. Used in the demo: "make it pass its tests". |
| `blink-uno/` | Arduino Uno | LED blinks; holding the button keeps it on. Shows non-ESP32 support and button `controls`. |

Each project folder has the same name as its `.ino` file (an arduino-cli rule) and contains:
- `<name>.ino`: the sketch
- `diagram.json`: the Wokwi circuit
- `wokwi.toml`: tells Wokwi where the compiled firmware is (`build/…` from `arduino-cli compile --output-dir build`)
- `boardloop.yaml`: BoardLoop's project file: board, libraries and **tests**

Status: all three compile with arduino-cli 1.5.1 and pass on Wokwi (wokwi-cli 0.29.1); the
buggy one fails exactly as planted. They also ship as templates: `mcu_project_new` with
`esp32-thermostat`, `uno-blink` or `demo-thermostat-buggy`. The pushbutton control name
(`pressed`) is confirmed by a recorded run (`tests/fixtures/wokwi/real_button_pass.json`).
