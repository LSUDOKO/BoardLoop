import { motion, useReducedMotion } from 'framer-motion'
import { useState } from 'react'
import Liquid from './Liquid.jsx'
import Session from './Session.jsx'
import Traces from './Traces.jsx'

const REPO = 'https://github.com/LSUDOKO/BoardLoop'

const Icon = {
  chip: (
    <svg viewBox="0 0 26 26" fill="none" stroke="currentColor" strokeWidth="2"><rect x="4" y="4" width="18" height="18" rx="3" /><rect x="9" y="9" width="8" height="8" rx="1.5" /><path d="M9 1v3M13 1v3M17 1v3M9 22v3M13 22v3M17 22v3M1 9h3M1 13h3M1 17h3M22 9h3M22 13h3M22 17h3" /></svg>
  ),
  check: (
    <svg viewBox="0 0 26 26" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="13" cy="13" r="11" /><path d="M8 13.5l3.5 3.5L18.5 9.5" stroke="#5cf29b" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
  ),
  github: (
    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 .5a11.5 11.5 0 0 0-3.6 22.4c.6.1.8-.3.8-.6v-2c-3.2.7-3.9-1.5-3.9-1.5-.5-1.3-1.3-1.7-1.3-1.7-1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.4 1 .1-.8.4-1.3.8-1.6-2.6-.3-5.3-1.3-5.3-5.7 0-1.3.5-2.3 1.2-3.1-.1-.3-.5-1.5.1-3.1 0 0 1-.3 3.2 1.2a11 11 0 0 1 5.8 0c2.2-1.5 3.2-1.2 3.2-1.2.6 1.6.2 2.8.1 3.1.8.8 1.2 1.8 1.2 3.1 0 4.4-2.7 5.4-5.3 5.7.4.4.8 1.1.8 2.2v3.2c0 .3.2.7.8.6A11.5 11.5 0 0 0 12 .5Z" /></svg>
  ),
  play: <svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 4.5v15l13-7.5z" /></svg>,
  shield: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2.5 4 5.5v6c0 5 3.4 8.8 8 10 4.6-1.2 8-5 8-10v-6z" /><path d="m8.5 12 2.5 2.5 4.5-5" /></svg>,
  key: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="8" cy="15" r="4.5" /><path d="m11.5 11.5 9-9M17 6l3 3M14.5 8.5l2 2" /></svg>,
  terminal: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2.5" y="4" width="19" height="16" rx="3" /><path d="m7 9 3 3-3 3M12.5 15h4.5" /></svg>,
  meter: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 18a8 8 0 1 1 16 0" /><path d="m12 18 4-6" /></svg>,
}

function Module() {
  // An ESP32 module, drawn to match the brand artwork.
  const pads = Array.from({ length: 12 }, (_, i) => i)
  return (
    <svg className="hero-module" viewBox="-60 -40 640 760" aria-hidden="true">
      <defs>
        <linearGradient id="pcb" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#14703c" /><stop offset="1" stopColor="#0a4224" /></linearGradient>
        <linearGradient id="shield" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#d9e0dc" /><stop offset=".5" stopColor="#aeb8b3" /><stop offset="1" stopColor="#8c9792" /></linearGradient>
        <linearGradient id="gold" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#f0cf7a" /><stop offset="1" stopColor="#b8892f" /></linearGradient>
      </defs>
      <g transform="translate(150 -20) rotate(26)">
        <rect width="330" height="560" rx="18" fill="url(#pcb)" stroke="#22d672" strokeOpacity=".55" strokeWidth="2.5" />
        {pads.map(i => <rect key={`l${i}`} x="-6" y={60 + i * 38} width="16" height="14" rx="7" fill="url(#gold)" />)}
        {pads.map(i => <rect key={`r${i}`} x="320" y={60 + i * 38} width="16" height="14" rx="7" fill="url(#gold)" />)}
        <rect x="40" y="46" width="250" height="250" rx="14" fill="#6d7873" />
        <rect x="46" y="52" width="238" height="238" rx="10" fill="url(#shield)" />
        {[26, 48, 70].map(r => <path key={r} d={`M${165 - r} 215 A${r} ${r} 0 0 1 ${165 + r} 215`} fill="none" stroke="#8f9a95" strokeWidth="8" strokeLinecap="round" />)}
        <circle cx="165" cy="215" r="8" fill="#8f9a95" />
        {Array.from({ length: 8 }, (_, i) => (
          <g key={i} transform={`translate(${60 + (i % 4) * 58} ${360 + Math.floor(i / 4) * 40})`}>
            <rect width="26" height="14" rx="2" fill="#1d1f1e" /><rect x="2" y="3" width="6" height="8" fill="#b9a06a" /><rect x="18" y="3" width="6" height="8" fill="#b9a06a" />
          </g>
        ))}
      </g>
    </svg>
  )
}

