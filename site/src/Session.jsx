import { AnimatePresence, motion, useInView, useReducedMotion } from 'framer-motion'
import { useEffect, useMemo, useRef, useState } from 'react'
import session from './session.json'

// Pair each tool call with its result so one card shows both.
function steps(events) {
  const out = []
  for (let i = 0; i < events.length; i++) {
    const e = events[i]
    if (e.kind === 'call') {
      const next = events[i + 1]
      out.push({ kind: 'tool', tool: e.tool, args: e.args, result: next && next.kind === 'result' ? next.data : null })
      if (next && next.kind === 'result') i++
    } else if (e.kind !== 'result') {
      out.push(e)
    }
  }
  return out
}

function argText(tool, args) {
  if (tool === 'patch') return args.path
  if (tool === 'read_file') return args.path
  return Object.entries(args || {})
    .filter(([k]) => k !== 'goal')
    .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(' ')
}

function Result({ tool, r }) {
  if (!r) return null
  if (r.diff) {
    return (
      <div className="res">
        {r.diff.map((l, i) => (
          <div key={i} className={l.startsWith('-') ? 'del' : 'add'}>{l}</div>
        ))}
      </div>
    )
  }
  if (r.status) {
    return (
      <div className="res">
        <span className={`status ${r.status}`}>{r.status}</span>{' '}
        {r.status === 'verified' ? `${r.tests} tests passed on Wokwi · flash ${r.compile?.flash_used}` : r.message}
        {r.status === 'blocked' && <div className="args">network drop, not a code failure: no fix attempt spent</div>}
      </div>
    )
  }
  if (r.checks) return <div className="res">{r.checks.map(c => <div key={c} className="ok">✓ {c}</div>)}</div>
  if (r.parts) return <div className="res">parts: {r.parts.join(', ')} · {r.tests?.length} tests</div>
  if (r.lines) return <div className="res">{r.lines} lines read</div>
  if (r.project) return <div className="res ok">created {r.project} ({r.fqbn})</div>
  return <div className="res">{JSON.stringify(r).slice(0, 120)}</div>
}

function AgentText({ text }) {
  const clean = text.split('\n').filter(l => !l.startsWith('MEDIA:')).join('\n').trim()
  const parts = clean.split(/(`[^`]+`)/g)
  return (
    <div className="msg-agent">
      {parts.map((p, i) => (p.startsWith('`') ? <code key={i}>{p.slice(1, -1)}</code> : <span key={i}>{p}</span>))}
      {'\n'}
      <span className="args">+ 2 OLED screenshots from the simulated board</span>
    </div>
  )
}

const TESTS = [
  { name: 'hot room turns the LED on', frame: 'hot', detail: 'DHT22 at 35 °C → LED=ON, led1:A = 1' },
  { name: 'cool room keeps the LED off', frame: 'cool', detail: 'DHT22 at 20 °C → LED=OFF, led1:A = 0' },
  { name: 'exactly 30 C is not too hot', frame: null, detail: 'DHT22 at 30 °C → LED=OFF' },
]

export default function Session() {
  const all = useMemo(() => steps(session.events), [])
  const ref = useRef(null)
  const chatRef = useRef(null)
  const inView = useInView(ref, { once: true, amount: 0.35 })
  const reduce = useReducedMotion()
  const [shown, setShown] = useState(reduce ? all.length : 0)
  const [run, setRun] = useState(0)
  const [view, setView] = useState('hot')

  useEffect(() => {
    if (!inView || reduce) return
    if (shown >= all.length) return
    const cur = all[shown]
    const wait = shown === 0 ? 500 : cur.tool === 'mcu_verify' ? 2200 : cur.kind === 'assistant' ? 1400 : 1000
    const t = setTimeout(() => setShown(s => s + 1), wait)
    return () => clearTimeout(t)
  }, [inView, shown, all, reduce, run])

  useEffect(() => {
    const el = chatRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [shown])

  const visible = all.slice(0, shown)
  const verified = visible.some(s => s.result?.status === 'verified')
  const verifying = all[shown]?.tool === 'mcu_verify' && inView && shown < all.length
  const frame = verified ? view : verifying ? 'boot-hot' : 'boot'
  const frameLabel = verified
    ? view === 'hot' ? 'hot room test · DHT22 35 °C' : 'cool room test · DHT22 20 °C'
    : verifying ? 'running tests on Wokwi…' : 'waiting for firmware'

  return (
    <div ref={ref}>
      <div className="session">
        <div className="window" aria-label="Hermes chat">
          <div className="titlebar">
            <div className="dots"><i /><i /><i /></div>
            <strong>Hermes</strong>
            <span className="grow" />
            <span className="chip">boardloop plugin</span>
          </div>
          <div className="chat" ref={chatRef} aria-live="polite">
            <AnimatePresence initial={false}>
              {visible.map((s, i) => (
                <motion.div key={`${run}-${i}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }} style={{ display: 'contents' }}>
                  {s.kind === 'user' && <div className="msg-user">{s.text}</div>}
                  {s.kind === 'assistant' && <AgentText text={s.text} />}
                  {s.kind === 'tool' && (
                    <div className="tool">
                      <span className="name">{s.tool}</span> <span className="args">{argText(s.tool, s.args)}</span>
                      <Result tool={s.tool} r={s.result} />
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
            {verifying && <div className="tool"><span className="name">mcu_verify</span> <span className="args">compiling and simulating…</span></div>}
          </div>
        </div>

        <div className="window" aria-label="Simulated circuit">
          <div className="titlebar">
            <div className="dots"><i /><i /><i /></div>
            <strong>Wokwi</strong>
            <span className="args">ESP32 · DHT22 · SSD1306 · LED</span>
            <span className="grow" />
            <span className="chip">{frameLabel}</span>
          </div>
          <div className="board-pane">
            <AnimatePresence mode="wait">
              <motion.img key={frame} src={`/wokwi/${frame}.png`} alt={`Wokwi simulation: ${frameLabel}`}
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.35 }} />
            </AnimatePresence>
          </div>
          <div className="tests">
            {TESTS.map(t => (
              <div className="test-row" key={t.name}>
                <span className="mark" style={{ color: verified ? 'var(--trace-hi)' : 'var(--silk-3)' }}>{verified ? '✓' : '·'}</span>
                <span>{t.name}</span>
                <span className="args" style={{ marginLeft: 'auto', fontSize: 13 }}>{t.detail}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="session-foot">
        <p className="caption">
          A real Hermes session from {session.date} (Hermes {session.hermes}, wokwi-cli {session.wokwi_cli}), replayed. The tool calls and
          results come from the session log, shortened for display. The circuit frames are real Wokwi captures of the same firmware.
        </p>
        {verified && (
          <div className="seg" role="group" aria-label="Show test">
            <button aria-pressed={view === 'hot'} onClick={() => setView('hot')}>35 °C</button>
            <button aria-pressed={view === 'cool'} onClick={() => setView('cool')}>20 °C</button>
          </div>
        )}
        <button className="copy" onClick={() => { setShown(0); setRun(r => r + 1); setView('hot') }}>Replay</button>
      </div>
    </div>
  )
}
