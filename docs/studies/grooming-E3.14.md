# Grooming E3.14: Incremental ingest path

## Context

`add_source` MCP tool wraps `run_build` (batch
pipeline) to index a single file. `run_build`
calls `create_tables` which recreates tables if
chunk params differ from the existing .db,
destroying all existing data. Found by E12.97
MCP LLM validation.

Root cause: no incremental ingest path. The batch
pipeline (`run_build`) and the incremental
operations (`add_source`, `remove_source`) need
different code paths.

## Current flow (broken)

```
add_source(file, build_dir)
  → create temp recipe with 1 source
  → run_build(recipe, docs_dir, build_dir, cfg)
    → create_tables(chunk_size=512, overlap=64)  ← DESTROYS existing
    → ingest_with_manifest()
    → optimize (skipped)
```

## Proposed flow

```
add_source(file, build_dir)
  → find .db in build_dir
  → if .db exists:
      → read meta (model_name, model_dim, chunk_size, chunk_overlap)
      → create_embedder matching model
      → validate_model (rejects if model mismatch)
      → preprocess file (clean_text, parse if needed)
      → _ingest_file(db, file, embedder, chunk_size, chunk_overlap)
  → if no .db:
      → fall back to run_build (creates fresh .db)
```

## Implementation

### New function: `ingest_source()` in ingest.py

```python
def ingest_source(
    db_path: str,
    md_file: Path,
    embedder: Embedder,
    source_meta: dict | None = None,
) -> dict:
    """Add a single source to an existing .db.

    Reads chunk params from db meta. Does not call
    create_tables. Raises if model mismatch.
    """
    db = open_db(db_path)
    validate_model(db, embedder.model_name, embedder.model_dim)

    meta = dict(db.execute("SELECT key, value FROM meta").fetchall())
    chunk_size = int(meta.get("chunk_size", DEFAULT_CHUNK_SIZE))
    chunk_overlap = int(meta.get("chunk_overlap", DEFAULT_CHUNK_OVERLAP))

    rel = md_file.name
    # Delete existing if re-indexing
    delete_source_chunks(db, rel)

    n = _ingest_file(db, md_file, rel, embedder,
                     chunk_size, chunk_overlap, source_meta)
    db.close()
    return {"file_count": 1 if n > 0 else 0, "chunk_count": n}
```

### Update add_source in server.py

Replace `run_build` call with:
1. Find .db in build_dir
2. If exists → preprocess file, call `ingest_source`
3. If not → call `run_build` (existing behavior, correct for new .db)

### Preprocessing for single file

`add_source` should preprocess the source before
ingesting (parse PDF/HTML, clean text). Use
`preprocess_sources` with a 1-source recipe, or
extract the per-file logic into a reusable
`preprocess_file()` function.

Simplest approach: keep the temp recipe + call
`preprocess_sources`, then call `ingest_source`
instead of `run_build` for the indexing step.

## DoD

- `ingest_source()` in ingest.py: reads params
  from existing .db meta, no create_tables
- `add_source` uses `ingest_source` for existing .db
- Test: add_source on .db with 5 sources → 6 sources,
  5 originals intact
- Test: add_source on empty build_dir → creates .db
- Test: add_source with model mismatch → error
- Test: add_source same file twice → re-indexed
  (old chunks replaced)

## Risks

- Preprocessing a single file outside the batch
  pipeline may miss some steps (dedup, PII).
  Acceptable for incremental add — user can run
  full preprocess separately.
- The embedder mode (builtin vs API) must match
  the model used to build the .db. validate_model
  checks model name, not mode.
