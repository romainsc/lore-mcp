# Grooming E3.18: add_source full pipeline

## Context

`add_source` with existing .db calls `ingest_source`
which does `read_text()` directly — no parsing, no
preprocessing, no enrichment. Only markdown works.
PDF/HTML/DOCX/video/audio produce garbage chunks.

The "no .db" path already calls `run_build` (full
pipeline). The "db exists" path shortcuts everything.

## Root cause

`add_source` = preprocess + ingest for one file.
The "db exists" path skips preprocess entirely.

## Design

### Unified flow

Both paths (db exists or not) run the same pipeline:

```
add_source(file, build_dir, collection, ...)
  1. Create temp recipe: {collection, sources: [{file}]}
  2. preprocess_sources(recipe, build_dir, config)
     → parse (Docling/trafilatura/markitdown/STT/VLM)
     → clean_text
     → enrich (if configured: context, Q&A, meta)
     → write prep .md
  3. if .db exists:
       ingest_source(db, prep_md, embedder)
     else:
       run_build(recipe, build_dir, config)
  4. _invalidate_db()
  5. cleanup temp files
```

### Collection parameter

```python
def add_source(file, build_dir, collection="",
               url="", title="", lang=""):
```

- Single-collection: ignored (one .db)
- Multi-collection + collection specified:
  `collection_db_path(build_dir, collection)`
- Multi-collection + no collection + >1 .db:
  error "specify collection"
- Multi-collection + no collection + 1 .db:
  use that .db

Same pattern as `search_docs(collection="")`.

### remove_source — same fix

```python
def remove_source(source, build_dir, collection=""):
```

Same collection resolution logic.

## MVPs

1. **MVP1**: preprocess before ingest in "db exists"
   path. All formats work. No collection param yet.
2. **MVP2**: `collection` parameter on add_source
   and remove_source.

## DoD

- add_source with PDF → chunks from parsed text
- add_source with HTML → trafilatura extraction
- add_source with video → STT + frames (if configured)
- add_source with enrichment config → enriched chunks
- add_source(collection="X") → correct .db targeted
- remove_source(collection="X") → correct .db targeted
- Multi-collection + no collection + >1 .db → error msg
- Tests: add PDF, add HTML, add with collection

## Risks

- preprocess_sources for a single video/PDF can take
  minutes (STT, VLM captioning). Acceptable — add_source
  runs as background task.
- preprocess_sources writes to build_dir/prep/ which
  accumulates files. Cleanup after ingest.
- Enrichment requires LLM server running. If not
  configured, preprocess still runs (parse + clean only).
