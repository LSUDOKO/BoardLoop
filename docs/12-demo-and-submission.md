# 12: Demo video, README outline and submission

## Demo video (< 90 s; aim for 80)

### Recording setup
- Screen: Hermes (Desktop or terminal, large font) on the left; on the right, the circuit running on
  **wokwi.com** (the same sketch and `diagram.json` pasted into a browser project) or the Desktop
  Workbench pane. Optional: a phone camera on a real ESP32 for the last shot.
- Before recording: run the demo once to warm the arduino-cli cache (the first ESP32 compile is
  slow), copy a **fresh** `thermostat-buggy` into the workspace, run `/mcu` to show minutes, clear
  the chat.
- Speed up long waits 2–4x in editing and say so with a small "sped up" label (honest and allowed).
- Rough Wokwi cost: about 3–5 full test runs, under 1 simulated minute.

### Script
| Time | Screen | Voice / caption |
|---|---|---|
| 0–7 s | Title: "BoardLoop: Hermes proves its hardware code works" | "AI writes Arduino code that usually doesn't work on the board. Research: the best model passes only 56% of embedded tasks." |
| 7–20 s | Prompt: *"The thermostat-buggy project is broken: make it pass its tests."* → `mcu_verify` → compile error, line 24 → Hermes fixes the `;` | "BoardLoop gives Hermes a real compiler…" |
| 20–40 s | Second `mcu_verify` → tests run in Wokwi → "hot room: expected led1:A = 1, got 0" → Hermes reads the serial tail and flips `<` to `>` | "…and a simulated circuit. Hermes sets the sensor to 35 °C and checks the LED itself." |
| 40–52 s | Third `mcu_verify` → **verified 3/3**, OLED screenshot showing "35.0 C ALERT" | "Every test passes: hot, cool, and exactly 30 degrees." |
| 52–70 s | New prompt: *"Add a buzzer that beeps above 35 °C and test it."* → Hermes edits the diagram and code, adds a test → verified (sped up) | "New features come with their own tests." |
| 70–82 s | Either a real ESP32: approval prompt → flash → LED lights when warmed by hand; or the wokwi.com circuit running | "Then flash a real board, with your approval." |
| 82–88 s | End card: repo URL, "Hermes Marketplace", @NousResearch, `/mcu` minutes meter | "BoardLoop, open source." |

## X post template
```
🔌 BoardLoop for @NousResearch Hermes Agent: Hermes doesn't just write ESP32/Arduino code, it proves it works.

✅ compiles with arduino-cli
🧪 tests in the Wokwi simulator: sets sensors, checks LEDs, serial and the OLED
🔁 fixes its own bugs (bounded attempts)
⚡ flashes real boards with your approval

Hermes Agent Plugin Hackathon entry 👇
<github link>
```
Attach the video natively (not as a link).

## README outline (Prompt 6)
1. Title + one-line pitch + demo GIF/video link
2. Why: the research table (docs/02)
3. What it does: the loop diagram + tool list
4. Quick start: install arduino-cli, the ESP32 core and libraries, wokwi-cli + token, the plugin, `/mcu doctor`
5. Example prompts (thermostat, buggy fix, new project from a template, real board)
6. Writing tests: `boardloop.yaml` format with the thermostat example
7. Supported boards and parts (ESP32 family, Uno/Nano/Mega; any part Wokwi simulates)
8. Settings
9. Privacy, safety and disclosures (docs/10)
10. Wokwi minutes and the free plan
11. Related plugins (esp32-debug, rigforge, gadget) and how BoardLoop complements them
12. Limitations
13. Development (tests, fakes) and License

## Catalog PR
1. Release: tests, doctor and validate green → push → `git rev-parse HEAD` → tag `v0.1.0`.
2. Fork https://github.com/NousResearch/hermes-agent, add `plugin-catalog/boardloop.yaml` (docs/05),
   with every URL pinned to the SHA.
3. PR title: `plugin-catalog: add boardloop (write, simulate, test and flash ESP32/Arduino code)`
4. PR body:
```markdown
## BoardLoop

Hermes writes ESP32/Arduino code, compiles it with arduino-cli, tests it in the Wokwi simulator
(sets sensor values, checks pins, serial output and OLED screenshots), fixes it within bounded
attempts, and flashes real boards with approval. Hermes Agent Plugin Hackathon entry.

Repo: https://github.com/<you>/boardloop (pinned at <sha>) · Demo: <X link>

### Hermes surfaces used
- `register_tool` (toolset `boardloop`): <tools>
- `pre_tool_call`: approval for `mcu_upload`, `mcu_serial_write`
- `register_command("mcu")`, `register_skill("boardloop")`
- `config_schema` (Wokwi token as a secret via `get_secret`), `plugin_db`, `plugin_data_dir`

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
`hermes plugins validate . --install-deps` passes at the pinned commit (output attached).
```
5. Submit the form: https://form.typeform.com/to/FwJLvOln (PR link + X link).

## Final checklist (Nov 11)
- [ ] Repo public; README complete; LICENSE; no binaries or tokens tracked
- [ ] validate green at the tagged commit
- [ ] Catalog PR open with the right SHA and pinned image URLs
- [ ] Demo < 90 s on X tagging @NousResearch
- [ ] Form submitted; confirmation screenshotted
- [ ] Re-checked open PRs for any new similar entry; README "related plugins" updated
