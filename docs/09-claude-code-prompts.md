# 09: Claude Code prompts (copy and paste, one per phase)

Run `claude` in the repo root (`CLAUDE.md` loads automatically). After each phase: check the
checkpoint in `08-build-plan.md`, ask Claude to commit, then `/clear`.

---

## Prompt 0: Orientation
```
Read CLAUDE.md, every file in docs/, and the three projects in examples/. Then:
1. Summarise BoardLoop in 5 lines.
2. Check my environment and report versions or missing pieces: python, pytest, pyyaml, pyserial,
   hermes (--version, `hermes plugins --help`), arduino-cli (version, `core list`, `lib list`),
   wokwi-cli (--help), and whether WOKWI_CLI_TOKEN is set (don't print it), plus git status.
3. Read tests/fixtures/wokwi/NOTES.md if it exists (my answers to the VERIFY list in
   docs/07-wokwi-guide.md). List any VERIFY items still open and how you'll resolve each.
4. List the files you'll create per phase, matching docs/04-architecture.md.
Don't write code yet. Wait for my OK.
```

## Prompt 0b (optional): Answer the Wokwi VERIFY list with me
```
Help me answer the VERIFY list in docs/07-wokwi-guide.md using real runs on examples/thermostat,
spending as few Wokwi minutes as possible (timeouts of 6000 ms or less). For each item: give me the
exact command, I'll run it and paste the output, then you record the answer and the raw output in
tests/fixtures/wokwi/ (NOTES.md plus one .txt per case with the exit code on the first line).
Compile the sample first with arduino-cli if build/ is missing.
```

## Prompt 1: Core modules + fakes
```
Build Phase 1 from docs/08-build-plan.md, exactly as specified in docs/04-architecture.md.
Modules: config.py, procs.py, projects.py, scenario.py, compiler.py, simulator.py, usage.py,
storage.py. Plus tests/fakes/fake_arduino_cli.py and tests/fakes/fake_wokwi_cli.py as described in
docs/11-testing.md, and unit tests for every module.
Requirements:
- No Hermes imports in these modules (storage.py takes a sqlite3 connection; config.py takes a
  settings dict), so they're testable without Hermes.
- scenario.py is a pure function: (project config, test dict) → YAML string. Follow the step format
  in docs/04 and the key names recorded in tests/fixtures/wokwi/NOTES.md (name vs control/pin).
- compiler.py parses GCC errors using real samples: compile examples/thermostat-buggy with
  arduino-cli if available and save stderr to tests/fixtures/gcc/buggy.txt; also hand-write fixtures
  for a missing header, an undeclared identifier and a wrong FQBN.
- simulator.py classifies results using tests/fixtures/wokwi/*.txt.
- projects.py: path safety (reject escapes and symlinks out), name rules, yaml validation, parts and
  wiring table, template copy with consistent renaming (folder, .ino, wokwi.toml, yaml).
Run pytest until green. Show me the test summary and what's still unverified.
```

## Prompt 2: Plugin skeleton + doctor, project, libraries, compile
```
Build Phase 2 from docs/08-build-plan.md. Read docs/05-hermes-plugin-reference.md first; for every
item marked VERIFY there, fetch the Hermes docs page given and confirm names and signatures
(register_tool, register_hook, register_command, register_skill, config_schema types, the pip
dependency key, external_dependencies). Tell me what you found before coding.
Then create plugin.yaml, __init__.py, schemas.py, tools.py and templates/ (copied from examples/:
esp32-thermostat from thermostat, uno-blink from blink-uno, and esp32-blank as a minimal ESP32
sketch printing BOOT OK with an empty test list) plus skills/boardloop/SKILL.md (stub).
Tools now: mcu_doctor, mcu_project_new, mcu_project_info, mcu_libraries, mcu_compile.
- One TOOLS table drives both register() and plugin.yaml; add a test that fails if they differ.
- Settings via ctx.get_config; the Wokwi token via get_secret (doctor only checks it exists).
- Handlers never raise; outputs match docs/04.
Tests: handler tests with fakes. Run pytest, then `hermes plugins doctor . --ci` if Hermes is
installed, and fix everything. Tell me how to link the plugin into Hermes and what to ask Hermes to
check it.
```

## Prompt 3: Simulation + test runner + usage meter
```
Build Phase 3 from docs/08-build-plan.md: mcu_simulate, testrunner.py, mcu_test, run-dir handling
and cleanup, and the usage meter, all per docs/04-architecture.md.
- Each test runs in its own run dir with a patched diagram.json (sensors → attrs as strings) and a
  generated scenario.yaml; copy only the files wokwi.toml needs.
- Failure reasons must be human-readable ("expected led1:A = 1, got 0",
  "expected serial 'LED=ON' not seen"); keep raw_reason too.
- Bound everything: timeouts per docs/04, at most 60 serial lines returned, at most 20 tests.
- Record sim_ms for every run in storage and include wokwi_minutes_30d in results.
Unit tests with the fake wokwi-cli. Then give me the exact Hermes prompts to run the real Wokwi
checkpoints from the build plan (they use about 1–2 Wokwi minutes), and tell me what to look for.
```

