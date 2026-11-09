// BoardLoop desktop half:
// - a Workbench pane (projects, Wokwi minutes, latest simulated and real-board results with
//   screenshots, history), fed by dashboard/plugin_api.py and refreshed on results.updated;
// - a card that draws the OLED / part screenshots BoardLoop's own tools produce, with the test
//   name, pass/fail and the reason.
//
// Uses only the public plugin SDK (catalog rule 8): no DOM reach-ins, no eval, no imports
// beyond @hermes/plugin-sdk and react. Any surprise falls back to the built-in image viewer.
import * as sdk from '@hermes/plugin-sdk'
import { useCallback, useEffect, useState } from 'react'
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

// --- Workbench pane ------------------------------------------------------------------------------

const muted = { color: 'var(--ui-text-tertiary)' }
const faint = { color: 'var(--ui-text-quaternary)' }

function mark(passed, skipped) {
  if (skipped) return jsx('span', { style: faint, children: '–' })
  return jsx('span', {
    style: { color: passed ? 'var(--ui-accent)' : 'var(--ui-text-secondary)', fontWeight: 600 },
    children: passed ? '✓' : '✗'
  })
}

function Section({ title, children }) {
  return jsxs('section', {
    style: { display: 'flex', flexDirection: 'column', gap: 6 },
    children: [
      jsx('div', { style: { ...faint, fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.4 }, children: title }),
      children
    ]
  })
}

function Results({ block, title }) {
  if (!block) return null
  return jsx(Section, {
    title: `${title} · ${block.passed}/${block.total} passed · ${block.at}`,
    children: jsxs('div', {
      style: { display: 'flex', flexDirection: 'column', gap: 8 },
      children: block.results.map(r =>
        jsxs('div', {
          style: { display: 'flex', flexDirection: 'column', gap: 4 },
          children: [
            jsxs('div', {
              style: { display: 'flex', gap: 6, fontSize: 12 },
              children: [mark(r.passed, r.skipped), jsx('span', { children: r.name })]
            }),
            r.reason && !r.passed &&
              jsx('div', { style: { ...muted, fontSize: 11, fontFamily: 'var(--font-mono, monospace)' }, children: r.reason }),
            r.image &&
              jsx('img', {
                src: r.image,
                alt: 'Simulated display: ' + r.name,
                style: { imageRendering: 'pixelated', width: 256, borderRadius: 4, background: '#000' }
              }),
            r.serial_tail &&
              jsx('pre', {
                style: { ...muted, fontSize: 10, margin: 0, whiteSpace: 'pre-wrap' },
                children: r.serial_tail.join('\n')
              })
          ]
        }, r.name)
      )
    })
  })
}

function Workbench({ ctx }) {
  const [overview, setOverview] = useState(null)
  const [project, setProject] = useState('')
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState('')

  const refresh = useCallback(() => {
    ctx
      .rest('/overview')
      .then(data => {
        setError('')
        setOverview(data)
        setProject(current => current || (data.projects[0] && data.projects[0].name) || '')
      })
      .catch(e => setError('BoardLoop backend unavailable: ' + (e && e.message ? e.message : String(e))))
  }, [ctx])

  useEffect(() => {
    if (!project) return
    let live = true
    ctx.rest('/project/' + encodeURIComponent(project)).then(d => live && setDetail(d), () => live && setDetail(null))
    return () => {
      live = false
    }
  }, [ctx, project, overview])

  useEffect(() => {
    refresh()
    const stopPoll = ctx.setInterval(refresh, 15000) // fallback; the event below is the fast path
    const stopEvent = ctx.onEvent('plugin.boardloop.results.updated', refresh)
    return () => {
      stopPoll()
      stopEvent()
    }
  }, [ctx, refresh])

  const minutes = overview && overview.minutes
  const pct = minutes ? Math.min(100, Math.round((minutes.used / Math.max(minutes.limit, 1)) * 100)) : 0
  const last = overview && overview.projects.find(p => p.name === project)
  return jsxs('div', {
    style: { display: 'flex', flexDirection: 'column', gap: 14, padding: 12, fontSize: 12, height: '100%', overflow: 'auto' },
    children: [
      jsxs('div', {
        style: { display: 'flex', alignItems: 'center', gap: 8 },
        children: [
          jsx('strong', { children: 'BoardLoop' }),
          jsx('span', { style: faint, children: 'workbench' }),
          jsx('button', {
            type: 'button',
            onClick: refresh,
            style: { marginLeft: 'auto', ...muted, background: 'none', border: 'none', cursor: 'pointer' },
            children: '↻'
          })
        ]
      }),
      error && jsx('div', { style: muted, children: error }),
      minutes &&
        jsx(Section, {
          title: `Wokwi minutes (30 days, estimate) · ${minutes.used} / ${minutes.limit}`,
          children: jsx('div', {
            style: { height: 4, borderRadius: 2, background: 'var(--ui-stroke-secondary)' },
            children: jsx('div', {
              style: { width: pct + '%', height: 4, borderRadius: 2, background: 'var(--ui-accent)' }
            })
          })
        }),
      overview &&
        (overview.projects.length
          ? jsx('select', {
              value: project,
              onChange: e => setProject(e.target.value),
              style: { padding: 4, background: 'transparent', color: 'inherit', border: '1px solid var(--ui-stroke-secondary)', borderRadius: 6 },
              children: overview.projects.map(p => jsx('option', { value: p.name, children: p.name }, p.name))
            })
          : jsx('div', { style: muted, children: 'No projects yet. Ask Hermes to create one with mcu_project_new.' })),
      last &&
        jsx('div', {
          style: muted,
          children: last.last_verify
            ? `Last verify: ${last.last_verify.status} · ${last.last_verify.at}`
            : 'Not verified yet'
        }),
      detail && jsx(Results, { block: detail.tests, title: 'Simulation (Wokwi)' }),
      detail && jsx(Results, { block: detail.real, title: 'Real board' }),
      detail &&
        detail.history &&
        detail.history.length > 0 &&
        jsx(Section, {
          title: 'History',
          children: jsx('div', {
            style: { display: 'flex', flexDirection: 'column', gap: 2, fontFamily: 'var(--font-mono, monospace)', fontSize: 10.5 },
            children: detail.history.map((h, i) =>
              jsxs('div', {
                style: { display: 'flex', gap: 6 },
                children: [
                  mark(h.ok, h.ok === null),
                  jsx('span', { style: faint, children: h.at.slice(11, 19) }),
                  jsx('span', { children: h.stage }),
                  jsx('span', { style: { ...muted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }, children: h.reason })
                ]
              }, i)
            )
          })
        })
    ]
  })
}

export default {
  id: 'boardloop',
  name: 'BoardLoop',
  register(ctx) {
    ctx.register({
      id: 'workbench',
      area: 'panes',
      title: 'BoardLoop',
      data: { placement: 'right', width: '360px' },
      render: () => jsx(Workbench, { ctx })
    })
    // Older Desktops don't have the media-renderer area: they keep the built-in image viewer.
    if (typeof sdk.TOOL_MEDIA_RENDERER_AREA === 'string') {
      ctx.register({
        id: 'oled-card',
        area: sdk.TOOL_MEDIA_RENDERER_AREA,
        data: { tools: TOOLS, render: props => jsx(OledCard, props) }
      })
    }
  }
}
