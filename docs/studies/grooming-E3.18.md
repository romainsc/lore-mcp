# Grooming E3.18: add_source full pipeline

## Context

`add_source` with existing .db calls `ingest_source`
which does `read_text()` directly — no parsing, no
preprocessing, no enrichment. Only markdown works.
PDF/HTML/DOCX/video/audio produce garbage chunks.

## Root cause

`add_source` = preprocess + ingest for one file.
The "db exists" path skips preprocess entirely.

## Design

### Signature

```python
def add_source(
    file: str,
    collection: str = "",
    url: str = "",
    title: str = "",
    lang: str = "",
    enrich: str = "",
    preprocess: bool = True,
) -> str:
```

- `file`: path to source file (any supported format)
- `collection`: target collection name (required in
  multi-collection, optional in single-collection)
- `enrich`: comma-separated techniques override
  (default from config.yaml `add_source.enrich`)
- `preprocess`: skip preprocess if False (file is
  already clean markdown)

No `build_dir` parameter — resolved internally:
- Single-collection: `Path(config.db_path).parent`
- Multi-collection: `config.db_dir / collection /`

### remove_source

```python
def remove_source(source: str, collection: str = ""):
```

No `build_dir`. Same collection resolution.

### Options cascade

```
MCP params → config.yaml add_source → pipeline defaults
```

config.yaml:

```yaml
add_source:
  enrich: [context, qa, meta]
  preprocess: true
```

The LLM can override per-call:
- `add_source(file, enrich="meta")` → only meta
- `add_source(file, preprocess=false)` → skip parse,
  assume file is clean markdown

If no config and no MCP param, pipeline defaults
apply (no enrich, preprocess=true).

### build_dir resolution

Implicit from collection:
- Single-collection:
  `build_dir = Path(config.db_path).parent`
- Multi-collection:
  `build_dir = Path(config.db_dir) / collection`

The .db, prep/, and intermediates all live in
build_dir. The LLM never sees filesystem paths.

### Pipeline flow

```
add_source(file, collection="docs-libre", enrich="context,qa")
  1. Resolve build_dir from collection
  2. Create temp recipe: {collection, sources: [{file}]}
  3. preprocess_sources(recipe, build_dir, config)
     → parse (Docling/trafilatura/markitdown/STT/VLM)
     → clean_text
     → enrich (techniques from param or config)
     → write prep .md
  4. Find .db:
     if exists: ingest_source(db, prep_md, embedder)
     else: create .db + ingest
  5. _invalidate_db()
  6. Cleanup temp recipe
```

## MVPs

1. **MVP1**: preprocess before ingest, all formats.
   build_dir from config.db_path parent. No collection
   param yet. No options override.
2. **MVP2**: collection param → build_dir resolution.
   remove_source(collection) same fix.
3. **MVP3**: options cascade (enrich, preprocess)
   from config.yaml + MCP param override.

## DoD

- add_source with PDF → parsed + chunked correctly
- add_source with HTML → trafilatura extraction
- add_source with video → STT + frames (if configured)
- add_source with enrich config → enriched chunks
- add_source(collection="X") → correct .db targeted
- add_source(preprocess=false) → skip parse, direct ingest
- add_source(enrich="meta") → overrides config default
- remove_source(collection="X") → correct .db
- Multi-collection + no collection → error msg
- Tests: add PDF, add HTML, add with collection,
  add with enrich override

### Error handling

Incompatible source + options must produce clear
errors, not silent failures:

- **Format not supported**: file extension not
  recognized → error with supported formats list
- **Missing dependency**: PDF without docling,
  HTML without trafilatura → error with install
  instruction (`pip install lore-mcp[parse]`)
- **Missing service**: enrich without LLM configured,
  video without STT configured → error naming the
  missing config key
- **Incompatible technique**: stt_correction on a
  non-audio/video source → skip with warning in
  task result (not an error — the technique is
  simply not applicable)
- **Partial success**: parse OK but enrich fails →
  ingest the parsed content, report enrich failure
  in task result. Don't block indexation for
  optional enrichment failure

The task result dict includes:
```python
{
    "file_count": 1,
    "chunk_count": 12,
    "warnings": ["stt_correction skipped: not an audio/video source"],
    "errors": [],  # empty = success
}
```

## Risks

- preprocess_sources for a single video/PDF can take
  minutes (STT, VLM captioning). Acceptable — runs
  as background task.
- preprocess_sources writes to build_dir/prep/ which
  accumulates files. Cleanup after ingest.
- Breaking change: `build_dir` removed from MCP
  signature. Pre-release, no users to break.
