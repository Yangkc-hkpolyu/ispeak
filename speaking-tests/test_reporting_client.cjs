const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')

function controller(response, options = {}) {
  const clicks = [], messages = [], revoked = []
  const source = fs.readFileSync(path.join(__dirname, '../frontend/src/speaking/controller.js'), 'utf8')
    .replace(/^import .*$/gm, '').replace('export default {', 'globalThis.component = {')
  const store = { legacy_video_delay_ms: '420', getItem(key) { return this[key] ?? null } }
  const sandbox = {
    VoiceRecorder: class {}, LiveAvatar: class {}, QuestionLibrary: {}, FeedbackReport: {}, VoiceCoach: {}, PrepChat: {},
    localStorage: store, URL: { createObjectURL() { return 'blob:report' }, revokeObjectURL(url) { revoked.push(url) } },
    document: { body: { appendChild() {} }, createElement() { return { click() { clicks.push({ name: this.download, href: this.href }) }, remove() {} } } },
    window: { setTimeout(callback) { callback() } },
    fetch: async () => { if (options.beforeResponse) options.beforeResponse(); return response },
  }
  vm.createContext(sandbox); vm.runInContext(source, sandbox)
  const state = { session: { id: 'saved-session', report: {} }, reportDownloading: false, toast(message) { messages.push(message) } }
  return { options: sandbox.component, state, clicks, messages, revoked }
}

async function main() {
  const pdf = { ok: true, headers: { get: () => 'application/pdf' }, blob: async () => ({ type: 'application/pdf' }) }
  let h = controller(pdf)
  assert.equal(h.options.data().videoDelayMs, 420, 'retain the saved media timing preference')
  await h.options.methods.downloadPdf.call(h.state)
  assert.equal(h.clicks[0].name, 'ispeak-speaking-report.pdf')
  assert.equal(h.revoked[0], 'blob:report')
  assert.equal(h.state.reportDownloading, false)
  h = controller({ ok: false, json: async () => ({ detail: 'Feedback has not been generated yet.' }) })
  await h.options.methods.downloadPdf.call(h.state)
  assert.equal(h.clicks.length, 0)
  assert.match(h.messages[0], /not been generated/)
  assert.equal(h.state.reportDownloading, false)
  h = controller({ ok: true, headers: { get: () => 'text/html' } })
  await h.options.methods.downloadPdf.call(h.state)
  assert.equal(h.clicks.length, 0)
  assert.match(h.messages[0], /did not return a PDF/)
  h = controller(pdf)
  h.state.reportDownloading = true
  await h.options.methods.downloadPdf.call(h.state)
  assert.equal(h.clicks.length, 0, 'ignore repeated download clicks')
  let stale
  h = controller(pdf, { beforeResponse: () => { stale.session = { id: 'another-session' } } }); stale = h.state
  await h.options.methods.downloadPdf.call(h.state)
  assert.equal(h.clicks.length, 0, 'do not download a stale session report')

  const chartSource = fs.readFileSync(path.join(__dirname, '../frontend/src/speaking/RadarChart.vue'), 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace('export default {', 'globalThis.chart = {')
  const chartContext = {}; vm.createContext(chartContext); vm.runInContext(chartSource, chartContext)
  const chart = chartContext.chart
  const items = [{score:6},{score:0},{score:null},{score:7.5}]
  const ctx = { items, valid: chart.methods.valid }
  assert.equal(chart.computed.complete.call(ctx), false, 'missing evidence must not create a filled radar')
  assert.equal(chart.methods.scoreText.call(ctx, null), 'Not assessed')
  assert.equal(chart.methods.scoreText.call(ctx, 6), '6/10', 'preserve raw scores without a display conversion')
  assert.equal(chart.methods.scoreText.call(ctx, 0), '0/10', 'a genuine zero is not missing evidence')
  assert.equal(chart.methods.scoreText.call(ctx, true), 'Not assessed')
  items[2].score = 5.5
  assert.equal(chart.computed.complete.call(ctx), true)
  console.log('PASS: PDF download, failure and stale-session handling; raw radar scores; retained video delay')
}
main().catch(error => { console.error(error); process.exitCode = 1 })
