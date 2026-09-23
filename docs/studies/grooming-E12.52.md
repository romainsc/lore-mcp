# Grooming E12.52 — Video frame captioning with transcript context

- **Status:** Prêt
- **Date:** 2026-09-23

## Problem

parse_video inserts scene change frames as base64
inline. clean_text strips them to empty "frame"
alt text. The images are never described by VLM.

## Solution

After STT (phase 1.6), extract base64 frames from
the markdown, send each to VLM with surrounding
transcript context, replace base64 with the
contextual description.

### Context extraction

For each frame at timestamp T:
- context = text from previous block + current
  block + start of next block
- prompt includes the context so VLM understands
  what the slide illustrates

### Prompt

```
This image appears at [{timestamp}] in a talk.
The speaker is saying: {context}
Describe what the slide or visual shows, focusing
on diagrams, text, and information visible.
```

### Pipeline insertion

After phase 1.6 (STT), before phase 2 (Docling
captioning). Uses same VLM as caption_primary
(granite-vision). Start/stop via IS lifecycle.

```
Phase 1.6: STT → markdown with base64 frames
Phase 1.7: For each ![frame](base64,...):
  → extract timestamp from preceding ## heading
  → gather context (prev + current + next block)
  → decode base64 → temp .png file
  → VLM API call with image + context prompt
  → replace ![frame](base64) with text description
```

### Reuse

Uses caption_standalone_image pattern (E12.45)
but with contextual prompt instead of generic.

## DoD

1. Video frames captioned by VLM with transcript
   context
2. base64 replaced by contextual description
3. VLM started/stopped via IS lifecycle
4. Prompt includes surrounding transcript text
5. Tests

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
