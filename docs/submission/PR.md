# plugin-catalog: add boardloop (write, simulate, test and flash ESP32/Arduino code)

## BoardLoop

Hermes writes ESP32/Arduino code, compiles it with arduino-cli, tests it in the Wokwi simulator
(sets sensor values, presses buttons, checks pins, serial output and OLED screenshots), fixes it
within bounded attempts, and flashes real boards with approval. Hermes Agent Plugin Hackathon entry.

Repo: https://github.com/LSUDOKO/BoardLoop (pinned at `<SHA>`) · Demo: <X link>

### Hermes surfaces used
- `register_tool` (toolset `boardloop`): mcu_doctor, mcu_project_new, mcu_project_info, mcu_libraries,
  mcu_compile, mcu_simulate, mcu_test, mcu_verify, mcu_ports, mcu_upload, mcu_serial_read,
  mcu_serial_write, mcu_wiring_check, mcu_export
- `pre_tool_call`: approval for `mcu_upload`, `mcu_serial_write` (escalate only; no auto-approve)
- `register_command("mcu")`, `register_skill("boardloop")`
- `config_schema` (Wokwi token as a `secret`, read with `get_secret`), `plugin_db`, `plugin_data_dir`
- Desktop half (`desktop/plugin.js`): one `TOOL_MEDIA_RENDERER_AREA` contribution for its own tools' screenshots

### Disclosures
- Runs user-installed `arduino-cli` and `wokwi-cli` as subprocesses (no shell, timeouts, process-group kill).
- wokwi-cli sends compiled firmware and the diagram to Wokwi's cloud using the user's token and plan minutes.
- arduino-cli may download cores and libraries when the user asks.
- Flashing and serial writes always go through Hermes's approval prompt.
- Stores projects, run folders, screenshots and history in the plugin data dir. No telemetry.

### Related entries
Complements `esp32-debug` (read-only crash triage) and `rigforge` (machine design / sketch
generation): BoardLoop compiles, simulates, tests and flashes.

### Validation
`hermes plugins validate . --install-deps` passes at the pinned commit; security scan: `safe`.
