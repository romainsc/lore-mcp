# Grooming E12.12 — Table sentinel chunking

- **Status:** En attente validation
- **Date:** 2026-09-09

## Problem

`tables.py` adds `TABLE_SENTINEL_START/END`
markers around markdown tables, but
`chunk_document()` uses `MD_SEPARATORS` which
does not include these sentinels. Tables can
still be split across chunks.

## Solution

Add table sentinels to `MD_SEPARATORS` in
`ingest.py` so the `RecursiveCharacterTextSplitter`
splits on sentinel boundaries before other
separators. This ensures tables stay in one chunk.

```python
MD_SEPARATORS = [
    TABLE_SENTINEL_END,   # split after table end
    "\n## ", "\n### ", "\n#### ",
    "\n\n", "\n", " ", "",
]
```

If a table is larger than `chunk_size`, it stays
in one chunk (the splitter won't split within
sentinel boundaries). This is the desired behavior
— a partial table has no semantic value.

## DoD

1. Add sentinels to `MD_SEPARATORS`
2. Test: table stays in one chunk
3. Test: text after table is in next chunk

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
