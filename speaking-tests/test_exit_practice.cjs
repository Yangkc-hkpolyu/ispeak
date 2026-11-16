// Exercise exit against real controller methods with delayed service responses.
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const { test } = require('node:test')
const root = path.join(__dirname, '../frontend/src/speaking')
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
const session = (mode = 'mock') => ({ id: 'saved-session', setup: { mode }, server_time: Date.now() / 1000,
  turns: [{ id: 'submitted', answer: 'Already saved' }], report: null,
  current_question: { id: 'q1', phase: 'ready', answer_seconds: 30 } })

function harness() {
  const calls = [], storage = new Map([['polyspeak-session', 'saved-session']]), timers = new Set()
  const recording = { abort() { calls.push('abort') }, start: async () => Date.now(), stop: async () => ({ text: 'Answer', id: 'audio' }) }
  const context = vm.createContext({
    VoiceRecorder: function () { return recording }, LiveAvatar: class {},
    QuestionLibrary: {}, FeedbackReport: {}, VoiceCoach: {}, PrepChat: {},
    api: async () => session(), post: async url => { calls.push(url); return session() },
    localStorage: { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) },
    window: { confirm: () => true, scrollTo() {} },
    setTimeout: fn => { timers.add(fn); return fn }, clearTimeout: fn => timers.delete(fn), Date,
  })
  const source = fs.readFileSync(path.join(root, 'controller.js'), 'utf8').replace(/^import .*\r?\n/gm, '').replace('export default', 'const component =')
  const component = vm.runInContext(source + '\ncomponent', context)
  const app = { ...component.data(), $refs: {}, $nextTick: fn => fn(), $el: { querySelector: () => ({ focus() { calls.push('focus-home') } }) } }
  for (const [name, method] of Object.entries(component.methods)) app[name] = method.bind(app)
  for (const [name, getter] of Object.entries(component.computed)) Object.defineProperty(app, name, { get: () => getter.call(app) })
  app.session = session()
  app.live = { interrupt() { calls.push('interrupt') }, close() { calls.push('close') } }
  return { app, context, recording, calls, storage, timers }
}

test('cancel keeps the session, draft and recording intact', () => {
  const h = harness(); h.app.draft = 'Unfinished'; h.app.recording = true
  h.context.window.confirm = () => false
  h.app.exitPractice()
  assert.equal(h.app.session.id, 'saved-session'); assert.equal(h.app.draft, 'Unfinished')
  assert.equal(h.app.recording, true); assert.equal(h.calls.length, 0)
})

test('exit stops media and recording, clears auto-resume, and leaves submitted answers intact', () => {
  const h = harness(), saved = h.app.session
  h.app.recording = true; h.app.playing = true; h.app.mediaBusy = true
  h.app.recordTimer = h.context.setTimeout(h.app.stopRecording)
  h.app.draft = 'Unfinished'; h.app.notes = 'Private notes'
  h.app.exitPractice(); h.app.tick()
  assert.equal(h.app.session, null); assert.equal(h.app.view, 'practice')
  assert.equal(h.app.draft, ''); assert.equal(h.app.notes, '')
  assert.equal(h.app.recording, false); assert.equal(h.app.playing, false)
  assert.equal(h.app.navigationLocked, false); assert.equal(h.app.live, null)
  assert.equal(h.storage.has('polyspeak-session'), false); assert.equal(h.storage.has('ispeak-session'), false); assert.equal(h.timers.size, 0)
  assert.deepEqual(h.calls, ['abort', 'interrupt', 'close', 'focus-home'])
  assert.equal(saved.turns[0].answer, 'Already saved')
})

for (const method of ['sendAnswer', 'finishSession', 'questionReady', 'restore']) {
  test(`late ${method} response cannot reopen an exited session or unlock a newer request`, async () => {
    const h = harness(), pending = deferred()
    h.context.post = h.context.api = () => pending.promise
    const work = h.app[method](...(method === 'restore' ? ['saved-session'] : []))
    h.app.exitPractice()
    h.app.session = { ...session('coach'), id: 'new-session' }; h.app.busy = true
    pending.resolve(session()); await work
    assert.equal(h.app.session.id, 'new-session'); assert.equal(h.app.busy, true)
    assert.equal(h.storage.has('polyspeak-session'), false)
  })
}

test('late transcription after exit cannot auto-submit a mock answer', async () => {
  const h = harness(), pending = deferred(); h.app.recording = true
  h.recording.stop = () => pending.promise
  const work = h.app.stopRecording(); h.app.exitPractice()
  pending.resolve({ id: 'audio', text: 'Late transcript' }); await work
  assert.equal(h.app.session, null); assert.equal(h.app.draft, '')
  assert.equal(h.calls.some(call => call.endsWith('/answers')), false)
})

test('microphone startup callbacks cannot restore recording after exit', async () => {
  const h = harness(), pending = deferred(); let onTranscript
  h.recording.start = options => { onTranscript = options.onTranscript; return pending.promise }
  const work = h.app.beginRecording(); h.app.exitPractice()
  onTranscript('Late words'); pending.resolve(Date.now()); await work
  assert.equal(h.app.session, null); assert.equal(h.app.recording, false); assert.equal(h.app.draft, '')
  assert.equal(h.calls.some(call => call.endsWith('/begin-answer')), false)
})

test('exit during playback interruption prevents a new connection', async () => {
  const h = harness(), pending = deferred()
  h.app.session.current_question.phase = 'listening'
  h.app.live.interrupt = () => pending.promise
  h.app.connectAvatar = async () => { throw new Error('Must not reconnect after exit') }
  const work = h.app.playQuestion(); h.app.exitPractice(); pending.resolve(); await work
  assert.equal(h.app.mediaBusy, false); assert.equal(h.app.toastMessage, '')
})

test('exit during avatar setup prevents the question from being spoken', async () => {
  const h = harness(), pending = deferred(); let connected
  h.app.session.current_question.phase = 'listening'
  const connecting = new Promise(resolve => { connected = resolve })
  h.app.connectAvatar = () => { connected(); return pending.promise }
  const work = h.app.playQuestion(); await connecting
  h.app.exitPractice(); pending.resolve(); await work
  assert.equal(h.app.mediaBusy, false); assert.equal(h.app.toastMessage, '')
})

test('actual recorder releases a microphone granted after cancellation', async () => {
  const pending = deferred(); let stopped = false
  const context = vm.createContext({ navigator: { mediaDevices: { getUserMedia: () => pending.promise } }, clearTimeout, setTimeout })
  const source = fs.readFileSync(path.join(root, 'recorder.js'), 'utf8').replace('export class', 'class')
  const Recorder = vm.runInContext(source + '\nVoiceRecorder', context), recorder = new Recorder()
  const work = recorder.start({ path: '/unused', onTranscript() {} })
  recorder.abort(); pending.resolve({ getTracks: () => [{ stop() { stopped = true } }] })
  await assert.rejects(work, /cancelled/); assert.equal(stopped, true)
})

test('old and renamed session keys retain resume compatibility', () => {
  const h = harness()
  assert.equal(vm.runInContext('savedSessionId()', h.context), 'saved-session')
  h.storage.set('ispeak-session', 'new-session')
  assert.equal(vm.runInContext('savedSessionId()', h.context), 'new-session')
  h.app.exitPractice()
  assert.equal(h.storage.has('polyspeak-session'), false)
  assert.equal(h.storage.has('ispeak-session'), false)
})
