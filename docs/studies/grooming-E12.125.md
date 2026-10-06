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
    model: pyannote-community/speaker-diarization-community-1
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

## Speaker identification

### Cascade

1. **Recipe `speakers` (string) + `enrich: speaker_id`**:
   LLM infers with user-provided context hint.
   `speakers` is a free-form prompt, not a list.
   ```yaml
   sources:
     - file: reunion.mp4
       speakers: "alice et bob, un parle anglais, l'autre de cailloux"
     - file: interview.mp3
       speakers: "journaliste et ministre de l'éducation"
   ```
   Prompt: "Context: {speakers}. Associate each
   SPEAKER_N to the correct person."

2. **`enrich: speaker_id` alone** (no speakers):
   LLM infers from content only.
   Prompt: "Identify each speaker from context."
   Unidentifiable speakers keep "Speaker N".

3. **No speakers, no speaker_id** (default):
   anonymous labels: SPEAKER_0 → "Speaker 1".

One LLM mechanism, two prompt variants
(with/without context hint). No structured data.

### LLM inference technique

New enrichment technique `speaker_id` in
enrich.py:
```python
def enrich_speaker_id(text, llm):
    """Replace anonymous labels with names."""
    # Prompt LLM with transcription
    # Get JSON mapping {SPEAKER_0: name, ...}
    # Regex replace in markdown headings
```

Activated via `enrich: speaker_id` or config
`enrich.techniques: [speaker_id]`.

## Config

Two backends supported:

```yaml
# Option 1: diarize library (ungated, Apache 2.0, recommended)
parse:
  diarization_model: diarize  # or empty → auto-detect

# Option 2: pyannote (gated, CC-BY-4.0, more accurate)
parse:
  diarization_model: pyannote/speaker-diarization-community-1

enrich:
  techniques: [speaker_id]  # optional LLM step
```

`diarize` (Apache 2.0): `pip install diarize`.
Ungated, CPU-only, WeSpeaker embeddings.

`pyannote` (CC-BY-4.0): `pip install pyannote.audio`.
HuggingFace token + gate acceptance required.

If model_name starts with "pyannote" → pyannote backend.
Otherwise → diarize backend.

Note: embedder builtin should eventually move
to the unified registry — logged as tech debt.

## DoD

- `parse.diarization_model` config option
- pyannote.audio optional dependency
- LLM registry entry without api_url = local
- Post-processing: audio → speaker turns →
  aligned with STT timestamps
- Markdown output: `## Speaker 1 [HH:MM:SS]`
  or `## Alice [HH:MM:SS]` (if identified)
- Speaker identification cascade:
  recipe speakers > LLM inference > anonymous
- `enrich: speaker_id` technique
- STT cache preserved (diarization is additive)
- Test with multi-speaker audio
- CI green

## Type

`[E]` study first — validate pyannote integration
+ LLM speaker inference on test audio.

## Effort

Moyen-gros (pyannote integration, alignment,
LLM speaker inference, ModelRegistry, new
enrichment technique).
