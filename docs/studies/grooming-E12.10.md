# Grooming E12.10 — Build integration: autonomous pipeline steps

- **Status:** Prêt
- **Date:** 2026-09-22 (replaces 2026-09-09 version)

## Problem

`run_build` plumbs internal parameters to each
step (chunk_sizes, judge_url, embedders,
preprocess_orig_dir, etc.). Each step should be
autonomous — read its own config, resolve its
own params.

Currently: `run_build` has 20+ parameters and
knows internals of preprocess, optimize, ingest.

## Vision

```
lore-mcp build =
  lore-mcp preprocess  (config → markdown + manifest-prep)
  lore-mcp optimize    (config → winning params)
  lore-mcp ingest      (config + winning params → .db)
  lore-mcp metadata    (manifest + .db → .json/.bib/.md)
```

Each step:
1. Accepts a `LoreConfig` (or reads config.yaml)
2. Resolves its own params from config
3. Produces output files
4. Next step reads those files as input

`run_build` only passes: config + input/output
paths. Zero internal parameter plumbing.

## Interface contracts between steps

```
preprocess:
  IN:  manifest.yaml, docs_dir, config
  OUT: manifest-prep.yaml, prep_dir/*.md

optimize:
  IN:  manifest-prep.yaml, prep_dir, config
  OUT: winning params (model, chunk_size, overlap)

ingest (index):
  IN:  manifest-prep.yaml, prep_dir, config,
       winning params
  OUT: collection.db

metadata:
  IN:  manifest-prep.yaml, collection.db
  OUT: .json, .bib, .md
```

## Implementation plan

### MVP 1: preprocess reads config

`preprocess_sources()` accepts `config: LoreConfig`
and resolves enrich, llm, caption, ocr, judge
internally. Extract resolution logic from
`_run_preprocess()` in server.py.

`run_build` passes only `config=cfg`.

### MVP 2: optimize reads config

`run_optimize()` accepts `config: LoreConfig`
and resolves chunk_sizes, overlaps, top_ks,
metrics, judge, embedders internally.

`run_build` passes only `config=cfg`.

### MVP 3: ingest reads config

`ingest_with_manifest()` accepts `config: LoreConfig`
and resolves embedder internally. Winning params
passed as simple values (output of optimize).

### MVP 4: clean run_build signature

`run_build(manifest_path, docs_dir, output_dir,
config, skip_optimize=False, preprocess=False)`

Six parameters. Everything else resolved by
each component from config.

## DoD

1. Each step accepts `config: LoreConfig`
2. Each step resolves its own params from config
3. `run_build` signature reduced to ~6 params
4. `_run_preprocess()` delegates to component
5. All existing tests pass
6. `lore-mcp build --preprocess --config` works
   with full pipeline (enrich, caption, OCR)

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
