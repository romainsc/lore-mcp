# Grooming E12.49 — Video ingestion

- **Status:** Prêt
- **Date:** 2026-09-22

## Problem

Video files (meetings with slides, talks, YouTube)
contain valuable content not indexable today.

## Solution

Extract audio + frames → single markdown file
with transcription and inline base64 frames at
their temporal position. Standard preprocess
pipeline then captions the images and enriches
the text.

### Output format

```markdown
## [00:00:00] Introduction

Bonjour, aujourd'hui nous allons parler de...

![frame](data:image/png;base64,iVBORw0KGgo...)

## [00:02:15] Architecture

Le système est composé de trois couches...

![frame](data:image/png;base64,iVBORw0KGgo...)
```

Single self-contained .md file with base64 inline
images (same pattern as Docling for PDF/DOCX).

### Pipeline

```
video.mp4
  → ffmpeg: extract audio.wav
  → STT API: transcription segments with timestamps
  → ffmpeg: extract frames at scene changes (with timestamps)
  → merge: transcription segments + frames at matching timestamps
  → single .md with inline base64 frames
  → standard preprocess pipeline (VLM caption + LLM enrich)
```

### Frame extraction

Scene change detection via ffmpeg:
```bash
ffmpeg -i video.mp4 \
  -vf "select=gt(scene\,0.3),showinfo" \
  -vsync vfn frames/frame_%04d.png
```

Each frame gets a timestamp from ffmpeg showinfo.
Frame inserted after the transcription segment
whose timestamp is closest.

### Dependencies

- ffmpeg (system, LGPL 2.1+, Level 1)
- E12.48 (STT API for audio transcription)
- Existing VLM captioning pipeline (for frames)

### Config

```yaml
llm:
  - name: whisper
    model: Systran/faster-whisper-large-v3
    api_url: http://127.0.0.1:8093/v1

parse:
  video_scene_threshold: 0.3  # ffmpeg scene change
```

## DoD

1. detect_format recognizes .mp4/.mkv/.webm/.avi
2. ffmpeg extracts audio → STT API → segments
3. ffmpeg extracts frames (scene change) with timestamps
4. Single .md with transcription + base64 frames inline
5. Standard preprocess pipeline captions + enriches
6. Tests

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
