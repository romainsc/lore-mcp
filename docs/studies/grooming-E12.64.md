# Grooming E12.64 — Sub-source checkpoint for captioning

- **Status:** Prêt
- **Date:** 2026-09-24

## Problem

PPTX with 49 images takes 2h captioning. Interrupt
at image 30 = all 49 re-done. Images skipped
(too small, error) are re-submitted uselessly.

## Solution

Per-image status in report. Docling JSON saved
after each captioned image. Resume from Nth image.

### Image statuses

- captioned: VLM description obtained
- skipped: excluded (too small, circuit breaker)
- error: VLM failed (timeout, refusal)
- pending: not yet processed

### Resume logic

1. Load Docling JSON (contains descriptions from
   previous run if saved after each image)
2. Read report for image statuses
3. Skip captioned/skipped/error images
4. Submit only pending images to VLM
5. After each image: save JSON + update report

### Docling JSON as persistent state

caption_with_docling saves JSON after EACH image:
- doc.save_as_json(path) after PictureDescription
- On reload, existing descriptions are preserved
- Only new images need VLM calls

### Impact code

1. checkpoint.py: mark_image(phase, source, idx, status)
   get_image_status(phase, source, idx)
2. caption_with_docling: filter elements by status,
   save JSON after each image
3. __init__.py phase 2: pass checkpoint to captioning

## DoD

1. Per-image status in checkpoint (captioned/skipped/error/pending)
2. Resume at Nth image (skip already processed)
3. Docling JSON saved after each image
4. Exclusion decisions persisted
5. Tests

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
