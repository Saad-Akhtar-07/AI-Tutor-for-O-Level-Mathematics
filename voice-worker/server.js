import http from 'node:http'
import { prepareSpeech } from './math-speech.js'
import { loadModel } from './runtime.js'

const token = process.env.VOICE_WORKER_TOKEN
if (!token) throw new Error('VOICE_WORKER_TOKEN is required')
let model = null
let busy = false
const server = http.createServer(async (request, response) => {
  const json = (status, body) => { response.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }); response.end(JSON.stringify(body)) }
  if (request.headers.authorization !== `Bearer ${token}`) return json(401, { error: 'Unauthorized' })
  if (request.method === 'GET' && request.url === '/health') return json(200, { ready: Boolean(model), busy })
  if (request.method !== 'POST') return json(404, { error: 'Not found' })
  try {
    const chunks = []
    let size = 0
    for await (const chunk of request) {
      size += chunk.length
      if (size > 24000) return json(413, { error: 'Too large' })
      chunks.push(chunk)
    }
    const body = JSON.parse(Buffer.concat(chunks).toString())
    if (typeof body.text !== 'string' || !body.text.trim() || body.text.length > 6000) return json(400, { error: 'Invalid text' })
    if (request.url === '/prepare') return json(200, prepareSpeech(body.text))
    if (request.url !== '/synthesize') return json(404, { error: 'Not found' })
    if (!model || busy) return json(503, { error: 'Voice is warming up or busy' })
    if (body.text.length > 280 || !['af_heart', 'bf_emma'].includes(body.voice)) return json(400, { error: 'Invalid voice segment' })
    busy = true
    try {
      const audio = await model.generate(body.text, { voice: body.voice })
      const buffer = Buffer.from(await audio.toBlob().arrayBuffer())
      response.writeHead(200, { 'Content-Type': 'audio/wav', 'Cache-Control': 'no-store' })
      response.end(buffer)
    } finally { busy = false }
  } catch { if (!response.headersSent) json(500, { error: 'Speech processing failed' }); else response.end() }
})
server.listen(Number(process.env.VOICE_WORKER_PORT || 8765), '127.0.0.1')
// Downloads are a setup step, never part of startup or student requests.
loadModel().then(async loaded => {
  await loaded.generate('Ready to help.', { voice: 'af_heart' })
  model = loaded
  console.log('Local tutor voice ready')
}).catch(() => console.warn('Local voice unavailable. Run npm run setup in voice-worker. Device voice remains available.'))
