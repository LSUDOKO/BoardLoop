// BoardLoop desktop half: draws the OLED / part screenshots that BoardLoop's own tools produce
// as a "simulated hardware" card with the test name, pass/fail and the reason.
//
// Uses only the public plugin SDK (catalog rule 8): no DOM reach-ins, no eval, no imports
// beyond @hermes/plugin-sdk and react. Any surprise falls back to the built-in image viewer.
import * as sdk from '@hermes/plugin-sdk'
import { useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const TOOLS = ['mcu_test', 'mcu_verify', 'mcu_simulate']

function parseResult(result) {
  if (result && typeof result === 'object') return result
  if (typeof result === 'string') {
    try {
      return JSON.parse(result)
    } catch {
      return null
    }
  }
  return null
}

// Find what this screenshot belongs to: a test result, a verify run, or a plain simulation.
function describe(toolName, result, path) {
  const r = parseResult(result) || {}
  const tests = Array.isArray(r.results) ? r.results : []
  const test = tests.find(t => t && t.screenshot === path)
  if (test) return { title: test.name, passed: !!test.passed, reason: test.reason || '' }
  if (toolName === 'mcu_verify' && Array.isArray(r.screenshots) && r.screenshots.includes(path)) {
    return { title: 'verified', passed: r.status === 'verified', reason: r.summary || '' }
  }
  if (toolName === 'mcu_simulate' && r.screenshot === path) {
    return { title: 'simulation', passed: !!r.passed, reason: r.reason || '' }
  }
  return null
}

function OledCard({ file, toolName, result, fallback }) {
  const [src, setSrc] = useState(null)
  useEffect(() => {
    let live = true
    file.resolveUrl().then(
      url => live && setSrc(url),
      () => live && setSrc('')
    )
    return () => {
      live = false
    }
  }, [file])

  const info = describe(toolName, result, file.path)
  if (file.kind !== 'image' || !info || src === '') return fallback

  const badgeColor = info.passed ? 'var(--ui-accent)' : 'var(--ui-text-secondary)'
  return jsxs('figure', {
    style: {
      margin: '4px 0',
      padding: '10px 12px',
      border: '1px solid var(--ui-stroke-secondary)',
      borderRadius: 10,
      display: 'inline-flex',
      flexDirection: 'column',
      gap: 8,
      maxWidth: 420
    },
    children: [
      jsxs('figcaption', {
        style: { display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 },
        children: [
          jsx('span', {
            style: { fontWeight: 600, color: badgeColor },
            children: info.passed ? '✓ PASS' : '✗ FAIL'
          }),
          jsx('span', { style: { color: 'var(--ui-text-secondary)' }, children: info.title }),
          jsx('span', {
            style: { marginLeft: 'auto', color: 'var(--ui-text-quaternary)', fontSize: 11 },
            children: 'Wokwi · ' + file.name
          })
        ]
      }),
      src &&
        jsx('img', {
          src,
          alt: 'Simulated display: ' + info.title,
          style: {
            imageRendering: 'pixelated',
            width: '100%',
            minWidth: 256,
            borderRadius: 4,
            background: '#000'
          }
        }),
      info.reason &&
        jsx('div', {
          style: { fontSize: 11, color: 'var(--ui-text-tertiary)', fontFamily: 'var(--font-mono, monospace)' },
          children: info.reason
        })
    ]
  })
}

export default {
  id: 'boardloop',
  name: 'BoardLoop',
  register(ctx) {
    // Older Desktops don't have the area: they keep the built-in image viewer.
    if (typeof sdk.TOOL_MEDIA_RENDERER_AREA !== 'string') return
    ctx.register({
      id: 'oled-card',
      area: sdk.TOOL_MEDIA_RENDERER_AREA,
      data: { tools: TOOLS, render: props => jsx(OledCard, props) }
    })
  }
}
