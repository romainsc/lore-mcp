# Grooming E12.23 — OCR artifact correction

- **Status:** Prêt
- **Date:** 2026-09-16

## Problem

RapidOCR (via Docling) extracts text faithfully
but does not understand page layout. Multi-column
text gets interleaved. Known Docling issue
(#2067, #1203, #2201, #3198). The upstream
`ReadingOrderPredictor` uses a rule-based spatial
algorithm with a fixed 15% dilation threshold —
not ML, not configurable, fails on complex
multi-column layouts.

Additionally, minor OCR artifacts: `I'homme`
instead of `l'homme` (apostrophe confusion).

## Solution

Two-part fix, no new dependencies.

### Part A — OCR artifact regex (clean.py)

`_fix_ocr_artifacts(text)` in `preprocess/clean.py`:
- `I'` → `l'` (when followed by lowercase letter)
- Common French OCR substitutions

Called in `clean_text()` pipeline. ~20 lines.

### Part B — Column reorder (parse.py)

`_reorder_columns(doc)` operating on the Docling
document object BEFORE `export_to_markdown()`:

1. Iterate `doc.body.children` (or `doc.texts`)
2. Extract bbox left x-coordinate from
   `item.prov[0].bbox.l`
3. Cluster x-coordinates by gap detection
   (sorted x values, split where gap > threshold)
4. Sort: columns left-to-right, items within
   each column top-to-bottom (by bbox.t)
5. Rewrite `doc.body.children` in corrected order
6. Then call `export_to_markdown()` as before

Scope: only apply when source is an image
(scanned document). Text-native PDFs already
have correct reading order from the PDF text
layer. Detect via file extension
(`IMAGE_EXTENSIONS`).

~50-70 lines. Deterministic, no model needed.

### Bug fix — PPTX caption (parse.py)

Separate from E12.23 but related: Docling
hardcodes `![Image](data:...)` as alt text for
all pictures. `caption_inline_images()` skips
these because alt is non-empty.

Fix: treat generic placeholders as empty:
```python
_GENERIC_ALT = {"image", "figure", "picture",
                "img", "photo"}
```

## Rejected approaches

- **docling-hierarchical-pdf**: pymupdf dep,
  designed for text-native PDFs, author says
  inferior on OCR
- **LLM-based correction**: hallucination risk
  on dense French legal text, expensive,
  non-deterministic. Spatial data already exists
- **Upstream fix**: PR #4153 not yet merged

## DoD

1. Part A: `I'homme` → `l'homme` and similar
   French OCR fixes in clean_text
2. Part B: multi-column documents reordered by
   bbox clustering before markdown export
3. PPTX generic alt text treated as empty for
   captioning
4. DUDH_2008.png produces correctly ordered text
5. Text-native PDFs unaffected
6. Tests for all three fixes

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
