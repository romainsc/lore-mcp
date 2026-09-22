# Study E12.48 — Audio ingestion

- **Date:** 2026-09-22
- **Status:** Study complete

## STT model selection

| Model | License | Level | WER | Multilingual | Notes |
|-------|---------|:---:|:---:|:---:|---|
| **Faster-Whisper** | MIT | 1 | ~7.5% | 99+ langs | CTranslate2, 4x faster |
| Distil-Whisper | MIT | 1 | ~7.8% | yes | 5-6x faster, 756M params |
| Vosk | Apache 2.0 | 1 | ~10% | 20+ langs | edge/CPU, no GPU needed |
| NVIDIA Parakeet | Apache 2.0 | 1 | ~5.6% | EN only | NeMo toolkit, NVIDIA GPU |
| WhisperX | BSD | 1 | ~7.5% | yes | + diarization + word timestamps |

**Initial recommendation**: Faster-Whisper (MIT, Level 1).

**IS provider decision** (2026-09-22): NVIDIA
Canary-1B-v2 (CC-BY-4.0, Level 3). Whisper
excluded (Level 4, opaque training data).
Canary: 25 EU languages, CC-BY-4.0, Granary
data published. CPU only (~0.56× realtime).

## API contract for IS provider

The STT service must expose an OpenAI-compatible
endpoint:

```
POST /v1/audio/transcriptions
Content-Type: multipart/form-data

file: <audio file>
model: <model name>
language: <ISO 639-1 code> (optional)
response_format: verbose_json
```

Response:
```json
{
  "text": "full transcription",
  "segments": [
    {"start": 0.0, "end": 5.2, "text": "segment text"},
    ...
  ]
}
```

This is the same API format as OpenAI, implemented
by faster-whisper-server, whisper.cpp server, and
most Whisper-compatible services.

## IS configuration

```yaml
llm:
  - name: whisper
    model: Systran/faster-whisper-large-v3
    api_url: http://127.0.0.1:8093/v1
    start: ./scripts/start-whisper-server.sh
    stop: podman stop whisper-server
    start_timeout: 120
    timeout: 600
```

## Integration in lore-mcp

Audio files (.mp3, .wav, .ogg, .m4a, .flac, .wma)
detected by `detect_format()` → `"audio"` backend.

`parse_to_markdown()` calls STT API, formats
transcription as markdown with timestamp headings.

Output used as orig → standard preprocess pipeline.

## Sources

- Faster-Whisper: https://github.com/SYSTRAN/faster-whisper
- faster-whisper-server: https://github.com/fedirz/faster-whisper-server
- AssemblyAI STT comparison:
  https://www.assemblyai.com/blog/top-open-source-stt-options-for-voice-applications

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
