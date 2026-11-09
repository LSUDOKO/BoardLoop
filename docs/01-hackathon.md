# 01: Hermes Agent Plugin Hackathon

Source: Nous Research's announcement on X (@NousResearch) and the Hermes docs.

## Key facts
- **Deadline:** Nov 11, 2026, **5:00 PM EST** = Nov 11, 22:00 UTC = **Nov 12, 3:30 AM IST**.
  Our target: **submit by Nov 11, 9 PM IST.**
- **Prize pool:** $20,000 cash plus extras. Any kind of plugin is eligible.
- **Accepted entries** get listed in the Hermes Marketplace for every Hermes user.

| Place | Prize |
|---|---|
| 1st | $10,000 + neon sign + merch + $1,000 credits |
| 2nd | $5,000 + neon sign + merch + $1,000 credits |
| 3rd | $2,500 + neon sign + merch + $1,000 credits |
| 4th | $1,500 + merch + $500 credits |
| 5th | $1,000 + merch + $500 credits |
| Runners-up (x5) | merch + $250 credits |

## Judging
- **The entry is the plugin itself.**
- Scored on **usefulness, reliability, polish, creativity**.
- They favour plugins that **do more than a prompt or a skill could**.
- Demo video **under 90 seconds**, showing the plugin **working**.

How BoardLoop scores:
| Criterion | BoardLoop |
|---|---|
| Usefulness | Makers, students and engineers; AI-written firmware usually fails without feedback from the board |
| Reliability | Every claim checked by a real compiler and a simulator; tests; fakes; bounded loops and timeouts |
| Polish | Clear tool outputs, OLED screenshots, test tables, `/mcu` status, Wokwi minute meter, good README |
| Creativity | The agent *proves* its hardware code works: it changes simulated sensor values and checks the LED itself |
| More than a prompt | Runs compilers, simulators and serial ports; generates test scenarios; tracks loop budgets. Impossible with a prompt |

## How to enter
1. **Pull request** adding `plugin-catalog/boardloop.yaml` to `NousResearch/hermes-agent`:
   https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/catalog-submission
2. **Demo video on X** (< 90 s), tagging **@NousResearch**.
3. **Form** with both links: https://form.typeform.com/to/FwJLvOln

The form can be submitted as soon as the PR is open. Catalog CI runs when a maintainer starts it.

## Links
- Developer guide: https://hermes-agent.nousresearch.com/docs/developer-guide/plugins
- Catalog README / entry schema: https://github.com/NousResearch/hermes-agent/blob/main/plugin-catalog/README.md
- Hooks: https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks
- Desktop SDK: https://hermes-agent.nousresearch.com/docs/developer-guide/desktop-plugin-sdk
- Discord: https://discord.gg/nousresearch

## Competing and neighbouring plugins (checked Nov 9, 2026)
The catalog had 1,377 entries; none compiles, simulates or flashes microcontroller code.
Related open hackathon PRs and catalog entries:

| Plugin | What it does | How BoardLoop differs |
|---|---|---|
| `gadget` (catalog) | ESP32 devices act as voice terminals for Hermes; updates its own firmware | We program the board with *new* code the agent writes and tests |
| `esp32-debug` (PR #151794, opened Nov 9) | Read-only: lists ports, chip info, captures and decodes crash backtraces; never flashes | We write, compile, simulate, test and flash. Complementary: mention it in the README and don't build crash decoding |
| `rigforge` (PR #149127) | Robot/machine design studio: 3D parts, servos, power, wiring, priced BOM, *generates* an Arduino sketch | It never compiles, runs or tests the sketch; we do |

README line to use: *"esp32-debug diagnoses crashes and rigforge designs the machine; BoardLoop makes
the code actually work on the board."*

**Re-check open PRs** before submitting:
https://github.com/NousResearch/hermes-agent/pulls?q=is%3Apr+arduino+OR+esp32+OR+wokwi+OR+firmware
