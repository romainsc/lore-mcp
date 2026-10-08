# Grooming E12.150 — Diarization output quality

## Context

First successful end-to-end diarization via MCP (diarize-v20).
Pipeline: pyannote CPU (342 turns, 4 speakers, 25 min) →
extract_speaker_audio (4 WAV files) → per-speaker STT (4×Canary CPU,
~30 min total) → reconstruct_timeline → enrich speaker_id.

Total: 67 min. Output: 672 lines, 80 KB.

## Reproduction

```
preprocess_source(
    file="/tmp/Réunion suivi école sophie 6 octobre 2026.mp3",
    collection="test-diarize-v20",
    enrich="speaker_id",
    speakers="Christine (teacher, speaks English), Sonia (teacher, speaks French), Sarah (parent), Romain (parent)",
    force=true,
    keep_intermediates=true
)
```

Config: `diarization_device: cpu`, `diarization_model: pyannote-diarize`.
MCP server with `--debug` + stderr wrapper (`/tmp/lore-mcp-stderr.log`).

## Output files

- **Input**: `/tmp/Réunion suivi école sophie 6 octobre 2026.mp3` (27 MB, ~24 min, 32 kbps)
- **phase1-diarize.md**: `workspace-validation/build/test-diarize-v20/.work/Réunion suivi école sophie 6 octobre 2026.phase1-diarize.md` (80086 bytes) — reconstruct_timeline output
- **phase3-enrich.md**: same dir, 79948 bytes — after speaker_id enrichment (almost identical)
- **Final output**: `workspace-validation/build/test-diarize-v20/prep/Réunion suivi école sophie 6 octobre 2026.md` (672 lines)

## Anomalies

### A. Timestamps incorrects (lines 4-93)

**Symptom**: First 18 sections have timestamps 00:00:00 to 00:00:37
for content that spans the first ~1 minute of the meeting.

```
## Christine [00:00:00]    ← 509s of Christine audio → should be ~0:00-1:30
## Sonia [00:00:02]        ← 241s of Sonia audio → should span multiple minutes
## Speaker 3 [00:00:04]    ← 304s of Speaker 3 audio
## Christine [00:00:07]    ← same text as [00:00:00], duplicated
```

After line 117, timestamps progress normally (01:34→24:38).

**Root cause**: `reconstruct_timeline()` in diarize.py maps per-speaker
STT segments back to the original timeline using the diarization turns.
The first turns from pyannote are very short (0.6-3s) and the per-speaker
STT produces one long transcription for each speaker's concatenated audio.
The mapping doesn't correctly distribute the STT text across the original
turn boundaries.

**Fix**: Check how `reconstruct_timeline()` aligns STT segments with
diarization turns. The per-speaker STT transcribes ALL of a speaker's
audio as one block — the timestamps within that block need to be remapped
to the original turn positions, not just placed at the first turn's start.

### B. 8 sections without speaker name

**Symptom**: Lines 94, 99, 112, 137, 147, 152, 157, 191 have headings
like `## [00:00:00]` or `## [00` (malformed).

```
94:## [00:00:00]
99:## [00
112:## [00:00:00]
137:## [00:00:00]
147:## [00:00:00]
152:## [00:00:00]
157:## [00:00:00]
191:## [00:00:00]
```

**Root cause**: `reconstruct_timeline()` failed to resolve the speaker
for these turns. Either the speaker ID is empty, or the turn has no
matching STT segment. Line 99 `## [00` is a truncated heading — suggests
a formatting bug in the markdown generation.

**Fix**: Check `reconstruct_timeline()` for edge cases where speaker
is empty or where the heading format string is malformed.

### C. Duplicated content (Christine sections)

**Symptom**: Christine has 51 sections. The first section (line 4)
contains a long paragraph that is repeated verbatim in sections at
lines 19, 29, 39, 49, 59, 69, 79, 89, 107, 122.

The repeated text is Christine's opening monologue about Sophie's
behavior — this text should appear ONCE, at the correct timestamp.

**Root cause**: Per-speaker STT transcribes ALL of Christine's 509s
of audio as one continuous text. `reconstruct_timeline()` then maps
this text to each of Christine's turns. Since the same full text is
mapped to every turn, it appears duplicated.

The per-speaker STT uses `transcribe_audio()` which returns the full
text with internal timestamps (`## [00:00:00]` sections). But
`reconstruct_timeline()` may not be using these internal timestamps
to split the text across the original turns.

