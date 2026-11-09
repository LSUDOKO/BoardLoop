# 02: The idea: BoardLoop

> **One line:** BoardLoop lets Hermes write microcontroller code, then **prove it works**:
> compile it, run it in a simulated circuit, change sensor values, check the LEDs, pins, serial
> output and screen, fix what's wrong, and flash a real board when you approve.

Tagline: **"Hermes doesn't just write hardware code. It proves it works."**

## The problem
1. **AI-written firmware usually fails.** Models write plausible Arduino code that doesn't compile,
   uses the wrong library, picks unusable pins, or has logic bugs you only see on the board.
2. **The model never sees the hardware.** In a normal chat, the code is never compiled or run,
   so every mistake becomes your debugging session.
3. **Testing hardware is manual and slow.** You'd need to heat the sensor to check "LED on above
   30°C". Nobody tests edge cases by hand.
4. **Beginners get stuck.** Students and hobbyists can't read cryptic compiler errors or work out
   why an OLED stays blank.
5. **Not everyone owns the hardware.** Without a board, you can't check anything at all.

## The solution
A Hermes plugin that gives the agent a real toolchain and a simulated workbench:
- **arduino-cli** to compile for ESP32, Arduino Uno and other boards, with errors parsed into
  short, fixable items.
- **Wokwi** (cloud simulator, `wokwi-cli`) to run the compiled firmware in a virtual circuit
  described by `diagram.json`: ESP32, OLED, DHT22, LEDs, buttons and more.
- **A test runner**: each test sets sensor values or presses buttons, runs the firmware, and checks
  serial output, pin states and OLED screenshots. The agent writes tests from the user's request,
  e.g. 35°C → LED on, 20°C → LED off, exactly 30°C → off.
- **A verify loop** that compiles, then tests, then returns one verdict plus what to fix, with
  attempt budgets (3 compile fixes, 5 behaviour fixes) taken from published research.
- **Real-board flashing and serial monitoring** with arduino-cli and pyserial, behind Hermes's
  approval prompt.

## Research backing (use in README and pitch)
| Study | Finding |
|---|---|
| **EmbedAgent** (ICSE 2026; arXiv 2506.11003): 126 embedded tasks on Arduino, ESP32, Raspberry Pi Pico | Best model only **55.6%** pass; **29.4%** on ESP-IDF tasks. Compiler feedback improved results. |
| **EmbedGenius** (arXiv 2412.09058, 2024): automated embedded IoT development | Compile → fix (max 3) → flash → read output → fix (max 5) reached **95.7% coding accuracy** across 4 platforms, 71 modules, 350+ tasks. |
| **Englhardt et al.** (University of Washington; arXiv 2307.03817) | Hardware-in-the-loop feedback raised **beginners' success from 25% to 100%** on a LoRa sensor task, including people with no C/C++ or hardware background. |

**Pitch:** *"Research shows AI fails at hardware without feedback from the board, and succeeds with
it. BoardLoop gives Hermes that feedback, in simulation for anyone and on real boards for makers."*

Links: https://arxiv.org/abs/2506.11003 · https://arxiv.org/abs/2412.09058 · https://arxiv.org/abs/2307.03817

## Why it is unique
- No catalog plugin (1,377 entries on Nov 9) compiles, simulates or flashes code.
- Open PRs `esp32-debug` (read-only crash triage) and `rigforge` (designs machines, generates but
  never runs sketches) are neighbours, not competitors. See `01-hackathon.md`.
- Automated *behaviour tests on simulated hardware*, run by the agent itself, is new.

## Who it's for
| User | Use |
|---|---|
| Student / beginner | "Make a temperature alarm": a working, tested project plus the wiring diagram |
| Maker | Iterate on ESP32 projects quickly, flash when the tests pass |
| Teacher | Students build and test without buying hardware; tests act as auto-grading |
| Engineer | Regression tests for firmware behaviour (simulated) before touching hardware |
| No hardware at all | Everything works in Wokwi; buy the board later |

## Limits (say these in the README)
- Wokwi is a cloud simulator: compiled firmware is uploaded to Wokwi. The free plan has **50
  simulated minutes per rolling 30 days**; heavy use needs a paid plan.
- Simulation ≠ reality: timing, power, noise and some peripherals differ. Real-board mode exists
  for the final check.
- Supported parts are whatever Wokwi simulates; scenario automation is "alpha" in Wokwi.
- arduino-cli, the board cores, wokwi-cli and the token are installed by the user.
