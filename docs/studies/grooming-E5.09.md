# Grooming E5.09 — Heading markers in RAG pipeline

- **Status:** Implémenté
- **Date:** 2026-09-08

## Problem

`clean_text()` strips `#` from markdown headings
before chunking. This breaks `MD_SEPARATORS`
(`"\n## "`, `"\n### "`, `"\n#### "`) which are
the primary structural split boundaries for
`RecursiveCharacterTextSplitter`.

Additionally, `clean_text()` is called twice in
the full pipeline:
1. In `preprocess_sources()` (preprocess step)
2. In `_ingest_file()` (build/ingest step)

The strip is idempotent for NFC/HTML/images but
compounds the heading problem.

## Analysis

### What `#` means in the pipeline

| Stage | Role of `#` |
|-------|-------------|
| Source markdown | Heading marker (structural) |
| Chunking (`MD_SEPARATORS`) | **Primary split boundary** — the chunker looks for `\n## ` to split sections |
| Indexed chunk content | Structural context — a chunk starting with `## Authentication` ranks higher for auth queries |
| Search query | Noise — users don't type `## authentication` |

### The 0.69 vs 0.61 observation

Measured locally: query `authentication setup`
scores 0.69, query `## authentication setup`
scores 0.61. This is a **query-side** issue, not
an index-side issue. The `#` dilutes the query
vector, not the chunk vector.

E14.17 found no external academic source for
stripping `#` from indexed content.

### Impact of current strip

1. `MD_SEPARATORS` can't find `\n## ` after strip
   → chunker falls through to `\n\n`, `\n`, ` `
   → **structure-unaware chunking**
2. Chunks lose heading context → retrieval quality
   drops
3. The preprocessing guide (docs/preprocessing.md)
   documents headings as structural signal while
   the code strips them — contradiction

## Recommendation

**Remove `_strip_heading_hashes` from
`clean_text()`.** Keep `#` in chunks — they are
structural signal for both chunking and retrieval.

If query-side `#` is a problem, handle it in
`search_docs()`:
```python
query = re.sub(r"^#{1,6}\s+", "", query.strip())
```

This is a targeted fix that doesn't affect the
index.

## DoD

1. Remove `_strip_heading_hashes` from
   `clean_text()`
2. Update tests (remove strip assertions, add
   heading preservation assertions)
3. Optionally: strip `#` from queries in
   `search_docs()` (separate concern)
4. Update `docs/preprocessing.md` — headings are
   preserved, not stripped
5. Verify chunking works correctly with headings

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
