# Study E12.49 — Video ingestion

- **Date:** 2026-09-22
- **Status:** Study complete, implementation deferred

## Approach

Video ingestion = audio extraction + frame capture.

1. **Audio track** → STT via E12.48 (Faster-Whisper)
2. **Frame capture** → keyframes or scene changes
3. **Output** → markdown (transcription) + images
   (captured frames) as orig → standard preprocess

## Frame extraction

**Tool**: ffmpeg (LGPL 2.1+, Level 1)

Strategies:
- **Fixed interval**: 1 frame per N seconds
- **Scene change**: `ffmpeg -vf "select=gt(scene\,0.3)"`
- **Transcription-guided**: extract frame at each
  segment timestamp from STT

Recommendation: scene change detection (no
configuration needed, captures slide transitions).

```bash
ffmpeg -i video.mp4 \
  -vf "select=gt(scene\,0.3)" \
  -vsync vfmt frames/frame_%04d.png
```

## Pipeline

```
video.mp4
  → ffmpeg: extract audio.wav
  → STT API: transcription segments
  → ffmpeg: extract keyframes
  → VLM API: caption keyframes (existing pipeline)
  → combine: markdown with timestamps + image descriptions
  → standard preprocess pipeline
```

## IS requirements

Same as E12.48 (STT service) + existing VLM
service for frame captioning.

## Dependencies

- ffmpeg (system, LGPL 2.1+)
- E12.48 (audio STT)
- Existing VLM captioning pipeline

## Conclusion

Deferred until E12.48 is validated. Video adds
frame extraction complexity on top of audio STT.

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
