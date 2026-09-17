"""Real local synthesis plus optional Groq transcription of synthetic audio only."""
import argparse
import time
from pathlib import Path

import requests

from backend.app.services import speech, transcription


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live-transcription', action='store_true')
    args = parser.parse_args()
    speech.start_worker()
    try:
        start = time.perf_counter()
        ready = False
        while time.perf_counter() - start < 35:
            try:
                result = requests.get(f'http://127.0.0.1:{speech._port}/health', headers={'Authorization': f'Bearer {speech._token}'}, timeout=1)
                ready = result.ok and result.json()['ready']
                if ready:
                    break
            except requests.RequestException:
                pass
            time.sleep(.25)
        if not ready:
            raise RuntimeError('Local voice did not become ready. Run voice-worker setup and check the port.')
        print(f'Local startup and warmup: {time.perf_counter() - start:.2f}s')
        prepared = speech.prepare('Try 3/5. What does the denominator represent?')
        assert prepared['warning'] is None
        for text in prepared['segments']:
            started = time.perf_counter()
            audio = speech.synthesize('synthetic-smoke', 'synthetic-reply', text, 'af_heart')
            print(f'Generated {len(audio)} WAV bytes in {time.perf_counter() - started:.2f}s')
            started = time.perf_counter()
            assert audio == speech.synthesize('synthetic-smoke', 'synthetic-reply', text, 'af_heart')
            print(f'Cached replay: {time.perf_counter() - started:.3f}s')
        if args.live_transcription:
            sample = Path(__file__).resolve().parents[2] / 'voice-worker/.models/sample-af_heart.wav'
            started = time.perf_counter()
            result = transcription.transcribe(sample.read_bytes())
            print(f'Synthetic Groq transcription: {time.perf_counter() - started:.2f}s')
            print(result['text'])
            assert 'fifths' in result['text'].lower()
    finally:
        speech.stop_worker()


if __name__ == '__main__':
    main()