**Fix**: `reconstruct_timeline()` should split the per-speaker STT
text using the internal STT timestamps, then map each segment to the
corresponding diarization turn based on temporal alignment.

### D. Speaker 3 not resolved

**Symptom**: 38 sections with `## Speaker 3` instead of a name.
Pyannote detects 4 speakers (SPEAKER_00 to SPEAKER_03). The
`speakers` hint provides 4 names. The enrichment `speaker_id` should
map SPEAKER_XX to the provided names.

The mapping seems to work for 2 speakers (Christine ↔ SPEAKER_00,
Sonia ↔ SPEAKER_02) but Speaker 3 is not resolved to Sarah or Romain.

**Root cause**: Check the speaker mapping in `reconstruct_timeline()`
or in the speaker_id enrichment. With only 4 known speakers and 4
detected speakers, all should be mapped. SPEAKER_01 may be the
4th (Sarah or Romain) but they spoke very briefly and the name
resolution failed.

**Fix**: Check `enrich_speaker_id()` — does it receive the `speakers`
hint? Does it correctly map all 4 detected speakers to the 4 names?

### E. French transcribed as English

**Symptom**: Sonia (French teacher) and Speaker 3 (parent, French)
have their French speech transcribed in English. E.g., Sonia says
"je suis à l'hôpital" but the text reads "I'm at the hospital".

**Root cause**: Per-speaker STT calls `transcribe_audio()` with no
`language` parameter. Canary-1B-v2 auto-detects language from the
first seconds. If the first segment of the speaker's concatenated
audio starts with a few English words (or silence), the entire
speaker's audio is transcribed as English.

**Fix**: Pass `language` hint to per-speaker STT based on the
`lang` field from the recipe (each source has `lang`). If multilingual,
pass no language and rely on per-section auto-detection.
Or detect speaker language from the first turn and pass it explicitly.

## Technical root cause analysis

### Root cause A — Duplication (anomalies A, B, C)

`_extract_stt_segments` (preprocess/__init__.py:48) creates one
segment `{start: 0.0, end: 10.0}` when STT returns text without
`## [HH:MM:SS]` headings (per-speaker Canary output).

In `reconstruct_timeline` line 226-234, every turn matches this
single segment because `seg_end(10) > consumed` is true for many
turns. Result: full text appended to every turn.

### Root cause B — Language (anomaly E)

Per-speaker STT call (line 993) did not pass `language` parameter.
Canary auto-detects from first seconds. Christine (EN) first →
all speakers transcribed as EN.

## Fix implemented

### MVP1 — Replace reconstruct_timeline (A+B+C)

Replaced timestamp-based segment matching with proportional
character distribution:
- Calculate total_dur per speaker from turns
- Track character cursor per speaker (not time)
- char_len = len(text) * turn_dur / total_dur
- Each text portion used exactly once (cursor never recedes)

Removed broken stt_segments matching path entirely.

### MVP2 — Pass lang to per-speaker STT (E)

Added `language=source_lang` to `transcribe_audio()` call in
the per-speaker STT loop. source_lang from recipe `lang` field.

### MVP3 — Speaker naming (D)

Expected to resolve after MVP1+MVP2 fix input quality.

## DoD

1. ✅ No text duplication (test_no_duplication_with_single_stt_segment)
2. ✅ Speaker always in heading (test_speaker_always_in_heading)
3. ✅ Proportional distribution (test_proportional_distribution)
4. ✅ Per-speaker STT receives lang
5. ⬜ CI green

## Pipeline data for debugging

```
pyannote: 342 turns, 4 speakers
  SPEAKER_00: ~386s audio → Christine
  SPEAKER_01: ~304s audio → Speaker 3 (Sarah or Romain)
  SPEAKER_02: ~241s audio → Sonia
  SPEAKER_03: ~509s audio → Christine (?) — unclear if same as SPEAKER_00

STT per speaker:
  SPEAKER_03: 509s audio, transcribed in ~14 min
  SPEAKER_02: 241s audio, transcribed in ~5 min
  SPEAKER_00: 386s audio, transcribed in ~10 min
  SPEAKER_01: 304s audio, transcribed in ~10 min (estimated)

Total audio by speakers: 509+241+386+304 = 1440s (24 min — matches input)
```

Note: SPEAKER_00 (386s) and SPEAKER_03 (509s) both map to Christine
(51 sections). This means pyannote split Christine into 2 speaker IDs.
The speaker_id enrichment correctly merged them under "Christine" but
the audio is transcribed separately, which contributes to the duplication.
