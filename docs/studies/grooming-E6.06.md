# Grooming E6.06 — Multi-format ingestion study

- **Status:** En attente validation
- **Date:** 2026-09-08

## Problem

lore-mcp preprocess only handles markdown files.
Raw sources come in PDF, HTML, DOCX and other
formats. E12.03 needs a parsing backend to
convert these to markdown.

## Candidates evaluated

### Docling (DS4SD/IBM)

- **License:** MIT
- **Version:** 2.126.0 (2026-09-04)
- **Python:** ≥3.10, <4.0
- **Stars:** 62.9k, LF AI & Data Foundation
- **Formats:** PDF, DOCX, PPTX, XLSX, HTML, EPUB,
  images, LaTeX, audio, email
- **Output:** Markdown, HTML, JSON, DocTags
- **Quality:** 97.9% table extraction accuracy
  (DocLayNet benchmark). Preserves tables,
  headings, reading order, formulas
- **Weight:** Heavy — downloads ~1 GB model
  weights on first run, pulls torch
- **API:**
  ```python
  from docling.document_converter import DocumentConverter
  converter = DocumentConverter()
  doc = converter.convert("file.pdf").document
  print(doc.export_to_markdown())
  ```
- **Slim variant:** `docling-slim` for minimal
  footprint (no AI models, basic extraction)

### trafilatura (adbar)

- **License:** Apache 2.0 (changed from GPL-3.0+
  at v1.8.0 — E14.17 reference outdated)
- **Version:** 2.2.0
- **Python:** ≥3.6
- **Stars:** widely adopted (HuggingFace, IBM,
  Microsoft Research)
- **Formats:** HTML → text/markdown/CSV/JSON/XML
- **Quality:** F1 0.966 (ScrapingHub benchmark).
  Best open-source HTML extractor
- **Weight:** Lightweight, no ML dependencies
- **API:**
  ```python
  import trafilatura
  html = open("page.html").read()
  text = trafilatura.extract(html, output_format="markdown")
  ```

### markitdown (Microsoft)

- **License:** MIT
- **Version:** 0.1.7 (2026-07)
- **Python:** ≥3.10
- **Stars:** 174k
- **Formats:** 15+ (PDF, DOCX, PPTX, XLSX, HTML,
  EPUB, images, audio, CSV, JSON, XML, ZIP)
- **Quality:** Basic text scraping. No OCR, no
  layout detection, poor table handling
- **Weight:** Light (no ML, wraps pdfminer.six,
  mammoth, etc.)
- **API:**
  ```python
  from markitdown import MarkItDown
  md = MarkItDown()
  result = md.convert("doc.pdf")
  print(result.text_content)
  ```

### pymupdf4llm (Artifex)

- **License:** AGPL-3.0 (unified since v1.28.2)
- **Version:** 1.28.2 (2026-08)
- **Python:** 3.10–3.14
- **Stars:** ~2k
- **Formats:** PDF only
- **Quality:** Good table/layout preservation
- **Weight:** Medium
- **API:**
  ```python
  import pymupdf4llm
  md = pymupdf4llm.to_markdown("doc.pdf")
  ```

## Comparison matrix

| Criterion | Docling | trafilatura | markitdown | pymupdf4llm |
|-----------|---------|-------------|------------|-------------|
| License | MIT | Apache 2.0 | MIT | AGPL-3.0 |
| AGPL compat | ✓ | ✓ | ✓ | ✓ |
| PDF quality | ★★★ | — | ★ | ★★ |
| HTML quality | ★★ | ★★★ | ★ | — |
| DOCX | ✓ | — | ✓ | — |
| Format breadth | 10+ | HTML only | 15+ | PDF only |
| Weight | Heavy | Light | Light | Medium |
| Community | 63k ★ | Adopted | 174k ★ | 2k ★ |

## Recommendation

**Two-library strategy** complementing by format:

- **trafilatura** for HTML (best quality, light,
  Apache 2.0)
- **Docling** for PDF/DOCX (best quality, heavy
  but optional dependency)

### Why not markitdown alone?

markitdown covers more formats but with basic
quality. For RAG, conversion quality directly
impacts retrieval quality (~60% per E14.17).
markitdown's poor table handling and lack of
layout detection make it insufficient for
production PDF/DOCX. It could serve as a
lightweight fallback for simple documents.

### Why not pymupdf4llm?

Docling is superior on quality (97.9% vs good)
and covers more formats. pymupdf4llm is
PDF-only. Same license (AGPL-3.0).

### Cascade for E12.03

Each tool handles the formats where it produces
the best quality. No overlap, no ambiguity.

| Tier | Formats | Tool | Why |
|------|---------|------|-----|
| 1 | `.md` | passthrough + clean | Already implemented |
| 2 | `.html` | trafilatura | Best HTML quality (F1 0.966) |
| 3 | `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.epub`, images | Docling | Best structure/table quality (97.9%), broadest coverage |
| 4 | `.csv`, `.json`, `.xml`, other data/text | markitdown | Formats Docling doesn't cover |

Format detection by file extension. Unknown
extensions → error (no silent fallback).

**Complex documents** (image-heavy, bad OCR,
complex layout where standard parsers produce
poor output) — deferred to E12.08. Detection
criteria: lint score on parser output below
threshold → flag for LLM-assisted conversion.
E6.03 (image captioning) subsumed by E12.08.

### Dependency strategy

All parse dependencies are **optional extras**
in pyproject.toml:

```toml
[project.optional-dependencies]
html = ["trafilatura>=2.0"]
pdf = ["docling>=2.100"]
office = ["markitdown>=0.1"]
parse = [
    "trafilatura>=2.0",
    "docling>=2.100",
    "markitdown>=0.1",
]
```

Install by need:
- `pip install lore-mcp[html]` — HTML only
- `pip install lore-mcp[pdf]` — PDF/DOCX/PPTX/XLSX/EPUB/images
- `pip install lore-mcp[office]` — CSV/JSON/XML/other
- `pip install lore-mcp[parse]` — all formats

### Correction: trafilatura license

E14.17 and CLAUDE.md reference trafilatura as
GPL-3.0+. This is outdated — trafilatura changed
to **Apache 2.0** at v1.8.0. Update all
references.

## DoD

1. Recommendation documented (this file)
2. License verified for all candidates
3. API verified (code examples)
4. Integration strategy defined (cascade +
   optional deps)
5. trafilatura license correction propagated

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
