// Renders desktop/plugin.js with real React in jsdom against a fake plugin context.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { JSDOM } from 'jsdom'
import { copyFileSync } from 'node:fs'

const dom = new JSDOM('<!doctype html><div id="root"></div>')
globalThis.window = dom.window
globalThis.document = dom.window.document
globalThis.IS_REACT_ACT_ENVIRONMENT = true

const React = await import('react')
const { createRoot } = await import('react-dom/client')
const { act } = await import('react')
// Copy the real file next to the stubs so its bare imports resolve here.
copyFileSync(new URL('../../desktop/plugin.js', import.meta.url), new URL('./.plugin-under-test.js', import.meta.url))
const plugin = (await import('./.plugin-under-test.js')).default

const PNG = 'data:image/png;base64,iVBORw0KGgo='
const API = {
  '/overview': { minutes: { used: 0.9, limit: 50 }, projects: [
    { name: 'thermostat-buggy', last_verify: { status: 'verified', summary: '3/3', at: '2026-11-09T14:58:00Z' } }] },
  '/project/thermostat-buggy': {
    name: 'thermostat-buggy',
    tests: { at: '2026-11-09T14:57:38Z', passed: 2, failed: 1, total: 3, results: [
      { name: 'hot room turns the LED on', passed: true, reason: 'all scenario steps passed', image: PNG },
      { name: 'cool room keeps the LED off', passed: false, reason: "expected serial 'LED=OFF' not seen", serial_tail: ['T=20.0 LED=ON'] },
      { name: 'exactly 30 C is not too hot', passed: true, reason: 'ok' }] },
    real: { at: '2026-11-09T15:10:00Z', passed: 1, failed: 0, total: 2, results: [
      { name: 'boots', passed: true, reason: 'all expected lines seen' },
      { name: 'hot room', passed: null, skipped: true, reason: 'sets simulated inputs (dht1)' }] },
    history: [{ at: '2026-11-09T14:58:00Z', stage: 'verify', ok: true, reason: 'verified' }] }
}

function fakeCtx() {
  const ctx = { contributions: [], listeners: {}, intervals: [] }
  ctx.register = c => { ctx.contributions.push(c); return () => {} }
  ctx.rest = path => (API[path] ? Promise.resolve(API[path]) : Promise.reject(new Error('404 ' + path)))
  ctx.setInterval = (fn, ms) => { ctx.intervals.push(ms); return () => {} }
  ctx.onEvent = (type, fn) => { ctx.listeners[type] = fn; return () => {} }
  return ctx
}

test('registers the Workbench pane and the screenshot renderer', () => {
  const ctx = fakeCtx()
  plugin.register(ctx)
  assert.equal(plugin.id, 'boardloop')
  const pane = ctx.contributions.find(c => c.id === 'workbench')
  assert.equal(pane.area, 'panes')
  assert.equal(pane.data.placement, 'right')
  const card = ctx.contributions.find(c => c.id === 'oled-card')
  assert.deepEqual(card.data.tools, ['mcu_test', 'mcu_verify', 'mcu_simulate'])
})

test('Workbench renders projects, minutes, results, real-board results and history', async () => {
  const ctx = fakeCtx()
  plugin.register(ctx)
  const pane = ctx.contributions.find(c => c.id === 'workbench')
  const root = createRoot(document.getElementById('root'))
  await act(async () => { root.render(pane.render()) })
  await act(async () => { await new Promise(r => setTimeout(r, 10)) })
  const text = document.getElementById('root').textContent
  for (const s of ['BoardLoop', '0.9 / 50', 'thermostat-buggy', 'Last verify: verified',
                   'Simulation (Wokwi) · 2/3 passed', "expected serial 'LED=OFF' not seen", 'T=20.0 LED=ON',
                   'Real board · 1/2 passed', 'sets simulated inputs (dht1)', 'History']) {
    assert.ok(text.includes(s), `missing: ${s}`)
  }
  assert.equal(document.querySelectorAll('img').length, 1)
  assert.ok(ctx.listeners['plugin.boardloop.results.updated'], 'listens for live updates')
  assert.deepEqual(ctx.intervals, [15000])
  await act(async () => { root.unmount() })
})

test('Workbench shows a clear message when the backend is off', async () => {
  const ctx = fakeCtx()
  ctx.rest = () => Promise.reject(new Error('plugin disabled'))
  plugin.register(ctx)
  const root = createRoot(document.getElementById('root'))
  await act(async () => { root.render(ctx.contributions.find(c => c.id === 'workbench').render()) })
  await act(async () => { await new Promise(r => setTimeout(r, 10)) })
  assert.ok(document.getElementById('root').textContent.includes('BoardLoop backend unavailable: plugin disabled'))
  await act(async () => { root.unmount() })
})

test('screenshot card claims only BoardLoop screenshots and falls back otherwise', async () => {
  const ctx = fakeCtx()
  plugin.register(ctx)
  const card = ctx.contributions.find(c => c.id === 'oled-card')
  const fallback = React.createElement('span', null, 'FALLBACK')
  const file = { path: '/runs/hot.png', name: 'hot.png', kind: 'image', resolveUrl: () => Promise.resolve(PNG) }
  const result = JSON.stringify({ results: [{ name: 'hot room', passed: true, reason: 'ok', screenshot: '/runs/hot.png' }] })
  const root = createRoot(document.getElementById('root'))
  await act(async () => { root.render(card.data.render({ file, toolName: 'mcu_test', result, fallback })) })
  await act(async () => { await new Promise(r => setTimeout(r, 10)) })
  assert.ok(document.getElementById('root').textContent.includes('✓ PASS'))
  await act(async () => { root.render(card.data.render({ file: { ...file, path: '/other.png' }, toolName: 'mcu_test', result, fallback })) })
  assert.equal(document.getElementById('root').textContent, 'FALLBACK')
  await act(async () => { root.unmount() })
})