function Hero() {
  const reduce = useReducedMotion()
  const rise = (delay) => ({
    initial: { opacity: reduce ? 1 : 0, y: reduce ? 0 : 16 },
    animate: { opacity: 1, y: 0 },
    transition: { delay: reduce ? 0 : delay, duration: 0.7, ease: [0.2, 0.8, 0.2, 1] },
  })
  return (
    <header className="hero" id="top">
      <Traces />
      <div className="hero-glow" />
      <motion.div initial={{ opacity: 0, x: reduce ? 0 : 60 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: reduce ? 0 : 0.6, duration: 1 }}>
        <Module />
      </motion.div>
      <div className="hero-content">
        <motion.img className="hero-logo" src="/logo.svg" alt="BoardLoop" width="1200" height="200" {...rise(0.9)} />
        <motion.div className="pills" {...rise(1.15)}>
          <span className="pill">{Icon.chip} Compiles it</span>
          <span className="pill">{Icon.check} Proves it works</span>
        </motion.div>
        <motion.h1 {...rise(1.35)}>
          A Hermes plugin that tests ESP32 and Arduino code on a simulated circuit, fixes what fails, and flashes your board when you say so.
        </motion.h1>
        <motion.div className="cta-row" {...rise(1.5)}>
          <Liquid primary href="#install">{Icon.terminal} Install BoardLoop</Liquid>
          <Liquid href="#session">{Icon.play} Watch it fix a bug</Liquid>
          <Liquid href={REPO} target="_blank" rel="noreferrer">{Icon.github} GitHub</Liquid>
        </motion.div>
        <motion.p className="hero-note" {...rise(1.6)}>Open source · MIT · Hermes 0.23 or newer</motion.p>
      </div>
    </header>
  )
}

const STAGES = [
  { t: 'Compile', p: 'arduino-cli builds the sketch. Errors come back located, with the line above for context and a fix hint.',
    a: "thermostat-buggy.ino:24:1\nexpected ',' or ';'\nhint: a statement just above\nthis line is missing a ';'" },
  { t: 'Simulate', p: 'Each test runs in its own copy of the circuit on Wokwi, with sensor values patched in.',
    a: 'sensors:\n  dht1: { temperature: 35 }\nrun_ms: 3000' },
  { t: 'Test', p: 'Serial lines, pin levels and OLED screenshots are checked, and failures read like a person wrote them.',
    a: 'expected led1:A = 1, got 0\nled1:A is wired to esp:26' },
  { t: 'Fix', p: 'The agent fixes the logic and tries again, within 3 compile and 5 behaviour attempts. Then it stops and asks you.',
    a: 'fix_behaviour  1/5\n…\nverified  3/3' },
  { t: 'Flash', p: 'With a board plugged in, flashing and serial writes wait for your approval in Hermes.',
    a: 'Flash "thermostat" (esp32,\n2 KB) to /dev/ttyUSB0.\nTests: 3/3 passed.  [y/n]' },
]

