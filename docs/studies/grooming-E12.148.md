# Grooming E12.148 — Fix extract_speaker_audio ffmpeg filter label mismatch

## Problem

`extract_speaker_audio` (diarize.py:126) builds an
ffmpeg `filter_complex` command with non-contiguous
stream labels when segments shorter than 0.05s are
skipped.

## Root cause

```python
for i, (start, end) in enumerate(segs):  # i = enumerate index
    if dur < 0.05:
        continue                          # i skips
    filter_parts.append(f"...[s{i}]")     # labels: s0, s2, s4...

concat_inputs = "".join(f"[s{i}]"
    for i in range(len(filter_parts)))    # labels: s0, s1, s2...
```

When a segment is filtered out, `i` from `enumerate`
creates gaps (s0, s2, s4) but `concat_inputs` uses
`range(len(filter_parts))` producing contiguous
labels (s0, s1, s2). ffmpeg fails because `[s1]`
references a non-existent stream.

With 342 diarization turns across 4 speakers,
micro-pauses < 50ms are virtually certain for every
speaker → 100% failure rate (0 extracts on 4
speakers observed in validation diarize-v18).

## Fix

Use a separate counter instead of `enumerate` index:

```python
valid_idx = 0
for start, end in segs:
    if dur < 0.05:
        continue
    filter_parts.append(f"...[s{valid_idx}]")
    valid_idx += 1
```

Also: removed duplicate `from pathlib import Path`
import (lines 6+8).

## DoD

1. ✅ Fix index in `extract_speaker_audio`
2. ✅ Test with interleaved short segments
3. ✅ Duplicate import cleaned
4. ✅ All 25 diarize tests pass
5. ⬜ CI green
