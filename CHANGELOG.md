# Changelog

## 0.1.0 (2026-11-11)

First release, for the Hermes Agent Plugin Hackathon.

- **Loop:** `mcu_verify` compiles, runs every behaviour test and returns one status with
  EmbedGenius attempt budgets (3 compile fixes, 5 behaviour fixes) and `needs_human` when spent.
- **Compile:** `mcu_compile` parses GCC errors (≤10, with source context) and adds fix hints,
  including the library to install for a missing header.
- **Simulate and test:** `mcu_simulate` and `mcu_test` run firmware on Wokwi in an isolated run
  folder per test, with sensor values patched into a copy of the diagram and generated automation
  scenarios: serial expectations, pin checks, button controls and part screenshots.
- **Projects:** `mcu_project_new` (4 templates), `mcu_project_info` (parts + wiring table),
  `mcu_libraries`, `mcu_wiring_check`, `mcu_export` for wokwi.com.
- **Real boards:** `mcu_ports`, `mcu_upload` and `mcu_serial_write` (both approval-gated),
  `mcu_serial_read`.
- **Hermes integration:** `/mcu` command, bundled skill, Wokwi minutes meter, settings with the
  token as a secret, and a Desktop renderer for simulated-display screenshots.
- **Verified against the real tools:** Wokwi formats recorded from wokwi-cli 0.29.1; arduino-cli 1.5.1.
