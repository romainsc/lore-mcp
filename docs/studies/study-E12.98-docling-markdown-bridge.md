# Study E12.98: Docling Markdown Bridge for Universal HybridChunker

> Date: 2026-09-29
> Status: Verified (tested on 4 sources)

## Goal

Validate that markdown produced by our parsers (trafilatura,
markitdown, STT) can be loaded into Docling's Markdown backend
to produce a structured DoclingDocument usable by HybridChunker.

## Availability

- `InputFormat.MD`: available in Docling v2.107.0
- `HybridChunker`: available in docling-core
- Both work without additional dependencies.

## Results — Per-source comparison

| Source | Type | Input chars | Roundtrip chars | Loss | Tables | Q&A preserved | Summary preserved | Hybrid chunks | MdSplit chunks |
|---|---|---|---|---|---|---|---|---|---|
| free-sw.en.md | HTML (trafilatura) | 51686 | 51589 | 0.2% | 0 | ✓ | ✓ | 29 | 65 |
| test-data-sample.md | CSV (markitdown) | 1633 | 1930 | -18.2%* | 1 | ✓ | ✓ | 2 | 2 |
| eEBv0STiYhI.md | Video STT | 65020 | 64849 | 0.3% | 0 | ✓ | ✓ | 48 | 88 |
| open-source-ai-definition.md | HTML (trafilatura) | 14011 | 13980 | 0.2% | 0 | ✓ | ✓ | 8 | 18 |

*Negative loss = Docling added formatting (table padding).

### HybridChunker characteristics

- **100% heading context** on all sources — every chunk
  carries its heading path
- **Fewer, larger chunks**: ~2× fewer than MdSplit (avg
  1500 chars vs 800 chars). Better for context-heavy RAG
- **max_tokens=512** parameter controls chunk size via
  tokenizer, not character count

### Enrichment annotations

All preserved through the Docling markdown round-trip:
- Q&A questions (`Q:`): 18/18 ✓
- Summaries (`Summary:`): 6/6 ✓
- Keywords (`Keywords:`): 6/6 ✓

### Round-trip fidelity

- **Content loss < 0.3%** for all sources — minor
  whitespace normalization (blank lines condensed)
- **Empty headings dropped** (`## ` with no title) —
  correct behavior
- **Tables expanded** in CSV source (+18%) — Docling
  pads table cells for alignment
- **Line count reduced** (~30% fewer lines) — blank
  line condensation, not content loss

### Base64 images

No prep files contained base64 images (captioning
replaced them with text descriptions). Not tested.
Would need verification if pipeline changes.

## Recommendation: GO

The Docling Markdown bridge works reliably:

1. **Content preserved** — <0.3% loss, all enrichment
   annotations survive
2. **Structure detected** — tables identified, headings
   parsed, hierarchy reconstructed
3. **HybridChunker superior** — 100% heading context,
   fewer chunks, no table splits

### Implementation path

In `ingest.py`, after reading the preprocessed `.md` file:

```python
# Current:
chunks = chunk_document(text, rel, chunk_size, chunk_overlap)

# Proposed:
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker import HybridChunker

converter = DocumentConverter()
doc = converter.convert(str(md_file)).document
chunker = HybridChunker(max_tokens=chunk_size // 4)
chunks = [{"content": c.text, ...} for c in chunker.chunk(doc)]
```

### Effort: LOW

- Change in `ingest.py` only (chunking step)
- No change to preprocess pipeline
- No change to parsers (trafilatura, markitdown, STT)
- Fallback to MdSplit if Docling not installed

### Trade-offs

- **Pro**: unified chunker, heading context, table integrity
- **Con**: extra Docling parse step (~1s per file), heavier
  dependency for chunking-only use case
- **Mitigated**: Docling is already a required dependency
  for PDF/DOCX parsing
