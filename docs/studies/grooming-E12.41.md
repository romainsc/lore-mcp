# Grooming E12.41 — Caption prompt quality

- **Status:** À valider
- **Date:** 2026-09-20

## Problem

Pexels photo correctly identified as "photo" in
single-model mode (Molmo alone, simple prompt)
but as "presentation slide" in multi-model mode
(OCR context + classify + caption prompt).

The more complex prompt structure degrades
Molmo's classification on photos.

## Solution

Investigate the prompt difference between the
two modes. Compare:
1. Old single-model prompt (caption_image before
   E12.28)
2. New multi-model prompt (caption_image with
   OCR context, alt text, specialized caption)

For a standalone photo with no OCR text and no
alt text, the multi-model prompt should be
equivalent to the single-model prompt. If the
prompt structure itself (empty OCR block, type
classification step) causes the degradation,
simplify: when OCR is empty and alt is empty,
use the simple prompt.

## DoD

1. Root cause identified (prompt comparison)
2. Fix applied
3. Pexels correctly identified as "photo"
4. Documents with OCR context still enriched
5. Tests pass

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
