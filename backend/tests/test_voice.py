import io
import wave
from uuid import uuid4
from unittest.mock import Mock

import numpy as np
import av
import pytest
from fastapi import HTTPException

from backend.app.services import transcription, speech
from backend.app.routers import voice
from backend.tests.test_tutor_recovery import learner, reply


def wav(seconds=1, amplitude=2000):
    stream = io.BytesIO()
    samples = (np.sin(np.arange(int(seconds * 16000)) * .1) * amplitude).astype('<i2')
    with wave.open(stream, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(samples.tobytes())
    return stream.getvalue()


@pytest.mark.parametrize('data,status', [(b'not audio', 422), (wav(.1), 422), (wav(amplitude=0), 422), (wav(32), 413), (b'x' * (transcription.MAX_BYTES + 1), 413)], ids=['invalid', 'short', 'silent', 'long', 'oversize'])
def test_audio_rejects_invalid_silent_long_and_oversize(data, status):
    with pytest.raises(HTTPException) as error:
        transcription.decode_recording(data)
    assert error.value.status_code == status


def test_audio_normalizes_to_bounded_mono_wav():
    output = transcription.decode_recording(wav())
    with wave.open(io.BytesIO(output)) as audio:
        assert (audio.getnchannels(), audio.getframerate(), audio.getnframes()) == (1, 16000, 16000)


@pytest.mark.parametrize('format,codec,rate', [('webm', 'libopus', 48000), ('mp4', 'aac', 44100), ('ogg', 'libopus', 48000)])
def test_browser_audio_formats_decode(format, codec, rate):
    output = io.BytesIO()
    with av.open(output, mode='w', format=format) as container:
        stream = container.add_stream(codec, rate=rate)
        stream.layout = 'mono'
        samples = (np.sin(np.arange(rate, dtype=np.float32) * .1) * .1).reshape(1, -1)
        frame = av.AudioFrame.from_ndarray(samples, format='flt', layout='mono')
        frame.sample_rate = rate
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
    normalized = transcription.decode_recording(output.getvalue())
    assert normalized.startswith(b'RIFF')


def test_voice_rate_limits_are_separate_from_other_operations(monkeypatch):
    from backend.app.services import voice_admission
    monkeypatch.setattr(voice_admission, '_requests', voice_admission.OrderedDict())
    for _ in range(8):
        voice_admission.admit('learner', 'transcription')
    with pytest.raises(HTTPException) as error:
        voice_admission.admit('learner', 'transcription')
    assert error.value.status_code == 429
    voice_admission.admit('learner', 'speech')
    voice_admission.admit('another-learner', 'transcription')


def test_transcription_preserves_ambiguous_maths_and_only_retries_explicitly(monkeypatch):
    call = Mock(return_value=Mock(ok=True, status_code=200, json=lambda: {'text': 'one over x plus two', 'segments': []}))
    monkeypatch.setattr(transcription.requests, 'post', call)
    monkeypatch.setattr(transcription, '_cooldown_until', 0)
    monkeypatch.setattr(transcription, 'get_settings', lambda: Mock(groq_api_key='fake'))
    result = transcription.transcribe(wav())
    assert result['text'] == 'one over x plus two'
    assert call.call_args.kwargs['data']['model'] == 'whisper-large-v3-turbo'
    transcription.transcribe(wav(), accurate=True)
    assert call.call_args.kwargs['data']['model'] == 'whisper-large-v3'
    assert call.call_count == 2


def test_provider_quota_has_separate_cooldown(monkeypatch):
    monkeypatch.setattr(transcription, '_cooldown_until', 0)
    monkeypatch.setattr(transcription, 'get_settings', lambda: Mock(groq_api_key='fake'))
    call = Mock(return_value=Mock(ok=False, status_code=429, headers={'retry-after': '5'}))
    monkeypatch.setattr(transcription.requests, 'post', call)
    for _ in range(2):
        with pytest.raises(HTTPException) as error:
            transcription.transcribe(wav())
        assert error.value.status_code == 429
    assert call.call_count == 1


def test_voice_ownership_no_private_snapshot_and_database_released(learner, monkeypatch):
    client, session, part = learner
    monkeypatch.setattr('backend.app.routers.tutor.run_tutor_chat', reply)
    turn = client.post(f'/api/v1/learner-sessions/{session}/question-parts/{part}/chat-turns', json={'message': 'Help', 'client_message_id': str(uuid4())}).json()
    def prepare(text):
        stats = voice.database.pool.get_stats()
        assert stats['pool_available'] == stats['pool_size']
        assert text == turn['tutor_message']
        return {'segments': [text], 'warning': None}
    monkeypatch.setattr(speech, 'prepare', prepare)
    monkeypatch.setattr(speech, 'synthesize', lambda *args: b'RIFFtest')
    body = {'source_type': 'chat', 'source_id': turn['id']}
    base = f'/api/v1/learner-sessions/{session}/voice'
    assert client.post(base + '/prepare', json=body).status_code == 200
    result = client.post(base + '/speech', json=body)
    assert result.status_code == 200
    assert result.headers['cache-control'] == 'private, no-store'
    assert client.post(base + '/speech', json={**body, 'segment': 99}).status_code == 422
    assert client.post(base + '/speech', json={**body, 'source_type': 'snapshot'}).status_code == 422
    assert client.post(f'/api/v1/learner-sessions/{uuid4()}/voice/prepare', json=body).status_code == 404


def test_transcription_does_not_submit_chat_and_releases_db(learner, monkeypatch):
    client, session, part = learner
    def fake(data, accurate):
        stats = voice.database.pool.get_stats()
        assert stats['pool_available'] == stats['pool_size']
        return {'text': 'one over x plus two', 'warning': 'Check grouping'}
    monkeypatch.setattr(transcription, 'transcribe', fake)
    result = client.post(f'/api/v1/learner-sessions/{session}/voice/transcriptions', files={'recording': ('input.wav', wav(), 'audio/wav')}, data={'question_part_id': part})
    assert result.status_code == 200
    assert client.get(f'/api/v1/learner-sessions/{session}/chat-turns').json()['turns'] == []


def test_voice_body_limit_before_parser(learner):
    client, session, _ = learner
    result = client.post(f'/api/v1/learner-sessions/{session}/voice/transcriptions', content=b'x' * (transcription.MAX_BYTES + 20000), headers={'Origin': 'http://localhost:5173'})
    assert result.status_code == 413
    assert result.headers['access-control-allow-origin'] == 'http://localhost:5173'


def test_playlists_cannot_load_external_audio_sources():
    with pytest.raises(HTTPException) as error:
        transcription.decode_recording(b'#EXTM3U\n#EXT-X-TARGETDURATION:10\n#EXTINF:10,\nfile:///not-a-recording.wav\n#EXT-X-ENDLIST\n')
    assert error.value.status_code == 422


def test_private_cache_isolated_and_replay_cached(monkeypatch):
    monkeypatch.setattr(speech, '_cache_bytes', 0)
    monkeypatch.setattr(speech, '_cache', speech.OrderedDict())
    call = Mock(return_value=Mock(content=b'RIFFaudio'))
    monkeypatch.setattr(speech, 'worker', call)
    speech.synthesize('learner-one', 'reply', 'Hello', 'af_heart')
    speech.synthesize('learner-one', 'reply', 'Hello', 'af_heart')
    assert call.call_count == 1
    speech.synthesize('learner-two', 'reply', 'Hello', 'af_heart')
    assert call.call_count == 2


def test_dead_worker_device_fallback_never_guesses_maths(monkeypatch):
    monkeypatch.setattr(speech, 'worker', Mock(side_effect=HTTPException(503, 'Unavailable')))
    result = speech.prepare('Try 1/(x+2). Think about the denominator.')
    assert result['device_only']
    assert result['warning']
    assert result['segments'] == ['Please check the mathematical expression shown in the text.', 'Think about the denominator.']


@pytest.mark.parametrize('text,expected', [
    ('1/(x+2).\n\n+\n2/(y+3).\n.\n3/(z+4).', ['math']),
    ('1/(x+2). 2/(y+3). Think about the denominator. 3/(z+4). 4/(a+5).',
     ['math', 'Think about the denominator.', 'math']),
    ('P(first A and second B)=P(first A)×P(second B | first A).\nHere A and B are both salt-flavoured packets.',
     ['math', 'Here A and B are both salt-flavoured packets.']),
])
def test_dead_worker_groups_maths_reminders_until_prose_resumes(monkeypatch, text, expected):
    monkeypatch.setattr(speech, 'worker', Mock(side_effect=HTTPException(503, 'Unavailable')))
    result = speech.prepare(text)
    reminder = 'Please check the mathematical expression shown in the text.'
    assert result['segments'] == [reminder if segment == 'math' else segment for segment in expected]
    assert result['warning']
    assert result['device_only']
