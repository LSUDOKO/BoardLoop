# 06: Developer setup

Works on macOS, Linux and Windows (WSL is easiest on Windows; for **real-board USB on Windows, use
native Windows**, since WSL needs extra USB passthrough).

## 1. Basics
- Python 3.11+ (`python3 --version`), Git, a GitHub account.
- `python3 -m pip install --user pytest "pyyaml>=6.0,<7" "pyserial>=3.5,<4"`

## 2. Hermes Agent
1. Install from https://hermes-agent.nousresearch.com and run `hermes` once (pick a model).
2. `hermes --version`: use this as the `requires_hermes` floor.
3. `hermes plugins --help`: check that `doctor`, `validate`, `list` and `enable` exist.
4. Running Hermes on your Claude subscription? Use only the official "Claude Subscription" provider
   plugin, which drives the real `claude` CLI. Claude Code and Hermes then share the same usage limits.

## 3. Claude Code
Docs: https://code.claude.com/docs/en/overview
- Install with the official installer for your OS from the docs page above.
- Or `brew install --cask claude-code` / `winget install Anthropic.ClaudeCode`
Open a new terminal: `claude --version`. Log in on first run.

## 4. arduino-cli + ESP32 core + libraries
Install arduino-cli (docs: https://arduino.github.io/arduino-cli/latest/installation/):
- macOS: `brew install arduino-cli`
- Linux / WSL: download the Linux release archive from https://github.com/arduino/arduino-cli/releases/latest
  and put `arduino-cli` on your PATH (or use the installer described on the installation page)
- Windows: download the Windows .zip from https://github.com/arduino/arduino-cli/releases/latest
  and put `arduino-cli.exe` on your PATH (or find a package with `winget search arduino-cli`).

Then:
```bash
arduino-cli config init
arduino-cli core update-index --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core install esp32:esp32 --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core install arduino:avr
arduino-cli lib install "Adafruit SSD1306" "Adafruit GFX Library" "DHT sensor library for ESPx"
arduino-cli version
```
To avoid repeating `--additional-urls`:
`arduino-cli config add board_manager.additional_urls https://espressif.github.io/arduino-esp32/package_esp32_index.json`
(VERIFY: older versions use `config set`).
The ESP32 core is a large download (hundreds of MB) and the **first ESP32 compile takes 1–3
minutes**; later ones are much faster.

## 5. wokwi-cli + token
Docs: https://docs.wokwi.com/wokwi-ci/getting-started
- Install with the official installer for your OS from the getting-started page above
  (it publishes one script for Linux/macOS and one for Windows PowerShell).
- Check: `wokwi-cli --help`
- Token: sign in at wokwi.com → your account's **CI / API tokens** page (linked from the Wokwi CI
  getting-started docs) → create a token. It starts with `wok_` and is 44 characters long.
- Set it for your shell:
  - macOS/Linux: `export WOKWI_CLI_TOKEN=wok_...` (add to `~/.bashrc` / `~/.zshrc` for later)
  - Windows: `setx WOKWI_CLI_TOKEN wok_...` (then open a new terminal)
- In Hermes, also put it in the plugin setting **Wokwi CI token** (stored as a secret). The plugin
  reads it from there with `get_secret`.
- Free plan: **50 simulated minutes per rolling 30 days** (Hobby 200, Hobby+ 500, Pro 2000).

## 6. Toolchain smoke test (must pass before Phase 1)
```bash
cd examples/thermostat
arduino-cli compile --fqbn esp32:esp32:esp32 --output-dir build .
ls build                                  # expect thermostat.ino.bin and thermostat.ino.elf
wokwi-cli . --timeout 5000 --expect-text "BOOT OK"
echo "exit code: $?"                      # expect 0
wokwi-cli lint                            # validates diagram.json (VERIFY: run it inside the project folder)
```
Then the scenario test: set `dht1` temperature to `"35"` in `diagram.json`, run
`wokwi-cli . --timeout 6000 --scenario scenario-hot.yaml`, and check that `screenshots/hot.png`
exists and shows the OLED. Then set it back to `"24"`.

Also try the deliberate failure: `wokwi-cli . --timeout 4000 --expect-text "NEVER"` → note the exit
code (expected 42) and the message. **Copy these outputs into `tests/fixtures/wokwi/`** so Claude
builds the result parser against real output (Prompt 1b).

## 7. Real board (optional, P1)
- ESP32 DevKit boards use a CP210x or CH340 USB chip. Install the driver if the port doesn't show:
  - CP210x: Silicon Labs "CP210x USB to UART Bridge VCP" driver
  - CH340: WCH "CH341SER" driver
- Linux: add yourself to the serial group (`sudo usermod -aG dialout $USER`, then log out and back in).
- `arduino-cli board list` should show the port (e.g. `/dev/ttyUSB0`, `/dev/cu.usbserial-…`, `COM5`).
- Test: `arduino-cli upload -p <port> --fqbn esp32:esp32:esp32 --input-dir build .` inside
  `examples/thermostat`. Some boards need the **BOOT** button held when "Connecting…" appears.

## 8. Load your working copy in Hermes
```bash
ln -s "$(pwd)" ~/.hermes/plugins/boardloop        # macOS/Linux/WSL; on Windows copy the folder instead
hermes plugins enable boardloop
HERMES_PLUGINS_DEBUG=1 hermes plugins list         # boardloop and its mcu_* tools should appear
```
If the symlink isn't picked up (VERIFY), copy the folder. Restart Hermes after code changes.
