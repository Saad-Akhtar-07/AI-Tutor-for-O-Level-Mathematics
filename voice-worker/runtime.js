import { KokoroTTS } from 'kokoro-js'
import { env } from '@huggingface/transformers'
import { fileURLToPath } from 'node:url'

export const MODEL = 'onnx-community/Kokoro-82M-v1.0-ONNX'
env.cacheDir = fileURLToPath(new URL('./.models/', import.meta.url))
export async function loadModel(download = false) {
  env.allowRemoteModels = download
  return KokoroTTS.from_pretrained(MODEL, { dtype: 'q8', device: 'cpu' })
}
