# Grooming E12.79 + E12.80: Docling image handling

## Context

`PIL UserWarning: Palette images with Transparency
expressed in bytes should be converted to RGBA images`
fires during phase 2 captioning (PPTX slides). Root cause:
Docling's `PictureDescriptionBaseModel.__call__` does
`el.image.convert("RGB")` on palette (P mode) images
with tRNS transparency bytes. This silently drops
transparency, potentially degrading VLM captions.

Docling is aware of the issue — test file
`test_picture_description_rgb_conversion.py` exists,
but only tests RGBA → RGB, not P+tRNS → RGB.

## Analysis (via Codebase-Memory on docling-upstream)

**Two conversion sites in Docling**:
1. `picture_description_base_model.py:102` —
   `el.image.convert("RGB")` (base class for all
   picture description models)
2. `vlm/_utils.py:131` — `normalize_image_to_pil()`
   — same direct `.convert("RGB")`

**Fix**: `img.convert("RGBA").convert("RGB")` — promotes
palette transparency to alpha channel (composites on
white), then drops alpha cleanly.

## E12.79 — Upstream contribution to Docling

### Scope

1. Fix `picture_description_base_model.py:102`:
   `el.image.convert("RGBA").convert("RGB")`
2. Fix `vlm/_utils.py:131`: same pattern
3. Add test for P mode with tRNS in
   `test_picture_description_rgb_conversion.py`

### Prerequisites

- Fork docling-project/docling on GitHub
- Check community repo for AI-generated code policy
- DCO/CLA: none found (MIT license, no DCO.md)

### DoD

- PR submitted to docling-project/docling
- Tests pass (existing + new P mode test)
- Compliant with Docling contribution guidelines

## E12.80 — Improve Docling usage in lore-mcp

### Scope

Three improvements identified from the analysis:

#### MVP1: Local RGBA workaround

In `parse.py:caption_with_docling`, pre-convert
palette images before passing to Docling:

```python
# Line ~188: before creating element
img = pic.image.pil_image
if img.mode == "P":
    img = img.convert("RGBA")
elements.append(
    ItemAndImageEnrichmentElement(item=pic, image=img)
)
```

Eliminates the warning without upstream fix. Can be
removed once Docling ships the fix.

#### MVP2: Phase 2 captioning progress logging

Currently `caption_with_docling` logs total count at
start but no per-image progress. Add per-image logging
inside the loop (line 216-226):

```python
logger.info("  Image %d/%d captioned", elem_idx + 1, len(elements))
```

This was identified as a blind spot — the user sees no
progress during 2h PPTX captioning.

#### MVP3: Phase 1 docling_json validation

After phase 1, verify that all referenced docling_json
files actually exist. If any are missing, invalidate
the phase 1 checkpoint so it re-runs on next build.

Prevents cascading failures where phase 1 checkpoint
marks success despite missing intermediate files (root
cause of the E12.76 crash chain).

### Dependencies

- E12.79 is independent (upstream)
- E12.80 MVP1 is independent (local workaround)
- E12.80 MVP2 is independent
- E12.80 MVP3 depends on understanding checkpoint
  validation (see E12.67)

### DoD per MVP

- MVP1: no PIL warning on PPTX captioning, test
- MVP2: per-image log visible with --verbose
- MVP3: missing docling_json triggers phase 1 re-run
