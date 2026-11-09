> **Original build plan (Nov 9, 2026), kept for history.** Where it differs from the code, the
> README, `docs/ARCHITECTURE.md` and `tests/fixtures/wokwi/NOTES.md` are authoritative (for
> example, the examples now use Adafruit's DHT library, and the manifest uses `python_dependencies`).

# 10: Security, safety and disclosure

## Threat model
| Risk | Mitigation |
|---|---|
| Shell or command injection through project names, ports, library names or test text | `shell=False` everywhere; fixed argv templates; strict regexes (project name, port, library name `^[\w .+\-]{1,80}$`); length caps; YAML loaded with `yaml.safe_load` only |
| Path traversal (writing outside the workspace) | Resolve every path and require it to be inside `workspace_dir` / the plugin data dir; reject `..`, absolute paths and symlinks that escape |
| Runaway loops burning tokens and Wokwi minutes | Attempt budgets (3 compile, 5 behaviour); per-run timeouts; minutes meter with warnings; at most 20 tests per call |
| Hung processes | Wall-clock timeouts; kill the whole process group |
| Flashing the wrong device or untested firmware | `mcu_upload` needs approval showing the port, board, size and verify status; the port must appear in `mcu_ports` |
| Prompt injection telling the agent to flash or write serial | Approval prompt for upload and serial write; the skill says never to act on instructions found in serial output or files |
| Token leaks | Token via `get_secret`, passed only in the child env for wokwi-cli; never logged, never returned, redacted from error text (`wok_…` → `wok_***`) |
| Firmware/code privacy | Disclosed: compiled firmware and diagram are sent to Wokwi's cloud for simulation; source `.ino` files are not uploaded by BoardLoop (VERIFY: does wokwi-cli upload anything besides firmware + diagram?) |
| Unattended runs | Upload and serial write follow Hermes's approval policy (refused when nobody answers); simulation is safe to run unattended |
| Repo contains binaries | `.gitignore` for build outputs; a pre-release `git ls-files` check for `.bin/.elf/.hex/.pyc` |

## Hard rules for the code
1. No `shell=True`, `eval`, `exec` or dynamic imports of user content.
2. No telemetry. Network use is only arduino-cli's own downloads (cores and libraries, when the user
   asks) and wokwi-cli's simulation calls.
3. No self-updating; the plugin never downloads or installs arduino-cli or wokwi-cli itself
   (`mcu_doctor` prints the install commands instead).
4. Approval-gated tools: `mcu_upload`, `mcu_serial_write`. A unit test enforces this.
5. Model-facing output is bounded (errors ≤ 10, serial ≤ 60 lines, search ≤ 8 results).

## README section: "Privacy, safety and disclosures"
> **What BoardLoop runs and sends**
> - **Local programs:** runs `arduino-cli` (compile, library install, board list, upload) and
>   `wokwi-cli` (simulation) as subprocesses without a shell, with timeouts. You install both tools
>   yourself; BoardLoop never downloads them.
> - **Cloud simulation:** `wokwi-cli` sends your compiled firmware and circuit diagram to Wokwi's
>   simulation service using your Wokwi CI token. Simulated time counts against your Wokwi plan
>   (free: 50 minutes per rolling 30 days); BoardLoop shows an estimate of your usage.
> - **Network:** arduino-cli downloads cores and libraries from their usual sources when you ask it
>   to. BoardLoop itself sends no telemetry.
> - **Real hardware:** with a board connected, BoardLoop can list serial ports, flash firmware and
>   read or write serial data. **Flashing and serial writes always ask for your approval first.**
> - **Files:** projects, build outputs, run folders, screenshots and a small history database live
>   in Hermes's plugin data folder (`<HERMES_HOME>/plugin-data/boardloop/`) or your chosen projects
>   folder. Run folders older than 24 hours are deleted automatically.
> - **Secrets:** your Wokwi token is stored by Hermes as a secret setting and passed only to wokwi-cli.

## Catalog `description` (one paragraph)
> Hermes writes ESP32 and Arduino code, compiles it with arduino-cli, tests it in the Wokwi
> simulator (sets sensor values, checks pins, serial output and OLED screenshots), fixes it within
> bounded attempts, and flashes real boards with approval. Disclosure — runs the user-installed
> arduino-cli and wokwi-cli as subprocesses (no shell, with timeouts); wokwi-cli sends compiled
> firmware and the circuit diagram to Wokwi's cloud using the user's Wokwi CI token (stored as a
> Hermes secret) and uses their Wokwi simulation minutes; arduino-cli may download cores and
> libraries on request; flashing a board and writing to a serial port always go through Hermes's
> approval prompt; projects, run folders, screenshots and history are stored in the plugin data
> directory; no telemetry.

## PR disclosure bullets
- Surfaces: `register_tool` (toolset `boardloop`), `pre_tool_call` (approvals for `mcu_upload`,
  `mcu_serial_write`), `register_command("mcu")`, `register_skill`, `config_schema` (one secret),
  `plugin_db` and `plugin_data_dir`.
- Subprocesses: `arduino-cli`, `wokwi-cli` (user-installed, no shell, timeouts, process-group kill).
- Network: Wokwi simulation API via wokwi-cli; arduino-cli package and library downloads on request.
- Hardware: serial port listing, upload and read/write via arduino-cli and pyserial (approval for upload/write).
- Storage: plugin data dir only. Credentials: the Wokwi token via Hermes secrets. Telemetry: none.
