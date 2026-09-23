# Grooming E12.55 — Frame extraction: OCR-guided strategy

- **Status:** Prêt
- **Date:** 2026-09-23

## Problem

Scene change detection (ffmpeg select=gt(scene,N))
detects visual changes (lighting, camera motion),
not slide content changes. On desynchronized camera
captures, it misses slide transitions and captures
false positives (lighting variations).

## Solution

Extract 1 frame per N seconds, OCR each, keep only
frames where text content changes significantly.

### Algorithm

```
1. ffmpeg: extract 1 frame every 30s
2. For each frame: tesseract → text (using manifest lang)
3. Compare text[n] vs text[n-1]:
   changed_words / total_words ratio
4. If ratio > threshold → keep frame
5. Always keep first frame
```

### Config

```yaml
parse:
  video_frame_strategy: ocr    # scene|interval|hybrid|ocr
  video_frame_interval: 30     # seconds
  video_scene_threshold: 0.3   # for scene strategy
  video_ocr_change_threshold: 0.3  # for ocr strategy
```

### Language

OCR uses `lang` from manifest (ISO 639-3, same
format as Tesseract langpacks). Passed directly
to `tesseract -l {lang}`. No conversion needed.

Slide OCR doesn't need perfect accuracy — only
enough to detect content changes between frames.

### Implementation

New function in parse.py:

```python
def _extract_frames_ocr_guided(
    video_path, output_dir, interval=30,
    change_threshold=0.3, ocr_lang="eng",
):
```

parse_video selects strategy based on config:
- "scene" → current ffmpeg scene change
- "interval" → fixed interval
- "hybrid" → scene + interval, deduplicated
- "ocr" → OCR-guided (this item)

### Dependencies

- Tesseract (already installed)
- ffmpeg (already installed)
- No new Python dependency

## DoD

1. _extract_frames_ocr_guided function
2. parse_video supports video_frame_strategy config
3. 4 strategies: scene, interval, hybrid, ocr
4. OCR uses manifest lang
5. Tests
6. E12.53/54 (interval, hybrid) implemented alongside

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
