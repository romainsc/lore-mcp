# Grooming E6.01 — Declarative DB sync

- **Status:** Prêt
- **Date:** 2026-09-22

## Problem

`lore-mcp build` does a full rebuild every time.
Adding 1 file to a 100-document corpus means
re-embedding everything (~30 min). No way to
update or remove a single source.

## Vision

The manifest is the source of truth. The DB is
its reflection. `lore-mcp build` synchronizes the
DB to match the manifest — declarative, like
`kubectl apply`.

## Algorithm

```
For each source_file in DB:
  absent from manifest → purge (delete chunks)

For each entry in manifest:
  absent from DB → ingest (chunk + embed + insert)
  present, hash identical → skip
  present, hash different → delete chunks + re-ingest
```

Full rebuild = special case (empty DB or --force).

## Identity and change detection

- **Identity**: `source_file` field (= manifest
  `path`). This is the user's declaration of what
  the file is called in the collection.
- **Change detection**: SHA-256 hash of source
  content, stored in DB alongside source metadata.

If the user renames a file in the manifest, the
old name is purged and the new name is ingested.
This is correct — the user declared a new identity.

## Schema change

Add `content_hash` to the `sources` table (if it
exists) or to a new tracking table:

```sql
CREATE TABLE IF NOT EXISTS source_hashes (
  source_file TEXT PRIMARY KEY,
  content_hash TEXT NOT NULL,
  indexed_at TEXT NOT NULL
);
```

Populated at ingest time. Queried at build time.

## Implementation

1. At build start, load existing source_hashes
   from DB
2. Load manifest, compute hash for each source
3. Diff: purge / skip / re-ingest
4. Report: "3 skipped, 1 updated, 2 new, 1 purged"
5. Update source_hashes after each ingest

### Preprocess interaction

If `--preprocess` is enabled, the hash comparison
uses the preprocessed output hash (not the raw
source hash). A change in preprocessing config
(e.g. new enrich technique) changes the hash →
triggers re-ingest.

Alternative: hash the raw source + preprocessing
config. This detects both content changes and
config changes.

## DoD

1. Build with unchanged manifest skips all sources
2. Adding a source to manifest ingests only it
3. Removing a source from manifest purges it
4. Modifying a source re-ingests only it
5. `--force` does full rebuild (ignore hashes)
6. Report shows skip/update/new/purge counts
7. Performance: skip is O(1) per source (hash lookup)

## Dependencies

- Existing `sources` table in DB (E6.05)
- No new dependencies

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
