import { motion, useReducedMotion } from 'framer-motion'
import { useMemo } from 'react'

// Deterministic PRNG so the board looks the same on every load.
function rng(seed) {
  let s = seed >>> 0
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296)
}

function buildTraces(w, h, count, seed) {
  const r = rng(seed)
  const pick = (a, b) => a + Math.floor(r() * (b - a + 1))
  const out = []
  for (let i = 0; i < count; i++) {
    const side = i % 4
    const step = [28, 36, 44][pick(0, 2)]
    const n = pick(2, 4)
    let pts
    if (side < 2) {
      const d = side === 0 ? 1 : -1
      let x = side === 0 ? -10 : w + 10
      pts = [[x, pick(30, h - 30)]]
      for (let k = 0; k < n; k++) {
        x += d * pick(70, 200)
        pts.push([x, pts[pts.length - 1][1]])
        const jog = (r() < 0.5 ? -1 : 1) * step
        pts.push([x + d * Math.abs(jog), pts[pts.length - 1][1] + jog])
        x += d * Math.abs(jog)
      }
    } else {
      const d = side === 2 ? 1 : -1
      let y = side === 2 ? -10 : h + 10
      pts = [[pick(30, w - 30), y]]
      for (let k = 0; k < n; k++) {
        y += d * pick(60, 160)
        pts.push([pts[pts.length - 1][0], y])
        const jog = (r() < 0.5 ? -1 : 1) * step
        pts.push([pts[pts.length - 1][0] + jog, y + d * Math.abs(jog)])
        y += d * Math.abs(jog)
      }
    }
    out.push({ d: 'M' + pts.map(p => p.join(',')).join(' L'), end: pts[pts.length - 1], bright: r() < 0.38 })
  }
  return out
}

/** The hero's circuit board: traces draw themselves in once, then a few signals travel along. */
export default function Traces({ width = 1600, height = 900 }) {
  const reduce = useReducedMotion()
  const traces = useMemo(() => buildTraces(width, height, 26, 7), [width, height])
  return (
    <svg className="hero-bg" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <defs>
        <filter id="tglow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="4" /></filter>
      </defs>
      {traces.map((t, i) => (
        <g key={i}>
          {t.bright && (
            <motion.path d={t.d} fill="none" stroke="#22d672" strokeWidth="8" strokeOpacity="0.32" filter="url(#tglow)"
              strokeLinejoin="round" initial={{ pathLength: reduce ? 1 : 0 }} animate={{ pathLength: 1 }}
              transition={{ duration: 1.6, delay: 0.1 + (i % 9) * 0.08, ease: [0.2, 0.8, 0.2, 1] }} />
          )}
          <motion.path d={t.d} fill="none" stroke={t.bright ? '#22d672' : '#1f7a46'} strokeOpacity={t.bright ? 0.95 : 0.5}
            strokeWidth="2.4" strokeLinejoin="round" strokeLinecap="round"
            initial={{ pathLength: reduce ? 1 : 0 }} animate={{ pathLength: 1 }}
            transition={{ duration: 1.6, delay: 0.1 + (i % 9) * 0.08, ease: [0.2, 0.8, 0.2, 1] }} />
          <motion.circle cx={t.end[0]} cy={t.end[1]} r="6" fill="#05200f" stroke={t.bright ? '#22d672' : '#1f7a46'}
            strokeWidth="2.4" initial={{ opacity: reduce ? 1 : 0 }} animate={{ opacity: 1 }}
            transition={{ delay: 1.4 + (i % 9) * 0.08 }} />
          {t.bright && !reduce && (
            <path d={t.d} fill="none" stroke="#c9ffe0" strokeWidth="3" strokeLinecap="round"
              pathLength="100" strokeDasharray="3 97" className="signal" style={{ animationDelay: `${2 + (i % 5) * 1.3}s` }} />
          )}
        </g>
      ))}
      <style>{`.signal{stroke-dashoffset:100;animation:signal 4.5s linear infinite;filter:drop-shadow(0 0 6px #5cf29b)}
        @keyframes signal{to{stroke-dashoffset:0}}`}</style>
    </svg>
  )
}
