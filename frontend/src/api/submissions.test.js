import { afterEach, beforeEach, test } from 'node:test'
import assert from 'node:assert/strict'
import { getTutorReviews, sendTutorChatMessage } from './submissions.js'

const originalFetch = globalThis.fetch
const sessionId = '12345678-1234-4234-8234-123456789abc'
const clientId = '22345678-1234-4234-8234-123456789abc'
let stored
beforeEach(() => {
  stored = sessionId
  globalThis.localStorage = {
    getItem: () => stored,
    setItem: (_, value) => { stored = value },
    removeItem: () => { stored = null },
  }
})
afterEach(() => { globalThis.fetch = originalFetch; delete globalThis.localStorage })

test('a manual retry sends the same message id and preserves saved results', async () => {
  const bodies = []
  globalThis.fetch = async (_, options) => {
    bodies.push(JSON.parse(options.body))
    return new Response(JSON.stringify({ status: 'completed', client_message_id: clientId }))
  }
  await sendTutorChatMessage('part', 'Help me', clientId)
  const result = await sendTutorChatMessage('part', 'Help me', clientId)
  assert.equal(result.status, 'completed')
  assert.deepEqual(bodies[0], bodies[1])
  assert.equal(bodies[0].client_message_id, clientId)
})

test('provider 404 does not discard a valid learner session', async () => {
  let calls = 0
  globalThis.fetch = async () => {
    calls++
    return new Response(JSON.stringify({ detail: 'Provider not found' }), { status: 404 })
  }
  await assert.rejects(sendTutorChatMessage('part','Help',clientId), /Provider not found/)
  assert.equal(stored, sessionId)
  assert.equal(calls, 1)
})

test('a deleted learner session is recreated exactly once', async () => {
  const newId = '32345678-1234-4234-8234-123456789abc'
  const urls = []
  globalThis.fetch = async (url) => {
    urls.push(url)
    if (urls.length === 1) return new Response(JSON.stringify({detail:'Learner session not found'}), {status:404})
    if (urls.length === 2) return new Response(JSON.stringify({id:newId}))
    return new Response(JSON.stringify({reviews:[]}))
  }
  assert.deepEqual(await getTutorReviews('8'), [])
  assert.equal(stored, newId)
  assert.equal(urls.length, 3)
  assert.ok(urls[2].includes(newId))
})

test('non-JSON gateway failures remain readable and are not resubmitted', async () => {
  let calls = 0
  globalThis.fetch = async () => { calls++; return new Response('<html>Unavailable</html>', {status:503}) }
  await assert.rejects(sendTutorChatMessage('part','Help',clientId), /Request failed \(503\)/)
  assert.equal(calls, 1)
})

test('timeout also covers reading the response body', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  globalThis.fetch = async (_, options) => ({
    ok: true, status: 200,
    json: () => new Promise((resolve, reject) => {
      options.signal.addEventListener('abort', () => reject(new DOMException('Aborted','AbortError')))
    }),
  })
  const pending = sendTutorChatMessage('part','Help',clientId)
  const checked = assert.rejects(pending, /Checking for your saved result/)
  await Promise.resolve()
  await Promise.resolve()
  await Promise.resolve()
  t.mock.timers.tick(60000)
  await checked
})
