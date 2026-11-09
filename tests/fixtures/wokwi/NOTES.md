# Wokwi CLI behaviour (VERIFY list from docs/07-wokwi-guide.md)

**Source:** read from the wokwi-cli source code, `github.com/wokwi/wokwi-cli` at commit
`f23ed6fe2a8df332a9020fafb3c82b6ca95aa61c` (2026-10-23), files under `packages/cli/src/`.
**Status:** derived from source, *not yet recorded* from a real run. The JSON fixtures next to
this file reproduce the messages the source prints (colours stripped, as when stdout is not a
TTY). Re-record them with a real token: `BOARDLOOP_REAL=1 pytest -m real -k record`.

| # | Question | Answer | Where in the source |
|---|---|---|---|
| 1 | `--expect-text` found / timeout | found: stdout `Expected text found: "<t>"` + `TEST PASSED.`, exit **0**. Timeout: stderr `Timeout: simulation did not finish in <N>ms`, exit **42** (`--timeout-exit-code`) | `commands/simulate.ts` (expectEngine, `SimulationTimeoutError`) |
| 2 | `--fail-text` seen | stderr `Error: Unexpected text found: "<t>"` + `TEST FAILED.`, exit **1** | `commands/simulate.ts` (`ExitCodeError(1, ...)`) |
| 3 | `expect-pin` fails | `scenario.fail()` throws `Error("[<ns>ns] GPIO <part>:<pin> expected to be <v> but was <w>")`; `main.ts` prints it with `console.error(err)` and exits **1** | `scenario/ExpectPinCommand.ts`, `TestScenario.ts`, `main.ts` |
| 4 | Exit when the scenario ends? | **Yes.** `Promise.race` over the scenario, expect/fail text and the timeout; the scenario prints `Scenario completed successfully` and the CLI exits 0 | `commands/simulate.ts`, `TestScenario.start` |
| 5 | `take-screenshot` `save-to` base | Relative to the **scenario file's directory** (`path.dirname(resolvedScenarioFile)`); the scenario path itself is resolved against the project dir | `scenario/TakeScreenshotCommand.ts`, `commands/simulate.ts` |
| 6 | Key names | `set-control`: `part-id`, `name` (deprecated alias `control`), `value`. `expect-pin`: `part-id`, `name` (deprecated alias `pin`), `value`. BoardLoop emits `name` | `scenario/SetControlCommand.ts`, `scenario/ExpectPinCommand.ts` |
| 7 | Pushbutton control | `pressed`, values `1`/`0` (Wokwi pushbutton docs, "Simulator controls") | docs.wokwi.com/parts/wokwi-pushbutton |
| 8 | Simulated time printed? | No summary line. Failures carry `[<ns>ns]`; BoardLoop records the timeout as an upper bound and the `[ns]` value when present | `TestScenario.fail` |
| 9 | `wokwi-cli lint` path | `wokwi-cli lint [path]` (diagram.json or project dir, default `.`), `--offline`, `--warnings-as-errors` | `commands/lint.ts` |
| 10 | Missing / bad token | Missing: stderr `Error: Missing WOKWI_CLI_TOKEN environment variable. Please set it to your Wokwi token.` exit **1**. Rejected: `API Error: <message>` exit **1** | `utils/token.ts`, `commands/simulate.ts` |

Other facts used by BoardLoop:
- `wait-serial` that never matches simply waits until `--timeout` → exit 42.
- `delay` values need units (`3000ms`); a bare number is rejected at validation.
- Unknown step keys fail validation before the simulation starts (`Invalid scenario step key`).
- Firmware missing: stderr `Error: firmware file not found: <path>.`, exit 1.
