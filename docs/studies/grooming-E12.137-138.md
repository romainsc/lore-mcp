# Grooming E12.137 + E12.138 — Diarization improvements

## E12.137 — diarization_device config

### Problem

pyannote supports GPU (`pipeline.to(cuda)`) but
the config has no device option. No warning for
risky configurations.

### Fix

Add `parse.diarization_device: gpu|cpu|auto` to
config.yaml. Pyannote reads this and calls
`pipeline.to(device)`. `auto` = GPU if available
and VRAM >4GB, else CPU.

No hardcoded business rules. No silent fallback.
If pyannote OOM on CPU with long audio, the error
is surfaced (E12.136). Documentation explains
limits of each backend.

Warning in preprocess report if pyannote CPU +
audio >30 min (info, not override).

### Config

```yaml
parse:
  diarization_model: pyannote/speaker-diarization-community-1
  diarization_device: auto  # gpu|cpu|auto
```

### DoD

- `diarization_device` in LoreConfig + config.yaml
- pyannote: `pipeline.to(device)` based on config
- diarize library: CPU only (ignored)
- Warning in report for risky config
- Documentation of limits
- CI green

### Effort

Petit.

---

## E12.138 — Per-speaker STT for code-switching

### Problem

STT auto-detects language from first seconds and
transcribes entire audio in that language.
Bilingual audio (FR+EN) → all FR or all EN.

### Consensus approach

Diarize → extract per speaker → concat per speaker
→ STT per speaker → reconstruct timeline.

```
Audio (25 min, 3 speakers)
  │
  ├─ Diarize → turns with timestamps
  │   S01[0-3] S02[3-5] S01[5-8] S02[8-12] S01[12-40]
  │
  ├─ Extract + concat per speaker (ffmpeg)
  │   S01.wav = [0-3] + [5-8] + [12-40] = 34s
  │   S02.wav = [3-5] + [8-12] = 6s
  │
  ├─ STT per speaker (1 call per speaker)
  │   S01 → FR auto-detected
  │   S02 → EN auto-detected
  │
  ├─ Reconstruct timeline (remap timestamps)
  │   S01[0:00] "Bonjour"
  │   S02[0:03] "Hello"
  │   S01[0:05] "Comment ça va"
  │
  └─ LLM stt_correction (optional, enrich)
      harmonize + fix boundary errors
```

### Why concat per speaker works

- Long audio per speaker → reliable language detect
- Only N STT calls (2-5 speakers, not hundreds)
- Full context per speaker → better transcription
- Reconstruction via timestamp mapping table

### Implementation

New functions in preprocess pipeline:

1. `extract_speaker_audio(audio_path, turns)`
   → `{speaker: (tmp_path, segment_table)}`
   Uses ffmpeg to extract segments + concat.
   Segment table maps relative→absolute timestamps.

2. `stt_per_speaker(speaker_audios, stt_entry)`
   → `{speaker: (text, segments, lang_detected)}`
   Calls transcribe_audio for each speaker.

3. `reconstruct_timeline(turns, per_speaker)`
   → markdown with `## Speaker N [HH:MM:SS]`
   Remaps relative timestamps to absolute using
   the segment table.

Wire into preprocess/__init__.py phase 1.5:
when diarization_model is set AND stt is needed,
use per-speaker STT instead of full-audio STT.

### LLM post-correction (optional)

Existing `enrich: stt_correction` with enriched
prompt in prompts.yaml:

```
You are correcting a multi-speaker transcription.
Context: {speakers_hint}
The transcription was done per-speaker then
reassembled. Fix:
- Obvious transcription errors
- Language confusion at speaker boundaries
- Incomplete words cut by segmentation
- Coherence between speakers
Preserve the original language of each speaker.
```

### Config

No new config — per-speaker STT is automatic
when `diarization_model` is set and audio needs
STT. The LLM correction is opt-in via
`enrich: stt_correction`.

### DoD

- extract_speaker_audio (ffmpeg concat)
- stt_per_speaker (N calls, not hundreds)
- reconstruct_timeline (timestamp remapping)
- Wire into phase 1.5
- stt_correction prompt enriched in prompts.yaml
- Tests (mock ffmpeg + mock STT)
- CI green

### Effort

Moyen (ffmpeg manipulation + timestamp mapping +
pipeline wiring).