const TOOL_GROUPS = [
  { h: 'Write and build', items: [
    ['mcu_project_new', 'Start from a template: blank ESP32, thermostat, Uno blink, or the buggy demo.'],
    ['mcu_project_info', 'Parts and wiring of the circuit, so code matches the board.'],
    ['mcu_libraries', 'Find and install Arduino libraries.'],
    ['mcu_compile', 'Compile with readable errors and fix hints.'],
    ['mcu_wiring_check', 'Catch input-only pins, missing resistors and parts without ground.'],
  ] },
  { h: 'Simulate and test', items: [
    ['mcu_verify', 'The loop: compile, run every test, return one status with an attempt budget.'],
    ['mcu_test', 'Behaviour tests on Wokwi: sensors, buttons, serial, pins, screenshots.'],
    ['mcu_simulate', 'One run of the firmware with a serial tail and a part screenshot.'],
    ['mcu_export', 'Open the same circuit in the wokwi.com editor and watch it live.'],
    ['mcu_doctor', 'Check the toolchain and get the exact command for anything missing.'],
  ] },
  { h: 'Real board', items: [
    ['mcu_ports', 'List connected boards.'],
    ['mcu_upload', 'Flash the board after you approve.', true],
    ['mcu_test target=real', 'Flash, reset and check the serial lines on hardware.', true],
    ['mcu_serial_read', 'Read what the board prints.'],
    ['mcu_serial_write', 'Send the board a command after you approve.', true],
  ] },
]

const SAFETY = [
  [Icon.shield, 'You approve every write to hardware', 'Flashing and serial writes go through Hermes approvals. With nobody there to answer, Hermes refuses them.'],
  [Icon.key, 'Your Wokwi token stays secret', 'Read from Hermes secrets, passed only to wokwi-cli, and removed from every tool result.'],
  [Icon.terminal, 'No shell, bounded runs', 'Fixed commands with timeouts that stop the whole process tree; at most 10 errors and 60 serial lines reach the model.'],
  [Icon.meter, 'Wokwi minutes you can see', 'A meter in /mcu and the Desktop pane; tests run in parallel and stop as soon as they pass.'],
]

function Install() {
  const [copied, setCopied] = useState(false)
  const cmd = 'hermes plugins install LSUDOKO/BoardLoop --enable'
  return (
    <div className="terminal">
      <div className="titlebar">
        <div className="dots"><i /><i /><i /></div><span>terminal</span>
        <button className="copy" onClick={() => navigator.clipboard?.writeText(cmd).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1600) })}>
          {copied ? 'Copied' : 'Copy install command'}
        </button>
      </div>
      <pre>
        <span className="c"># 1. the plugin</span>{'\n'}<span className="p">$</span> {cmd}{'\n\n'}
        <span className="c"># 2. the toolchain (arduino-cli + wokwi-cli are installed by you)</span>{'\n'}
        <span className="p">$</span> arduino-cli core install esp32:esp32 arduino:avr{'\n'}
        <span className="p">$</span> arduino-cli lib install "Adafruit SSD1306" "DHT sensor library"{'\n\n'}
        <span className="c"># 3. add your free Wokwi CI token in Settings → Plugins → BoardLoop, then in Hermes:</span>{'\n'}
        <span className="p">›</span> /mcu doctor
      </pre>
    </div>
  )
}

