> **Original build plan (Nov 9, 2026), kept for history.** Where it differs from the code, the
> README, `docs/ARCHITECTURE.md` and `tests/fixtures/wokwi/NOTES.md` are authoritative (for
> example, the examples now use Adafruit's DHT library, and the manifest uses `python_dependencies`).

# 05: Hermes plugin reference (what BoardLoop needs)

Collected from the official Hermes docs and the open-source `phone-harness` plugin (Nov 7–9, 2026).
**VERIFY** = check the linked page before relying on it.

- Build a plugin: https://hermes-agent.nousresearch.com/docs/developer-guide/plugins
- Catalog submission and rules: https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/catalog-submission
- Catalog README (entry schema): https://github.com/NousResearch/hermes-agent/blob/main/plugin-catalog/README.md
- Hooks: https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks
- Desktop SDK: https://hermes-agent.nousresearch.com/docs/developer-guide/desktop-plugin-sdk
- Real example with approvals: https://github.com/phone-harness/phone-harness/tree/main/integrations/hermes

## Discovery and local testing
- User plugins: `~/.hermes/plugins/<name>/` containing `plugin.yaml` + `__init__.py`.
- Enable: `hermes plugins enable boardloop`.
- Debug discovery: `HERMES_PLUGINS_DEBUG=1 hermes plugins list`; logs: `~/.hermes/logs/agent.log`.
- Isolated check: `hermes plugins doctor <path> --ci`.
- Catalog-equivalent check: `hermes plugins validate <path> --install-deps`.

## plugin.yaml
```yaml
name: boardloop
version: 0.1.0
manifest_version: 2
description: Hermes writes ESP32/Arduino code, compiles it, tests it in the Wokwi simulator (sensors, pins, serial, OLED screenshots), fixes it, and flashes real boards with approval
author: <Your Name>
license: MIT
homepage: https://github.com/<you>/boardloop
tags: [hardware, esp32, arduino, embedded, simulation, wokwi, iot]
requires_hermes: ">=X.Y.Z"          # floor = the version you test on (`hermes --version`), never newer than the current release
dependencies:                       # VERIFY the exact key name for pip deps in the developer guide
  - "pyyaml>=6.0,<7"
  - "pyserial>=3.5,<4"
provides_tools:                     # MUST equal what register() registers
  - mcu_doctor
  - mcu_project_new
  - mcu_project_info
  - mcu_libraries
  - mcu_compile
  - mcu_simulate
  - mcu_test
  - mcu_verify
  - mcu_ports
  - mcu_upload
  - mcu_serial_read
  - mcu_serial_write
  - mcu_wiring_check
provides_hooks:
  - pre_tool_call
config_schema:
  workspace_dir:       {type: str,  default: "", label: "Projects folder", description: "Leave empty for Hermes's plugin data folder"}
  default_board:       {type: str,  default: "esp32", label: "Default board"}
  wokwi_token:         {type: secret, env: WOKWI_CLI_TOKEN, label: "Wokwi CI token", description: "From your Wokwi account's CI settings; starts with wok_"}
  wokwi_minutes_limit: {type: int,  default: 50, label: "Wokwi minutes per 30 days", description: "Your plan limit; free plan is 50"}
  sim_timeout_ms:      {type: int,  default: 6000, label: "Default simulation timeout (ms)"}
  compile_timeout_s:   {type: int,  default: 300, label: "Compile timeout (s)"}
  compile_budget:      {type: int,  default: 3, label: "Compile fix attempts"}
  test_budget:         {type: int,  default: 5, label: "Behaviour fix attempts"}
  arduino_cli_path:    {type: str,  default: "", label: "arduino-cli path (optional)"}
  wokwi_cli_path:      {type: str,  default: "", label: "wokwi-cli path (optional)"}
external_dependencies:              # VERIFY key name; the official claude-subscription plugin declares one
  - arduino-cli
  - wokwi-cli
```
Only list tools you actually registered: if real-board tools aren't built, remove them from the list.
VERIFY that `int` is an accepted `config_schema` type; otherwise use `str` and parse it.

## register(ctx)
```python
from . import schemas, tools, approvals, commands

def register(ctx):
    for name, schema, handler in tools.TOOLS:            # one table drives registration and tests
        ctx.register_tool(name=name, toolset="boardloop", schema=schema, handler=handler)
    ctx.register_hook("pre_tool_call", approvals.on_pre_tool_call)
    ctx.register_command("mcu", lambda raw: commands.handle(ctx, raw),
                         description="BoardLoop: status, projects, history, doctor")
    try:
        ctx.register_skill("boardloop", SKILL_PATH)        # VERIFY signature
    except TypeError:
        ctx.register_skill("boardloop", SKILL_PATH, description="Build, test and flash ESP32/Arduino projects")
```
Other APIs:
- `ctx.get_config("key", default=...)`: this plugin's settings.
- `from agent.secret_scope import get_secret; get_secret("WOKWI_CLI_TOKEN")`: the token. Never
  `os.environ[...]` for it, never read `.env`.
- `from plugins.plugin_storage import plugin_data_dir, plugin_db`: `plugin_db("boardloop")` returns
  SQLite (WAL) at `<HERMES_HOME>/plugin-data/boardloop/data.db`; `plugin_data_dir("boardloop")` is
  the folder for projects, runs and screenshots. Never write state into the plugin directory.
- `from plugins.plugin_utils import lazy_singleton`: thread-safe lazy singletons.

### Tool handler rules
`def handler(args: dict, **kwargs) -> str`. Always return a JSON string; never raise; accept
`**kwargs` (Hermes passes `task_id`, `session_id`, `conversation_id`).

## Approvals (pattern from phone-harness)
```python
NEEDS_APPROVAL = {"mcu_upload", "mcu_serial_write"}

def on_pre_tool_call(tool_name: str = "", args: dict | None = None, task_id: str = "", **kwargs):
    if tool_name not in NEEDS_APPROVAL:
        return None
    return {"action": "approve", "message": describe(tool_name, args or {}), "rule_key": tool_name}
```
Example message: `Flash "thermostat" (ESP32, 284 KB) to /dev/ttyUSB0. Tests: 3/3 passed in simulation.`
If the last verify isn't `verified`: `⚠ Tests have NOT passed for this build.`
Under cron or gateway runs with nobody to answer, Hermes's approval policy applies; the tool must
not wait forever. VERIFY how a denial is reported, so the tool can return a clear result.

## Hooks available (from the hooks reference)
`pre_tool_call` (tool_name, args, task_id …), `post_tool_call`, `pre_llm_call` (can add context),
`post_llm_call`, `on_session_start`, `on_session_end`. All callbacks must accept `**kwargs`.

## Catalog admission rules (summary; full text at the submission URL)
1. PR to `NousResearch/hermes-agent`; maintainer merges.
2. Pin a 40-char commit SHA.
3. No self-updating code.
4. SHA bumps are new PRs.
5. Submit as owner or major contributor.
6. **Declared capabilities = registered capabilities.**
7. The install security scan must not be `dangerous`; `caution` findings are shown to reviewers.
8. Desktop plugins use the SDK only (no prototype patching, no eval, no reaching into app markup).
9. No runtime overrides of Hermes core.
10. **Dependencies: floor plus upper bound.**
11. **Credentials only through Hermes** (`get_secret`, `config_schema` secrets).
12. **Respect approvals; never auto-approve; fail or time out cleanly when unattended.**
13. **Disclose risky behaviour** in README and PR (network, subprocess, background, serial, cloud).
14. Truthful `requires_hermes` floor in both plugin.yaml and the catalog entry; `version` matches the code.
15. No skins or forks of bundled plugins.
16. One listing per lineage.
17. **No unscannable binaries** (no ELF/PE/Mach-O/wasm/.pyc/opaque archives) in the repo. Don't
    commit `build/` outputs or `.bin`/`.elf`/`.hex` files.
18. Password-manager rule (not relevant).

## Catalog entry: `plugin-catalog/boardloop.yaml`
```yaml
name: boardloop
repo: https://github.com/<you>/boardloop
sha: <40-hex release commit>
subdir: ""
title: BoardLoop
description: "<one line>. Disclosure — <text from 10-security-and-disclosure.md>"
maintainer: <GitHubName>
tier: community
category: tools
requires_hermes: ">=X.Y.Z"
docs_url: https://github.com/<you>/boardloop#readme
version: "0.1.0"
image: https://raw.githubusercontent.com/<you>/boardloop/<sha>/assets/banner.png   # 2:1, e.g. 1200x600
screenshots:                                                                       # up to 6, pinned to the sha
  - https://raw.githubusercontent.com/<you>/boardloop/<sha>/assets/test-results.png
platforms: []
capabilities:
  provides_tools: [mcu_doctor, mcu_project_new, ...]   # same list as plugin.yaml
  provides_hooks: [pre_tool_call]
  provides_middleware: []
  requires_env: []          # VERIFY: list WOKWI_CLI_TOKEN here if the schema expects secret env names
```
Categories allowed: desktop, memory, platform, web, tools, voice, automation, models, general.
