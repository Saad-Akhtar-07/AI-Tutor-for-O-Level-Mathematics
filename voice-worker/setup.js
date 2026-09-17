import { loadModel } from './runtime.js'
import { fileURLToPath } from 'node:url'
try {
const start = performance.now()
const model = await loadModel(true)
console.log(`Model loaded in ${((performance.now() - start) / 1000).toFixed(1)} seconds`)
for (const voice of ['af_heart', 'bf_emma']) {
  const started = performance.now()
  const audio = await model.generate('The probability is three fifths. What could you try next?', { voice })
  await audio.save(fileURLToPath(new URL(`./.models/sample-${voice}.wav`, import.meta.url)))
  console.log(`${voice}: ${((performance.now() - started) / 1000).toFixed(2)} seconds; sample saved under .models`)
}
} catch (error) { console.error('Voice setup failed:', error.message); process.exitCode = 1 }
