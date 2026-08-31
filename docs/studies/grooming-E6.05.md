# Grooming E6.05 — Per-collection metadata

> Retrospective artifact — grooming occurred in
> conversation (2026-08-31), documented after
> implementation.

## Context

Openshift consumer demand: each redistributable
`.db` must be self-contained with bibliographic
information. Search results must include source
attribution (title, author, license). Metadata
must survive migration to pgvector/Milvus (E7.01).

## Definition of Done

1. `sources` table in each `.db` (title, author,
   url, date, license, level)
2. YAML manifest as ingestion entry point with
   per-source bibliographic metadata
3. `search_docs` results include biblio metadata
4. `.json`, `.bib`, `.md` output files generated
   alongside each `.db`
5. Front matter extraction when no manifest
6. Tests, docs, EPUBs updated

## MVPs

| MVP | Scope |
|-----|-------|
| 1 | sources table, manifest parsing, ingest_with_manifest |
| 2 | search_docs includes title/author/license |
| 3 | .json + .bib + .md output generation |
| 4 | Front matter YAML extraction without manifest |

## Dependencies

- E7.01 (backend abstraction) must carry source
  metadata in export/import
- `pyyaml` (transitive dep of sentence-transformers)

## Design decisions

- **Separate sources table** (not a column in
  chunks): normalized, avoids repeating biblio
  per chunk, enables independent source listing
- **YAML manifest**: native to Markdown front
  matter, human-readable, standard
- **BibTeX without dependency**: simple template
  generation, no `bibtexparser` needed
- **Backward compatible**: `.db` without sources
  table still works (LEFT JOIN returns NULL)
- **Portability**: sources table is standard SQL,
  portable to pgvector. For non-SQL backends,
  serialize to `extra` JSON field.

## Status

Implemented (4 MVPs tagged e6.05-mvp1 through
e6.05-mvp4), pending user validation.

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by Romain Chantereau.
