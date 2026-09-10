# Grooming E5.11 — Context window retrieval study

- **Status:** Implémenté (study)
- **Date:** 2026-09-10

## Study conclusion

### Adjacent-chunk (E5.08) first

Adjacent-chunk retrieval is the recommended first
implementation:
- No ingestion change (no schema modification)
- Dynamic window at retrieval time (window_size
  configurable)
- Industry standard: LlamaIndex SentenceWindow
  pattern

### Parent-child (E6.08) if adjacent insufficient

If adjacent-chunk does not deliver expected
quality improvement:
- Measure with `optimize` (E10.29)
- If gain < expected, implement parent-child
  (double indexation, parent_id)
- LlamaIndex HierarchicalNodeParser +
  AutoMergingRetriever pattern

### Merge before LLM (confirmed)

Both patterns must merge adjacent/parent chunks
into one continuous text before sending to the
LLM. The LLM receives a coherent passage, not
separate fragments. Score from the matched chunk
is preserved.

Source: LlamaIndex MetadataReplacementPostProcessor,
HiChunk research (arXiv:2509.11552), Chroma
(July 2025).

### No cohabitation

Adjacent and parent-child solve the same problem.
Running both in the same pipeline over-expands
context without value. Pick one per corpus.

### Optimize dimension

Both are dimensions of E10.29 (end-to-end
optimize):
- `context_window: [none, adjacent-1, adjacent-2,
  parent-512]`

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
