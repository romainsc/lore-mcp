# Grooming E12.139 — MOSS-Transcribe-Diarize evaluation

## Context

Current STT+diarization pipeline is multi-stage:
1. STT (Canary-1B-v2 via API)
2. Diarization (pyannote or diarize library)
3. Alignment (timestamp matching)
4. Speaker identification (LLM enrichment)

Problems identified:
- Long audio CPU OOM (pyannote, E12.137)
- Code-switching not handled (E12.138)
- Complex pipeline (4 stages, 3 libraries)
- STT timeout management (E12.134)

## MOSS-Transcribe-Diarize 0.9B

Single model, single pass:
- Transcription + diarization + timestamps
- 50+ languages including FR+EN
- Up to 90 minutes per pass
- 1st INTERSPEECH 2026 (14 languages)
- Apache 2.0, ungated, Level 2
- 0.9B params (~0.9 GB, CPU feasible)

## Evaluation plan

### MVP1 — Basic evaluation

1. Install: `pip install transformers torch`
2. Download model (ungated, ~0.9 GB)
3. Test on `/tmp/Test Français.mp3` (4s, 1 speaker)
4. Test on meeting audio (2h, multi-speaker, FR+EN)
5. Compare output format with our current pipeline
6. Measure: speed, memory, quality

### MVP2 — Integration

If MVP1 validates:
1. Add MOSS as backend in `diarize.py`
   (alongside pyannote and diarize)
2. Config: `parse.stt_model: moss-td`
   references LLM registry entry
3. MOSS produces transcription + diarization
   in one call — no separate STT needed
4. Output format: markdown with speaker
   headings + timestamps (same as current)

### MVP3 — Replace pipeline

If MVP2 works:
1. MOSS becomes the recommended default for
   audio/video with diarization
2. Canary STT remains for non-diarized
   transcription (simpler, faster for
   single-speaker audio)
3. pyannote/diarize remain as alternatives
   (config-driven choice)

## Config

```yaml
llm:
  - name: moss-td
    model: OpenMOSS-Team/MOSS-Transcribe-Diarize
    # no api_url → local model

parse:
  stt_model: canary-stt        # single-speaker
  diarization_model: moss-td   # multi-speaker: STT+diarize in one pass
```

When `diarization_model` is MOSS, the pipeline:
- Skips separate STT (MOSS does both)
- Skips separate diarization alignment
- Gets speaker-labeled transcription directly

## Compliance

| Criterion | Status |
|-----------|--------|
| License | Apache 2.0 ✓ |
| Gated | No ✓ |
| Level | Level 2 ✓ |
| AGPL-3.0 compat | Yes ✓ |
| Dependencies | PyTorch + Transformers ✓ |

## LLM post-correction fallback

Regardless of backend, `enrich: stt_correction`
with enriched multilingual prompt remains as
quality improvement:
- Fix phonetic errors
- Correct language confusion
- Leverage global context

Prompt enrichment (prompts.yaml):
```
Fix STT errors including language confusion.
Context: {speakers_hint}. Some passages may be
in the wrong language. Correct obvious errors
while preserving each speaker's language.
```

## DoD

- MOSS tested on short + long audio
- Quality comparison with current pipeline
- Integration as diarize.py backend
- Config-driven choice (MOSS vs pyannote vs diarize)
- stt_correction prompt enriched for multilingual
- Tests
- CI green

## Effort

MVP1: petit (installation + tests manuels)
MVP2: moyen (integration diarize.py)
MVP3: petit (config + docs)
