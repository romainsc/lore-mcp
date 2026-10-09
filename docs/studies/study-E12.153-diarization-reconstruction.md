# Study E12.153 — Diarization pipeline: world consensus and reconstruction

CC-BY-SA 4.0

## Research methodology

7 search iterations, 3 consecutive dry (5, 6, 7).
6 primary sources: pyannoteAI blog (official),
WhisperX (INTERSPEECH 2023, 13k+ stars), Vast.ai
docs, Fora Soft production guide, NVIDIA NeMo docs,
DISPLACE 2024 Challenge. Each iteration used
different search terms to maximize coverage.

## 1. Two consensus pipelines (situational)

### 1.1 Monolingual: Global STT → diarize → align

WhisperX (Bain et al., INTERSPEECH 2023):

```
Audio → Whisper (full) → wav2vec2 forced alignment
     → pyannote diarization → word-level speaker assignment
```

Advantages:
- Word-level timestamps from forced alignment
- Single STT pass (fast)
- Direct temporal alignment (no reconstruction)

Limitation:
- Whisper locks language from first 30s
- Code-switching causes "significant quality
  degradation" on non-detected languages
- WhisperX community workaround: chunk by speaker
  segment and re-run STT → converges to pipeline 2

### 1.2 Multilingual: Diarize → per-speaker STT → reconstruct

pyannoteAI "multi-stream" architecture:

```
Audio → pyannote diarization (language-agnostic)
     → extract per-speaker audio (ffmpeg concat)
     → STT per speaker (with explicit lang)
     → reconstruct timeline (STT timestamps + seg_table)
```

Key insight from pyannoteAI: diarization is
**language-agnostic** (embeddings capture pitch,
formant, vocal tract — stable across languages).
Transcription is **language-specific**. They must
be configured separately.

Sources: pyannoteAI blog "Multilingual and
Code-Switching Diarization", Vast.ai
"Speaker Diarization with Pyannote", Fora Soft
"Pyannote in Production".

**lore-mcp operates in this pipeline.**
The architecture is correct. The implementation
has bugs.

## 2. Three implementation bugs

### 2.1 Canary does NOT auto-detect language

**Verified**: Canary uses a task-token architecture.
`<source_lang>`, `<target_lang>`, `<task>` tokens
are fed to the decoder. Without explicit
`source_lang`, Canary defaults to **English ASR**.
There is no auto-detection — this is by design.

Source: NVIDIA NeMo docs, Canary-1B HuggingFace
model card, MarkTechPost Canary guide.

Impact on lore-mcp: E12.152 removed `source_lang`
from per-speaker STT to "let auto-detection work".
But auto-detection doesn't exist in Canary →
everything transcribed as English.

**Fix**: pass `source_lang` explicitly. Options:
1. Parse `speakers` hint for language cues
2. Pre-STT language detection (SpeechBrain)
3. Source-level `lang` field (existing mechanism)

### 2.2 Reconstruction ignores STT timestamps

lore-mcp's `reconstruct_timeline` distributes text
proportionally by character position. The consensus
uses **temporal alignment** via:

1. STT produces timestamped segments (Canary
   `verbose_json` → `segments[].start/end`)
2. `seg_table` maps relative → absolute time:
   `(abs_start, abs_end, rel_start, rel_end)`
3. Each STT segment is placed at its absolute
   position on the original timeline

lore-mcp already HAS `seg_table` from
`extract_speaker_audio` and requests `verbose_json`
from Canary. But `_extract_stt_segments` (line 48
of `__init__.py`) discards the real timestamps and
creates fake `end = start + 10.0`.

**Fix**: use the real STT segment timestamps +
seg_table mapping for reconstruction.

### 2.3 _extract_stt_segments destroys timestamps

```python
# Current code (broken)
segments.append({
    "text": line.strip(),
    "start": current_start,
    "end": current_start + 10.0,  # FAKE
})
```

The real timestamps exist in the Canary API
response (`data["segments"]`) but are converted
to markdown by `transcribe_audio` and then
re-parsed by `_extract_stt_segments` which
loses them.

**Fix**: preserve structured segment data through
the pipeline, not just the markdown text.

## 3. Emerging concepts

### 3.1 SpeechBrain VoxLingua107 — pre-STT language detection

- Model: `speechbrain/lang-id-voxlingua107-ecapa`
- License: Apache 2.0 (compatible AGPL)
- Languages: 107
- Accuracy: 93.3%
- Size: ~85 MB
- Use case: detect each speaker's language from
  their concatenated audio before STT

Integration point: after `extract_speaker_audio`,
before `transcribe_audio`. Run language detection
on each speaker's WAV → pass detected language
to Canary `source_lang`.

Advantage over hint parsing: automatic, no user
input required. Works for unknown speakers.
Complementary to hint: hint overrides auto-detect.