## Prompt 4: Verify loop, history, /mcu, skill
```
Build Phase 4 from docs/08-build-plan.md: loop.py + mcu_verify (budgets, statuses fix_compile /
fix_behaviour / verified / needs_human / needs_tests, reset), history rows, the /mcu command
(status, projects, history <p>, doctor), and the full skills/boardloop/SKILL.md per docs/03 F11.
The skill must teach this workflow:
mcu_project_info → edit files → mcu_verify → on fix_compile fix only the reported errors → on
fix_behaviour read the reasons and serial tail, fix the logic, and run only the failing tests with
mcu_test `only` while iterating → final mcu_verify → report with screenshots → offer mcu_upload only
if the user has a board, and always explain what will be flashed.
It must also teach how to write tests from a request: normal case, edge case, opposite case;
machine-readable serial lines; a boot line; ESP32 pin rules; library choices; and never inventing
part ids (read diagram.json via mcu_project_info).
Unit-test loop.py thoroughly with fakes (budget exhaustion, reset, needs_tests).
Then give me the exact demo prompt for thermostat-buggy and a checklist for watching it run.
```

## Prompt 5: Real board + wiring check (P1)
```
Build Phase 5 from docs/08-build-plan.md: mcu_ports, mcu_upload, mcu_serial_read, mcu_serial_write
and mcu_wiring_check, per docs/04 and docs/10.
- approvals.py: pre_tool_call returns the approve dict for mcu_upload and mcu_serial_write. The
  message includes the project, board, port, firmware size and the last verify status (with a
  warning if not verified).
- Validate ports against the mcu_ports list and the regex in docs/04. pyserial is imported lazily
  with a clear error if it's missing.
- Add a test that fails if any tool whose name contains upload/write/flash/erase is missing from
  the approval set.
- I <have / don't have> a real board: <port, e.g. /dev/ttyUSB0 or COM5>. If I don't, keep these
  tools out of plugin.yaml and register() behind a setting `enable_real_board` (default false), and
  tell me what you couldn't test.
Run pytest and doctor.
```

## Prompt 6: Polish, README, compliance
```
Build Phase 6 from docs/08-build-plan.md.
1. Write README.md for users (replace the kit README; follow the outline in
   docs/12-demo-and-submission.md), including the research table from docs/02, the "related plugins"
   note from docs/01, the disclosures from docs/10 and the limitations.
2. .gitignore per docs/04; MIT LICENSE with my name; make sure no build outputs, .bin/.elf/.hex,
   tokens or screenshots of private things are tracked (git ls-files check).
3. plugin.yaml: provides_tools equals registered tools; requires_hermes = my Hermes version floor;
   version 0.1.0; dependencies with bounds.
4. Run `hermes plugins validate . --install-deps`; fix every failure; list every warning with your
   view on it.
5. Tell me exactly which screenshots to take for assets/ and the README (doctor, test table, OLED
   screenshot, verify result), and make a simple 1200x600 banner (SVG → PNG with Python if possible,
   otherwise give me text for a design tool).
6. Do a fresh-install walk-through from the README in a temp HERMES_HOME if possible, and report
   anything confusing.
```

## Prompt 7 (stretch): Desktop Workbench pane
```
Read https://hermes-agent.nousresearch.com/docs/developer-guide/desktop-plugin-sdk fully. If a
Desktop pane can show data from this plugin within catalog rule 8 (SDK only, no eval, no app-markup
access), build a small "Workbench" pane: project picker, the latest test results table, the latest
OLED screenshot, the serial tail and the Wokwi minutes. Keep it small and robust. If it isn't
feasible in about 1 hour, stop and tell me. Re-run doctor and validate afterwards.
```

## Prompt 8: Release and catalog PR
```
Help me release and submit (docs/08 Phase 8 and docs/12).
1. Confirm pytest, doctor and validate are green. Commit and push. Print the full 40-char SHA.
2. Tag v0.1.0 and push the tag.
3. Draft plugin-catalog/boardloop.yaml from the docs/05 template with the real SHA, the image and
   screenshot URLs pinned to that SHA, and the exact provides_tools list.
4. Draft the PR title and body from docs/12, filled in.
5. Walk me through forking NousResearch/hermes-agent and opening the PR (gh if installed and
   logged in, otherwise the exact web steps). Show me the final text before anything is submitted.
```

## Useful one-liners
- "Run all tests and doctor; fix anything failing."
- "Review the code for any path that runs a shell or builds argv from unvalidated input."
- "Review for any way mcu_upload could run without the approval hook."
- "Estimate how many Wokwi minutes the demo uses and how to cut that."
- "Make every error message understandable to a beginner."
