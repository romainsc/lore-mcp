# Grooming E12.127 — STT transcription language + params passthrough

## Problem

NeMo Canary-1B-v2 translates FR→EN instead of
transcribing FR→FR. The endpoint URL is correct
(`/v1/audio/transcriptions`) but NeMo ignores
the endpoint distinction and needs an explicit
`task: asr` parameter.

## Fix — Generic params passthrough

Add a `params` dict to LLM registry entries.
Every key/value in `params` is forwarded to
the API call:
- **STT**: as multipart form data fields
- **LLM/VLM**: as JSON body keys

No interpretation by lore-mcp. The user knows
what their server accepts.

```yaml
llm:
  - name: canary-stt
    model: nvidia/canary-1b-v2
    api_url: http://127.0.0.1:8093/v1/audio/transcriptions
    timeout: 600
    params:
      task: asr           # NeMo-specific
      initial_prompt: ""  # Whisper-compatible
```

### Code changes

1. `transcribe_audio` (parse.py): read
   `stt_entry.get("params", {})` and append
   each key/value as form data field.

2. `call_llm` (llm.py): read
   `config.params` and merge into JSON body
   (`payload.update(params)`).

3. `caption_standalone_image` (parse.py):
   same pattern for VLM API calls.

4. `judge_captions` (parse.py): same pattern.

### Reserved fields (NOT forwarded)

name, model, api_url, api_key, start, stop,
timeout, batch_size, verify_ssl, concurrency

These are consumed by lore-mcp. `params` is
the explicit passthrough — no ambiguity.

## Test

`/tmp/Test Français.mp3` with `params.task: asr`
→ transcription in French (not English translation).

## DoD

- `params` dict read from LLM registry entries
- Forwarded in all API calls (STT, LLM, VLM)
- Test with French audio → FR transcription
- Document in configuration.md
- CI green

## Effort

Petit — 4 call sites + 1 test + doc.
