# BoardLoop: Hackathon Project Kit

Everything Claude Code needs to build **BoardLoop**, a Hermes Agent plugin, for the Hermes Agent
Plugin Hackathon. Submissions are due **Nov 11, 5 PM EST = Nov 12, 3:30 AM IST**.

**BoardLoop** lets Hermes write code for ESP32 and Arduino boards, compile it, run it in the
**Wokwi** simulator, test it automatically (set sensor values, check LEDs and serial output,
screenshot the OLED), fix its own mistakes, and flash a real board when you approve.

---

## What's in the kit
| Path | Purpose |
|---|---|
| `CLAUDE.md` | Rules Claude Code reads automatically every session. **Keep it at the project root.** |
| `docs/01-hackathon.md` | Rules, prizes, deadline, judging, how to submit, competing entries |
| `docs/02-idea-and-problem.md` | Problem, solution, research numbers, why it's unique |
| `docs/03-features.md` | Every feature with priority (P0/P1/P2) and acceptance criteria |
| `docs/04-architecture.md` | Repo layout, every tool's input/output, project file format, test runner, fix loop, data model |
| `docs/05-hermes-plugin-reference.md` | Hermes plugin APIs used, manifest, catalog rules, catalog entry |
| `docs/06-dev-setup.md` | Install Hermes, Claude Code, arduino-cli + ESP32 core + libraries, wokwi-cli + token |
| `docs/07-wokwi-guide.md` | Verified Wokwi file formats, CLI flags, scenarios, free-minute budget, VERIFY list |
| `docs/08-build-plan.md` | Hour-by-hour plan for the 2.5 days left, with checkpoints |
| `docs/09-claude-code-prompts.md` | Copy-paste prompts for Claude Code, one per phase |
| `docs/10-security-and-disclosure.md` | Safety rules, threat model, ready-made disclosure text |
| `docs/11-testing.md` | Fake tools, unit/integration tests, manual checklist |
| `docs/12-demo-and-submission.md` | 90-second demo script, recording setup, X post, PR text, form |
| `examples/thermostat/` | Working ESP32 + OLED + DHT22 + LED project with tests |
| `examples/thermostat-buggy/` | Same project with a compile error and a logic bug, for the demo |
| `examples/blink-uno/` | Arduino Uno + button example (shows it isn't ESP32-only) |

The example sketches pass a C++ syntax check, and their JSON, TOML and YAML files are valid and
cross-referenced. They have **not** been compiled with the real ESP32 toolchain or run on Wokwi yet:
Step 2 below does that.

---

## Step by step

### Step 1: Install everything (tonight, about 45 min)
Follow `docs/06-dev-setup.md`. Summary:
1. Python 3.11+, Git, a GitHub account.
2. Hermes Agent (hermes-agent.nousresearch.com). Run `hermes` once.
3. Claude Code: `curl -fsSL https://claude.ai/install.sh | bash` (macOS/Linux/WSL) or
   `irm https://claude.ai/install.ps1 | iex` (Windows PowerShell). Check `claude --version`.
4. arduino-cli, the ESP32 core and the three libraries.
5. wokwi-cli plus a free Wokwi CI token in `WOKWI_CLI_TOKEN`.

### Step 2: Prove the toolchain works (15 min, do this before any coding)
```bash
cd examples/thermostat
arduino-cli compile --fqbn esp32:esp32:esp32 --output-dir build .
wokwi-cli . --timeout 5000 --expect-text "BOOT OK"
wokwi-cli . --timeout 6000 --scenario scenario-hot.yaml
```
Expected: the first command compiles; the second prints `BOOT OK` and exits 0. For the third,
edit the `dht1` temperature in `diagram.json` to `"35"` first, then the LED check passes and
`screenshots/hot.png` appears. Put the temperature back to `"24"` afterwards.

If anything fails, paste the error into Claude Code and fix the setup first. **Don't build on a
broken toolchain.**

### Step 3: Create the project repo
```bash
mkdir boardloop && cd boardloop && git init
# copy this whole kit in, then:
mv README.md KIT_README.md          # the plugin gets its own README later
git add . && git commit -m "Project kit: plan, docs, examples"
git branch -M main
git remote add origin https://github.com/<you>/boardloop.git    # create an empty public repo first
git push -u origin main
```

### Step 4: Start Claude Code
```bash
claude
```
Paste **Prompt 0** from `docs/09-claude-code-prompts.md`. Claude reads the kit, checks your tools,
and confirms the plan before writing code.

### Step 5: Build phase by phase
For each phase in `docs/08-build-plan.md`:
1. Paste its prompt.
2. Let Claude write the code **and run the tests**.
3. Do the phase checkpoint yourself.
4. Ask Claude to commit.
5. Type `/clear` and start the next phase.

### Step 6: Rehearse the demo (Nov 11 afternoon)
Run `docs/12-demo-and-submission.md`'s script end to end at least twice.

### Step 7: Submit (Nov 11, by 9 PM IST)
Tag the release, open the catalog PR, post the demo on X tagging @NousResearch, fill in the form.

---

## Golden rules
- **Toolchain check first.** Step 2 must pass before Phase 1.
- **P0 first.** The demo needs only: compile, simulate, test, verify loop, `/mcu`, skill, README.
  Real-board flashing and the Desktop panel are P1/P2.
- **Watch Wokwi minutes.** The free plan gives **50 simulated minutes per rolling 30 days**. Unit
  tests use the fake `wokwi-cli`; only run real simulations for checkpoints and the demo.
- **Never commit** your Wokwi token, `build/` folders or screenshots of anything private.