Level assessment needed: verify SpeechBrain ECAPA
model level (Level 1-2 expected, pre-trained on
VoxLingua107 dataset, CC BY 4.0).

### 3.2 Hungarian Algorithm — speaker→name mapping

When diarization labels (SPEAKER_00-03) need to
be mapped to real names provided in `speakers`
hint, the Hungarian Algorithm finds the optimal
assignment by minimizing a cost matrix.

Used in diarization evaluation (DER computation)
to match predicted speakers to reference speakers.
Same problem as mapping SPEAKER_XX to hint names.

Advantages over current LLM-based `speaker_id`
enrichment:
- Deterministic (no LLM variability)
- Requires a similarity metric (e.g., language
  match, speaking duration proportion, keyword
  overlap)
- scipy.optimize.linear_sum_assignment implements
  it (BSD license)

Could replace or complement `enrich_speaker_id`:
1. Build cost matrix from features (detected lang
   vs expected lang, duration vs expected duration)
2. Run Hungarian → optimal assignment
3. Rename speakers deterministically

### 3.3 Concatenation artifacts

When `extract_speaker_audio` concatenates segments
via ffmpeg `atrim+concat`, abrupt joins between
segments can confuse STT models (burst of noise,
phase discontinuity).

Production recommendation: add short crossfade
(10-50ms) between segments or tiny silence gaps.

ffmpeg: `acrossfade=d=0.01:c1=tri:c2=tri` between
each pair of segments. More complex filter but
avoids STT artifacts at join points.

Impact assessment needed: measure STT accuracy
with/without crossfade on the test meeting.

### 3.4 ±250ms tolerance window

At turn boundaries, STT and diarization timestamps
may differ by up to 250ms. Production systems use
a tolerance window when aligning STT segments to
diarization turns:

```
if abs(stt_seg.start - turn.start) < 0.25:
    assign to this turn
```

This handles the "reconciliation brittleness"
identified by pyannoteAI as the main failure
mode of timestamp-based alignment.

### 3.5 Joint models (MOSS-TD, Sortformer)

End-to-end models that jointly perform STT +
diarization in a single pass, avoiding the
reconciliation problem entirely.

- MOSS-TD: already evaluated (E12.139, GO),
  depends on IA Serving container
- NVIDIA Streaming Sortformer: real-time,
  production-ready, requires GPU
- SLIDAR, DiCoW: research-stage

These represent the future but don't replace the
current pipeline yet (availability constraint).

### 3.6 Canary-Qwen 2.5B

Newer Canary model (June 2025) with SALM
architecture + Qwen3 LLM decoder. Potentially
better accuracy than Canary-1B-v2 for non-English
languages. Model assessment needed (level, license,
benchmarks vs 1B).

## 4. Recommendations for lore-mcp

### Priority 1: Fix reconstruction (timestamps)

Rework `reconstruct_timeline` to use STT segment
timestamps + seg_table mapping instead of
proportional character distribution. This is the
highest-impact fix — eliminates fragmentation,
duplication, and mis-alignment.

Implementation:
1. `transcribe_audio` returns structured segments
   (not just markdown text)
2. `reconstruct_timeline` uses seg_table to map
   each STT segment's relative timestamp to
   absolute position
3. Each segment placed at correct turn by temporal
   overlap (±250ms tolerance)

### Priority 2: Fix language (explicit source_lang)

Canary requires explicit `source_lang`. Three
options in order of preference:

1. **SpeechBrain pre-STT detection** — automatic,
   no user input, works for unknown speakers
2. **Parse speakers hint** — "Sonia (speaks
   French)" → fr. Fragile, requires structured
   hint
3. **Source-level lang field** — single language
   per source, doesn't support multilingual

Option 1 is the most robust. Option 2 is a
fallback. Option 3 exists but is insufficient
for multilingual.

### Priority 3: Speaker mapping (after P1+P2)

With correct language and timestamps, the LLM
enrichment `speaker_id` should work better.
Hungarian Algorithm is an alternative if LLM
mapping remains unreliable.

### Deferred

- Crossfade (measure impact first)
- Canary-Qwen 2.5B (assess level + license)
- Joint models (wait for IA Serving container)

## 5. Impact on backlog

E12.153 should be restructured as:

- **E12.153 MVP1**: Preserve STT segment timestamps
  through pipeline + seg_table reconstruction
- **E12.153 MVP2**: SpeechBrain pre-STT language
  detection OR explicit source_lang from hint
- **E12.153 MVP3**: Validate speaker mapping

New items to consider:
- Study: SpeechBrain VoxLingua107 level assessment
- Study: Canary-Qwen 2.5B model assessment
- Study: Hungarian Algorithm for speaker mapping
- Fix: Concatenation crossfade in extract_speaker_audio
