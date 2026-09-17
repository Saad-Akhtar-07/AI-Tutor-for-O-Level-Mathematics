import { afterEach, beforeEach, test } from 'node:test'
import assert from 'node:assert/strict'
import { voiceRequest, transcribeRecording } from './voice.js'

const originalFetch = globalThis.fetch
beforeEach(() => { globalThis.localStorage = { getItem: () => '12345678-1234-4234-8234-123456789abc' } })
afterEach(() => { globalThis.fetch = originalFetch; delete globalThis.localStorage })

test('transcription is session scoped multipart, without a manual content type', async () => {
  globalThis.fetch = async (url, options) => {
    assert.match(url, /learner-sessions\/12345678-1234-4234-8234-123456789abc\/voice\/transcriptions$/)
    assert.equal(options.headers['Content-Type'], undefined)
    assert.equal(options.body.get('question_part_id'), 'part-one')
    assert.equal(options.body.get('accurate'), 'false')
    assert.equal(await options.body.get('recording').text(), 'sample')
    return new Response(JSON.stringify({ text: 'sample' }))
  }
  assert.deepEqual(await transcribeRecording(new Blob(['sample']), 'part-one', false), { text: 'sample' })
})
test('an already cancelled voice request never uploads audio', async () => {
  globalThis.fetch = async () => assert.fail('fetch should not run')
  const controller = new AbortController()
  controller.abort()
  await assert.rejects(voiceRequest('prepare', {}, controller.signal), { name: 'AbortError' })
})
test('voice failures expose server guidance without retrying or submitting chat', async () => {
  let calls = 0
  globalThis.fetch = async () => { calls++; return new Response(JSON.stringify({ detail: 'Please retry shortly.' }), { status: 429 }) }
  await assert.rejects(voiceRequest('speech', {}), /Please retry shortly/)
  assert.equal(calls, 1)
})
