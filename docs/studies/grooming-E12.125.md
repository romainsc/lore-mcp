# Grooming E12.125 — Speaker diarization STT

## Problem

Multi-speaker audio/video (meetings, interviews)
produce a single stream of text without speaker
identification. RAG quality suffers — impossible
to attribute statements to speakers.

## Model compliance

| Model | License | Level | Compatible |
|-------|---------|-------|------------|
| pyannote.audio (code) | MIT | Level 1 | ✓ |
| community-1 | CC-BY-4.0 | Level 2 | ✓ |
| speaker-diarization-3.1 | MIT | Level 2 | ✓ |
| segmentation-3.0 | MIT | Level 2 | ✓ |

All libre, AGPL-3.0 compatible.
Recommended: community-1 (ungated, best perf).

## Approach

Post-processing step on audio after STT:
1. STT produces transcription with timestamps
   (segments with start/end times) — already done
2. pyannote diarization on same audio → speaker
   turn boundaries (speaker_id, start, end)
3. Align STT segments with speaker labels →
   markdown with `## Speaker 1 [00:15]`

This is the industry-standard pattern
(Whisper + pyannote). No STT API supports
diarization natively.

## Config

```yaml
parse:
  diarization_model: pyannote-diarize  # optional

llm:
  - name: pyannote-diarize
    model: pyannote/speaker-diarization-community-1
    # no api_url — local model via pyannote.audio
```

If `diarization_model` absent → no diarization
(current behavior).

## Architecture

- New phase 1.5: between STT and clean
- pyannote loaded via ModelRegistry (LOCAL_GPU
  or LOCAL_CPU slot)
- Input: audio file path + STT segments
- Output: enriched markdown with speaker headings
- pyannote as optional dependency

## DoD

- `parse.diarization_model` config option
- pyannote.audio optional dependency
- Post-processing: audio → speaker turns →
  aligned with STT timestamps
- Markdown output: `## Speaker 1 [HH:MM:SS]`
- STT cache preserved (diarization is additive)
- Test with multi-speaker audio
- CI green

## Type

`[E]` study first — validate pyannote integration
on test audio before implementing pipeline step.

## Effort

Moyen (new dependency, alignment algorithm,
ModelRegistry integration).
