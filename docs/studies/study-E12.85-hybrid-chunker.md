# Study E12.85: HybridChunker vs MarkdownTextSplitter

> Date: 2026-09-29
> Status: Verified (benchmark performed)

## Setup

- Corpus: test-redist (21 sources)
- Chunk config: 2048 chars / 64 overlap (MdSplit), 512 tokens (HybridChunker)
- HybridChunker tokenizer: nomic-ai/nomic-embed-text-v2-moe (HuggingFace)
- Docling-core version: installed in .venv

## Benchmark Results

| Source | MdSplit chunks | Hybrid chunks | MdSplit avg | Hybrid avg | Hybrid headings |
|--------|---------------|---------------|-------------|------------|-----------------|
| osaid (HTML) | 9 | 11 | 1561 | 816 | 100% |
| governing_ai (PDF) | 277 | 212 | 1706 | 1236 | 100% |
| pptx (PPTX) | 48 | 10 | 1831 | 1264 | 100% |

## Table Integrity

| Method | Table splits detected |
|--------|----------------------|
| MarkdownTextSplitter | 3 |
| HybridChunker | 0 |

HybridChunker never splits tables across chunk boundaries.

## Heading Context

- **MdSplit**: 15% of chunks start with a heading (the rest lack structural context)
- **HybridChunker**: 100% of chunks carry heading metadata (`meta.headings` path from root)

This heading metadata could be prepended to chunks for better retrieval ("Section: Executive summary > 1.2 Goals").

## Qualitative Comparison (governing_ai chunk #5)

**MdSplit** produces a table of contents fragment:
```
| About the High-level Advisory Body... | 4 |
| Executive summary | 7 |
```

**HybridChunker** produces a coherent paragraph with context:
```
[Heading: Executive summary]
Artificial intelligence (AI) is transforming our world.
This suite of technologies offers tremendous potential...
```

## Limitations

HybridChunker **only works with Docling-parsed sources**:
- ✓ PDF, DOCX, PPTX, XLSX, images (Docling backend)
- ✗ HTML (trafilatura), markdown, CSV/JSON (markitdown), video transcripts

Requires a `DoclingDocument` object (docling.json). lore-mcp's
`_cleanup_phase_files` currently deletes these after phase 4.

## PPTX Concern

PPTX produced only 10 chunks (vs 48 with MdSplit). Each PPTX slide
becomes one chunk regardless of content density. For long presentations,
this may reduce retrieval granularity.

## Recommendation

**Keep MarkdownTextSplitter as default** (universal, works on all formats).

**Offer HybridChunker as optional** for Docling sources via recipe option
(`chunking_mode: hybrid`). Benefits: table integrity, heading context.

**Priority: LOW.** The heading hierarchy fix (E12.84) already improved
MdSplit quality. The table splits (3 detected) are edge cases. The 
heading context advantage is real but can be partially addressed by
prepending section paths to chunks without changing the chunker.

**Implementation effort** (if chosen):
- Preserve docling.json through to ingest (don't clean up)
- Add `chunking_mode: hybrid` to recipe options
- Fallback to MdSplit for non-Docling sources
- ~1 day of work
