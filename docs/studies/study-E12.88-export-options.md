# Study E12.88: Docling export_to_markdown Options

> Date: 2026-09-29
> Status: Verified (benchmark performed)

## Options Tested

Tested on governing_ai (PDF, 186 pages) and
Reunion-Parents (PPTX, 49 slides).

## Results — governing_ai (PDF)

| Option | Chars | Lines | Effect |
|--------|-------|-------|--------|
| default | 284,946 | 2,000 | Baseline |
| strict_text | 284,946 | 2,000 | **Deprecated**, no effect |
| compact_tables | 259,060 | 2,000 | -9% chars (shorter table formatting) |
| traverse_pictures | 321,269 | 7,184 | +13% chars, +260% lines (sub-elements inside pictures) |
| no_annotations | 284,946 | 2,000 | No effect (no annotations in this doc) |
| BODY+FURNITURE | 287,367 | - | +0.8% (headers/footers/page numbers) |

## Results — PPTX

No difference across any option. PPTX has no
tables, sub-elements, or annotations — only
text and embedded images.

## Analysis

### compact_tables

Reduces table cell padding. Default:
```
| About the High-level Advisory Body...          |   4 |
|------------------------------------------------|-----|
```
Compact:
```
| About the High-level Advisory Body... | 4 |
| - | - |
```

**Saves 9% on table-heavy PDFs.** Reduces chunk
sizes, more chunks fit in the embedding context.
No semantic loss.

**Recommendation: ENABLE**

### traverse_pictures

Exports sub-elements inside picture items.
Adds 13% content and 260% more lines.
Most are OCR artifacts, not semantically useful.

**Recommendation: DO NOT ENABLE**

### strict_text

**Deprecated** in current docling-core. Ignored.

### included_content_layers

Default BODY only. FURNITURE adds < 1% (noise).

**Recommendation: KEEP DEFAULT**

## Summary

| Option | Recommendation | Impact |
|--------|---------------|--------|
| compact_tables | **Enable** | -9% chunk sizes |
| traverse_pictures | Skip | +13% noise |
| strict_text | N/A | Deprecated |
| BODY+FURNITURE | Skip | +0.8% noise |

## Implementation

One-line change in `parse.py:export_to_markdown`:
```python
doc.export_to_markdown(image_mode=ImageRefMode.EMBEDDED, compact_tables=True)
```
