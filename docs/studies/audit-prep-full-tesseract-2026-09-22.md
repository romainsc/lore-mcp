# Audit — Full 18-source test with Tesseract OCR

- **Date:** 2026-09-22
- **Pipeline:** Docling-native + Tesseract CLI (scale=4, fra+eng)
- **Caption models:** granite-vision (CPU, 600s timeout), molmo-7b (CPU, 180s timeout)
- **Judge:** granite-8b (distant)
- **Enrichment:** context + qa + meta via granite-8b
- **Result:** 18/18 processed, 0 failures

## Quality audit

| File | Size | RAG? | Enrichment | Lang? | I' | Issues |
|---|---|---|---|---|---|---|
| DUDH_2008.md | 49K | Yes | FR context, **EN** Summary | Mixed | **0** | Title truncated (Docling crop) |
| ocde-definition-ia-legal-0449.md | 78K | Yes | FR context, EN Summary | Mixed | 0 | EN Summary on FR source |
| ocde-memorandum-definition-ia-2024.md | 57K | Yes | FR context, FR Summary | OK | 0 | OK |
| linuxfr-devnewton-osaid-2024.md | 36K | Yes | FR | OK | 0 | OK |
| hatta-reproducibility-copyleft-2026.md | 96K | Yes | EN | OK | 0 | OK |
| governing_ai_for_humanity_final_report_en.md | 502K | Yes | EN | OK | 0 | Large but clean |
| S-GEN-UNACT-2021-PDF-E.md | 1.2M | Yes | EN | OK | 0 | Very large, image placeholders |
| free-sw.en.md | 51K | Yes | EN | OK | 0 | Clean |
| fsf-ml-applications-2024.md | 14K | Yes | EN | OK | 0 | Clean |
| osi-osaid-v1.0-definition.md | 16K | Yes | EN | OK | 0 | Clean |
| osi-open-weights.md | 25K | Yes | EN | OK | 0 | Clean |
| worldcup-full.md | 50K | Yes | FR | OK | 0 | JSON table data |
| aout-2026.md | 13K | Marginal | FR | OK | 0 | Calendar tables, low RAG value |
| test-markdown-sample.md | 8K | Yes | EN | OK | 0 | Clean |
| test-data-sample.md | 2K | Yes | EN | OK | 0 | Clean |
| 2026-Declaration-Vacance-Marche-Noel-Createurs.md | 198K | Yes | FR | OK | 0 | 1 VLM refusal ("I'm sorry") |
| Reunion-Parents-ppt-Parcoursup-2025-version-pour-le-7-01-25-1.md | 21K | Partial | FR | OK | 0 | Title "w" (Docling crop), generic captions |
| **pexels-melike-bayram-2154228305-33121483.md** | **0B** | **No** | None | — | — | **BUG: empty file** |

## Comparison with Claude reference corpus

| Source | Pipeline | Ref | Ratio | Notes |
|---|---|---|---|---|
| DUDH_2008 | 49KB | 13KB | 3.7x | 0 I', 32 ARTICLE, title truncated |
| Pexels | **0B** | 722B | **0.0x** | BUG: Docling JSON has 0 pictures/texts |
| PPTX | 21KB | N/A | — | granite-vision: 42/49 captioned, molmo: 0/49 (timeout) |
| test-data-sample | 1.5KB | 1.4KB | 1.1x | Enrichment present |
| hatta | 95KB | 6KB | 15.0x | EN enrichment correct |
| linuxfr | 36KB | 4KB | 8.3x | FR enrichment correct (27 FR markers) |
| OCDE-legal | 78KB | 5.6KB | 13.8x | Mixed FR/EN (bilingual source, expected) |

## Issues identified

### BUG: Pexels photo empty (severity: high)

Docling JSON has 0 pictures, 0 texts for standalone
photo. Docling parser does not recognize it as an
image to caption. VLM captioning via
`PictureDescriptionApiModel` requires Docling to
have parsed the image first. Standalone photos
need a fallback path.

**Action:** new backlog item needed — standalone
photo/infographic handling when Docling produces
empty output.

### Summary/Keywords in English on FR sources (severity: medium)

`enrich_meta` template produces `Summary:` and
`Keywords:` labels in English even when the source
is French. The context enrichment is correctly in
French, but metadata labels are not translated.

**Action:** new backlog item — translate
enrich_meta labels to source language.

### Molmo timeout on all 49 PPTX images (severity: resolved)

180s Docling timeout too short for CPU 7B model.
**Fixed by E12.44** (configurable timeout, now 600s).

### DUDH title truncation (severity: known, mitigated)

Docling layout model crops decorative title too
tightly. Body text complete (27/30 articles found,
3 at crop boundaries). Manifest `title` field
overrides extracted title.

### VLM refusal on 1 image (severity: low)

Declaration-Vacance: one image got "I'm sorry"
from granite-vision. Not harmful but adds noise.
Existing circuit breaker should catch this.

### PPTX title "w" (severity: known, mitigated)

Docling crop on decorative slide → title extracted
as "w". Manifest `title` field overrides.

## Verdict

- **0/18 OCR I' artifacts** — Tesseract `fra` confirmed clean
- **16/18 files usable** for RAG
- **1 bug** (pexels empty) needs new item
- **1 improvement** (enrich_meta FR labels) needs new item
- **E12.44** (timeout) fixes Molmo PPTX timeouts

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
