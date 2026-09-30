# Study E12.100: HybridChunker vs Parent-Child Chunking

## Context

E6.08 implemented parent-child chunking: double
indexation where parent chunks (large) provide
context for child chunks (small, embedded). When
a child matches a query, the parent content is
returned to the LLM for broader context.

E12.99 replaced MarkdownTextSplitter with Docling
HybridChunker, which provides heading path metadata
per chunk natively.

## Comparison

### Parent-child (E6.08)

- **Mechanism**: two MarkdownTextSplitters, parent
  (2048 chars) and child (1024 chars). Children
  reference parents via parent_id.
- **Storage**: parent_chunks table + parent_id column
  in chunks table. Double the data in .db.
- **At search**: child matched → parent content
  returned via _expand_parent.
- **Context quality**: parent is a large text block
  around the child. Good context but coarse.

### HybridChunker headings (E12.99)

- **Mechanism**: single chunking pass. Each chunk
  carries its heading path as metadata.
- **Storage**: heading path in chunk metadata JSON.
  No extra table. No double indexation.
- **At search**: chunk returned with heading path.
  LLM sees "Governing AI > Chapter 2 > Risk
  Assessment" alongside the chunk content.
- **Context quality**: heading hierarchy gives
  precise structural context. Less raw text than
  parent but more structured.

## Evaluation

| Criterion | Parent-child | HybridChunker |
|-----------|-------------|---------------|
| Context type | Raw text (parent) | Heading path |
| Storage cost | 2× chunks + parent table | 1× chunks |
| Code complexity | custom chunking + parent table | single chunker |
| Context precision | Coarse (entire parent) | Precise (heading hierarchy) |
| Works for all formats | MarkdownTextSplitter only | All via Docling bridge |

## Recommendation

**Replace parent-child with HybridChunker heading
path.** Rationale:

1. Heading path gives more precise context than
   a parent text block (the LLM knows exactly
   which section the chunk belongs to).
2. Eliminates double indexation (2× storage saved).
3. Removes custom code (chunk_document_parent_child,
   parent_chunks table management).
4. HybridChunker already provides this for free —
   no additional work needed.

The parent_chunks table and _expand_parent search
code are kept for backward compatibility with
existing .db files that used parent-child indexing.
New indexation no longer produces parent chunks.

## Changes applied

- Removed `chunk_document_parent_child()` from
  ingest.py (no longer called).
- Removed parent-child chunking mode from
  `_ingest_file()`.
- Removed `insert_parent_chunk` import from
  ingest.py.
- Kept `parent_chunks` table creation and
  `_expand_parent` search in store.py for
  backward compat with existing .db files.
- Removed `TestChunkDocumentParentChild` tests.
- Kept `TestParentChunkStorage` and
  `TestParentExpansion` tests (backward compat).
