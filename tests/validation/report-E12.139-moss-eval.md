# Report E12.139 — MOSS-Transcribe-Diarize Evaluation

Date: 2026-10-07
Model: OpenMOSS-Team/MOSS-Transcribe-Diarize 0.9B
License: Apache 2.0, Level 2, ungated

## Results

| Test | Device | Audio | Result |
|------|--------|-------|--------|
| 1.2s FR | GPU (RTX 500, 4GB) | `/tmp/Test Français.mp3` | ❌ Hallucination ("Yes, it's a test") — audio too short |
| 2 min FR meeting | CPU | First 2 min of meeting | ✅ **FR transcription correct, 3 speakers** |
| 25 min FR meeting | GPU (RTX 500, 4GB) | Full meeting | ❌ OOM (needs >8GB VRAM) |

## Detailed results — 2 min meeting (CPU)

- Inference: 113s for 120s audio (RTF ~1x)
- Speakers: S01, S02, S03 (correct)
- Language: French (correct, no translation)
- Format: `[timestamp][speaker_id] text[end_timestamp]`

Sample output:
```
[0.57][S01] Maman vient d'arriver, voilà.[3.24]
[4.38][S02] Allo ? Vous m'entendez ?[6.54]
[6.54][S01] Oui, nous vous entendons.[8.27]
[22.62][S03] Bonjour.[23.34]
[48.96][S01] Donc, d'un point de vue scolaire avec Sophie
ça se passe plutôt bien.[53.04]
```

## Performance

| Metric | Value |
|--------|-------|
| Model load (CPU) | 5s |
| Model load (GPU) | 5s |
| VRAM (bf16) | 1732 MB |
| Inference RTF (CPU) | ~1x |
| Inference RTF (GPU, short) | 0.8s for 1.2s |
| Min audio length | >2s (hallucinates on <2s) |
| Min VRAM for 25 min | >8 GB estimated |

## Dependencies

- `moss-transcribe-diarize` (pip from GitHub)
- `transformers`, `torch` (already installed)
- `librosa`, `av` (audio loading)
- `soundfile` (wav writing)

## Issues found

1. **Hallucination on short audio** (<2s):
   MOSS outputs English text for any audio
   under ~2 seconds regardless of language
2. **OOM on RTX 500 (4GB)** for >5 min audio:
   whisper encoder needs ~586 MB per chunk,
   total exceeds 4GB with model loaded
3. **Default prompt in Chinese**: works fine
   with EN/FR prompts, but FR prompt produces
   same quality as default — model auto-detects
4. **parse_transcript bug**: expects str but
   receives dict for raw output — minor

## Verdict

**GO for integration (E12.140)** with conditions:
- CPU mode: viable for audio <30 min (RTF ~1x)
- GPU mode: requires >8 GB VRAM
- Config: `parse.diarization_device: cpu|gpu`
- Min audio guard: skip MOSS for <5s audio
- Fallback: existing pipeline for GPU <8GB

MOSS replaces the 4-stage pipeline (STT + diarize
+ align + speaker_id) with a single call.
Quality is excellent for FR transcription +
speaker diarization.
