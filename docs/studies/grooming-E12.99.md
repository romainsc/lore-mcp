# Grooming E12.99: Docling bridge + HybridChunker

## Context

E12.98 study validated that all markdown sources
(trafilatura HTML, markitdown CSV, STT transcripts)
can be loaded via Docling Markdown backend and
chunked with HybridChunker with better results
than MarkdownTextSplitter:
- <0.3% content loss in round-trip
- 2× fewer chunks (better granularity)
- 100% heading context per chunk
- 0 table splits
- Enrichment preserved (Q&A, Summary, Keywords)

## Scope

Replace MarkdownTextSplitter with Docling bridge
in `ingest.py`. No parser changes — only the
chunking step.

### Current flow (ingest.py)

```
markdown text → MarkdownTextSplitter → chunks → embed → .db
```

### New flow

```
markdown text → Docling Markdown backend → DoclingDocument → HybridChunker → chunks → embed → .db
```

For sources that already have a DoclingDocument
(PDF, DOCX, PPTX via Docling parse), use it
directly — no markdown round-trip.

## Implementation

### ingest.py changes

```python
def _chunk_via_docling(text, source_file, chunk_size):
    """Load markdown into Docling, chunk with HybridChunker."""
    from docling.document_converter import DocumentConverter
    from docling_core.transforms.chunker import HybridChunker
    import tempfile
    
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w",
                                     encoding="utf-8", delete=False) as f:
        f.write(text)
        tmp_path = f.name
    
    converter = DocumentConverter()
    doc = converter.convert(tmp_path).document
    
    chunker = HybridChunker(max_tokens=chunk_size)
    chunks = list(chunker.chunk(doc))
    
    return [{"source_file": source_file,
             "chunk_index": i,
             "content": c.text,
             "metadata": json.dumps({"headings": c.meta.headings})}
            for i, c in enumerate(chunks)]
```

Replace `chunk_document()` call with
`_chunk_via_docling()` in `_ingest_source()`.

### Keep MarkdownTextSplitter as fallback

If Docling is not installed (optional dep), fall
back to MarkdownTextSplitter. Same as current
behavior for parse (Docling optional).

### Parent-child chunking

HybridChunker supports hierarchical chunking
natively — evaluate if it replaces the custom
parent-child implementation (E6.08).

## DoD

- `_chunk_via_docling()` in ingest.py
- All sources chunked via Docling bridge
- MarkdownTextSplitter fallback if no Docling
- Tests: same source, both chunkers, compare counts
- Eval: NDCG/recall before vs after on test-redist
- No parser changes (trafilatura, markitdown, STT)

## Risks

- Docling Markdown backend may not reconstruct
  all markdown structures perfectly (base64 images,
  complex nested lists)
- HybridChunker token counting may differ from
  character-based chunk_size
- Performance: extra Docling parse step per source
  at ingest time (not preprocess)
