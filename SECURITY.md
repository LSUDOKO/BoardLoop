# Security

## Threat model and mitigations

| Risk | Mitigation | Where | Test |
|---|---|---|---|
| Command injection via project names, ports, library names or test text | Fixed argv lists, `shell=False`, stdin closed; strict patterns for names (`^[a-z0-9][a-z0-9-]{0,40}$`), ports, libraries (`^[\w .+\-]{1,80}$`) and FQBNs; length caps; `yaml.safe_load` only | `procs.py`, `projects.py`, `tools.py`, `serialmon.py` | `test_procs.py::test_rejects_shell_strings`, `test_tools.py::test_libraries`, `test_serialmon.py::test_port_pattern` |
| Path traversal | Every project path resolves inside the workspace; `..`, absolute paths and escaping symlinks are refused; `wokwi.toml` firmware paths must stay inside the project | `projects.safe_child`, `testrunner.stage` | `test_projects.py::test_path_escape_blocked`, `::test_symlink_escape_blocked` |
| Runaway loops (tokens, Wokwi minutes) | Attempt budgets (3 compile, 5 behaviour) → `needs_human`; per-run simulated and wall-clock timeouts; ≤20 tests per project; minutes meter warns at 80% | `loop.py`, `scenario.py`, `usage.py` | `test_loop.py` |
| Hung processes | Wall-clock timeouts on every subprocess; the whole process group is killed | `procs.py` | `test_procs.py::test_timeout_kills_child_tree` |
| Flashing the wrong device or untested firmware | `mcu_upload` goes through the approval prompt, showing board, port, size and verify status; the port must be listed by `arduino-cli board list`; stale firmware is refused | `approvals.py`, `tools.mcu_upload` | `test_approvals.py`, `test_tools.py::test_ports_and_upload` |
| Prompt injection asking to flash or write serial | Approval prompt for upload and serial write; the skill and the tool output mark serial text as data, not instructions | `approvals.py`, `skills/boardloop/SKILL.md` | `test_approvals.py::test_guard_every_risky_tool_is_gated` |
| Token leaks | Read only via Hermes `get_secret`; passed only in wokwi-cli's environment; redacted from every tool result; never logged | `config.py`, `testrunner.Runner._env`, `tools._tool` | `test_config.py::test_redact_hides_tokens`, `test_tools.py::test_doctor_ready_with_fakes` |
| Code privacy | Only firmware, `diagram.json`, `wokwi.toml` and the scenario are in a Wokwi run folder; sources stay local | `testrunner.stage` | `test_testrunner.py::test_sensor_patch_only_touches_the_copy` |
| Unattended runs | Approval-gated tools are refused by Hermes's policy when nobody can answer; simulation is safe unattended | Hermes approvals | – |
| Binaries in the repo | `.gitignore` for build outputs; CI fails on tracked binaries, bytecode or tokens | `scripts/check_repo.py`, `.github/workflows/ci.yml` | CI |

## Rules the code follows

1. No `shell=True`, `eval`, `exec` or dynamic imports of user content.
2. No telemetry. Network use is only arduino-cli's own downloads (on request) and wokwi-cli's simulation calls.
3. No self-updating; BoardLoop never downloads or installs arduino-cli or wokwi-cli (`mcu_doctor` prints the install steps).
4. Hardware-touching tools (`mcu_upload`, `mcu_serial_write`) always require approval; there is no auto-approve path.
5. Model-facing output is bounded: ≤10 compiler errors, ≤60 serial lines, ≤8 library search results.

## Reporting a vulnerability

Please open a private security advisory on GitHub
(<https://github.com/LSUDOKO/BoardLoop/security/advisories/new>) rather than a public issue.
