# Grooming E10.03/E10.04 — optimize + manifest

> Retrospective artifact — grooming occurred in
> conversation (2026-08-31), documented after
> implementation.

## Context

E10.03: automated parameter optimization to find
the best chunk_size/overlap/top_k combination.
E10.04 (openshift demand): optimize must support
manifest-driven ingestion to preserve biblio
metadata during parameter sweep.

## Definition of Done

### E10.03 — optimize

1. `lore-mcp optimize` CLI subcommand
2. Vary chunk_size (512, 1024, 2048), overlap
   (64, 128), top_k (3, 5, 10)
3. Generate questions once, reuse across configs
4. Report best configuration with scores
5. `run_optimize()` function in eval.py

### E10.04 — manifest support

1. `--manifest` as alternative to `--source-dir`
2. `ingest_with_manifest()` preserves biblio
3. Deterministic .db naming (`opt-<size>-<overlap>.db`)

## MVPs

Sequential: E10.03 first, E10.04 extends it.

## Dependencies

- E10.02 (eval) — scoring pipeline
- E6.05 (manifest) — ingest_with_manifest

## Design decisions

- **Questions generated once**: fair comparison
  across configurations (same test set)
- **Deterministic naming** (E10.06/07 fix):
  `opt-<size>-<overlap>.db` avoids collision when
  manifest names all .db after the collection.
  Replaces fragile glob+st_mtime pattern.
- **`_optimize_ingest()` helper**: encapsulates
  the ingest-and-rename logic for one config

## Status

Implemented (tags e10.03-mvp2, e10.04),
E10.06/07 fixes applied, pending user validation.

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by Romain Chantereau.
