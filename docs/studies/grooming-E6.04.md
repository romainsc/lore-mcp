# Grooming E6.04 — Configurable chunking

> Retrospective artifact — grooming occurred in
> conversation (2026-08-31), documented after
> implementation.

## Context

Openshift consumer demand (2026-08-31): AutoRAG
E1.08 benchmark validated 1024/128 as optimal
for bge-m3 on a technical corpus (+13%
answer_correctness vs 2048/128). The defaults
in lore-mcp were hardcoded at 2048/128 and not
configurable without modifying the code.

## Definition of Done

1. `DEFAULT_CHUNK_SIZE` changed from 2048 to 1024
2. `get_chunk_config()` reads `LORE_CHUNK_SIZE`
   and `LORE_CHUNK_OVERLAP` from env vars
3. `ingest_directory()` uses `get_chunk_config()`
   when params not explicitly passed
4. `create_tables()` stores chunk_size/overlap
   in the `meta` table for traceability
5. `discover_collections()` returns chunk params
6. `list_collections()` displays chunk info
7. Tests, docs, EPUBs updated

## MVPs

Atomic change — no sub-MVPs.

## Dependencies

- E4.04 (CLI `lore-mcp index`) will add
  `--chunk-size`/`--chunk-overlap` args later
- No impact on existing `.db` files (new chunks
  use new defaults, old chunks unchanged)

## Design decisions

- **Env vars over CLI**: configurable now without
  waiting for E4.04
- **Meta table storage**: enables traceability
  per collection (which params were used?)
- **No validation constraint**: different
  chunk_size across collections is legitimate

## Status

Implemented, pending user validation.

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by Romain Chantereau.
