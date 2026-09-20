# Grooming E12.37 — Whole-document enrichment

- **Status:** Prêt
- **Date:** 2026-09-20

## Problem

Enrichment (context, Q&A, meta) requires
sections with `##` headings. Documents without
headings (CSV, XLSX, standalone images, flat
text) get zero enrichment. test-data-sample:
380 bytes raw vs Claude reference 1.4K with
context + Q&A + summary.

## Solution

When no headings found in document, treat the
entire content as a single section. Generate
summary + Q&A for the whole document.

### Implementation

In enrich.py, before the section-by-section
loop: if no `##` headings found, call the
enrichment functions once on the full text.

```python
sections = split_by_headings(text)
if len(sections) <= 1:
    # No headings — enrich whole document
    text = enrich_context(text, ...)
    text = enrich_qa(text, ...)
    text = enrich_meta(text, ...)
else:
    # Per-section enrichment (existing)
    for section in sections:
        ...
```

## DoD

1. Documents without headings get enrichment
2. Summary + Q&A generated for whole content
3. test-data-sample produces enriched output
4. Documents with headings unchanged
5. Tests pass

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