export default function App() {
  return (
    <>
      <a href="#session" className="sr-only" style={{ position: 'absolute', left: -9999 }}>Skip to the demo</a>
      <nav className="nav">
        <div className="wrap nav-inner">
          <a href="#top" aria-label="BoardLoop home"><img className="nav-logo" src="/logo.svg" alt="BoardLoop" width="186" height="30" /></a>
          <div className="nav-links">
            <a href="#session">See it work</a><a href="#loop">How it works</a><a href="#tools">Tools</a><a href="#safety">Safety</a>
          </div>
          <Liquid primary href="#install" style={{ padding: '10px 18px', fontSize: 15 }}>Install</Liquid>
        </div>
      </nav>
      <Hero />
      <main>
        <section id="session">
          <div className="wrap">
            <h2 className="section-title">Watch Hermes fix a broken thermostat</h2>
            <p className="section-lead">
              One prompt. Hermes reads the circuit, fixes a missing semicolon and a reversed comparison, survives a dropped
              Wokwi connection, and stops only when all three tests pass on the simulated board.
            </p>
            <Session />
          </div>
        </section>

        <section id="loop">
          <div className="wrap">
            <h2 className="section-title">The loop research says AI needs</h2>
            <p className="section-lead">Models write firmware that looks right and fails on the board. BoardLoop gives Hermes the board, simulated or real, and a budget so it can't loop forever.</p>
            <div className="loop">
              {STAGES.map((s, i) => (
                <div className="stage" key={s.t}>
                  <div className="stage-node"><span className="stage-dot">{i + 1}</span>{i < STAGES.length - 1 && <span className="stage-line" />}</div>
                  <h3>{s.t}</h3>
                  <p>{s.p}</p>
                  <div className="artifact">{s.a}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section>
          <div className="wrap facts">
            <div className="fact">
              <div className="num">55.6<small>%</small></div>
              <p>The best model's pass rate on 126 embedded tasks without hardware feedback.</p>
              <a href="https://arxiv.org/abs/2506.11003" target="_blank" rel="noreferrer">EmbedAgent, ICSE 2026</a>
            </div>
            <div className="fact">
              <div className="num">95.7<small>%</small></div>
              <p>Coding accuracy with compile → fix ×3 → run → fix ×5, the budgets BoardLoop uses.</p>
              <a href="https://arxiv.org/abs/2412.09058" target="_blank" rel="noreferrer">EmbedGenius, 2024</a>
            </div>
            <div className="fact">
              <div className="num">25<small>→</small>100<small>%</small></div>
              <p>Beginners' success on a sensor task once they had hardware-in-the-loop feedback.</p>
              <a href="https://arxiv.org/abs/2307.03817" target="_blank" rel="noreferrer">Englhardt et al., UW</a>
            </div>
          </div>
        </section>

        <section id="tools">
          <div className="wrap">
            <h2 className="section-title">Fourteen tools, one plugin</h2>
            <p className="section-lead">Plus a <code>/mcu</code> command, a skill that teaches Hermes how to write tests, and a Workbench pane for Hermes Desktop.</p>
            <div className="tool-groups">
              {TOOL_GROUPS.map(g => (
                <div className="tool-group" key={g.h}>
                  <h3><span />{g.h}</h3>
                  <ul className="tool-list">
                    {g.items.map(([n, d, lock]) => (
                      <li key={n}><code>{n}</code>{lock && <span className="lock">asks first</span>}<p>{d}</p></li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section>
          <div className="wrap">
            <h2 className="section-title">Real runs, not mockups</h2>
            <p className="section-lead">Every image here came out of BoardLoop's own test runs and the wokwi.com editor.</p>
            <div className="proof">
              <figure><img src="/verify-result.png" alt="Three verify attempts and two real OLED screenshots" loading="lazy" /><figcaption>The OLED at 35 °C and 20 °C, captured during BoardLoop's test run.</figcaption></figure>
              <figure><img src="/wokwi/hot.png" alt="The thermostat running live on wokwi.com" loading="lazy" style={{ background: '#ddd' }} /><figcaption>The same circuit exported with mcu_export and running in the browser.</figcaption></figure>
            </div>
          </div>
        </section>

        <section id="safety">
          <div className="wrap">
            <h2 className="section-title">Careful with your hardware</h2>
            <p className="section-lead">Built to the Hermes catalog rules: public plugin surfaces only, declared capabilities, and nothing that runs on your board without you.</p>
            <div className="safety">
              {SAFETY.map(([icon, h, p]) => (
                <div key={h}>{icon}<span><h3>{h}</h3><p>{p}</p></span></div>
              ))}
            </div>
          </div>
        </section>

        <section id="install">
          <div className="wrap">
            <h2 className="section-title">Install in a minute</h2>
            <p className="section-lead">No board needed: everything runs in the Wokwi simulator. The free Wokwi plan covers about 160 full test runs a month.</p>
            <Install />
            <div className="cta-row" style={{ justifyContent: 'flex-start', marginTop: 28 }}>
              <Liquid primary href={REPO} target="_blank" rel="noreferrer">{Icon.github} Read the docs on GitHub</Liquid>
            </div>
          </div>
        </section>
      </main>
      <footer>
        <div className="wrap foot">
          <img src="/logo.svg" alt="BoardLoop" width="160" height="26" />
          <span>A Hermes Agent plugin. MIT licensed.</span>
          <nav><a href={REPO}>GitHub</a><a href={`${REPO}/releases`}>Releases</a><a href={`${REPO}/blob/main/SECURITY.md`}>Security</a></nav>
        </div>
      </footer>
    </>
  )
}
