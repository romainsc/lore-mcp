# Grooming E3.18: Unified add pipeline

## Context

`add_source` only works with markdown (skips
preprocess). 17 MCP tools expose pipeline internals
(`start_build`, `start_preprocess`, `start_enrich`)
instead of user intentions.

LLM evaluation confirms: the LLM hesitates between
tools and must know pipeline internals to choose.

## Design principles

1. **Intent-based tools** — "add to corpus", not
   "preprocess then enrich then ingest"
2. **Sensible defaults** — `add_source(file)` does
   everything automatically from config
3. **Options override defaults** — enrich, preprocess,
   optimize controllable per-call
4. **Collection, not build_dir** — LLM reasons in
   collections, not filesystem paths

## MCP tools after E3.18

### Add tools (3 input modes, same pipeline)

```python
def add_source(
    file: str,
    collection: str = "",
    url: str = "", title: str = "", author: str = "",
    license: str = "", date: str = "", lang: str = "",
    level: str = "",
    enrich: str = "",
    preprocess: bool = True,
    optimize: bool = False,
) -> str:
    """Add one source to the index."""

def add_sources(
    sources: str,       # JSON array of source objects
    collection: str = "",
    enrich: str = "",
    preprocess: bool = True,
    optimize: bool = False,
) -> str:
    """Add multiple sources (inline JSON with metadata)."""

def add_recipe(
    recipe: str,        # path to recipe YAML
    collection: str = "",
    enrich: str = "",
    preprocess: bool = True,
    optimize: bool = False,
) -> str:
    """Add sources from a recipe file."""
```

### Retained tools

```python
search_docs(query, top_k, collection, filter)
list_indexed_sources(collection)
remove_source(source, collection)
list_collections()
start_eval(collection)
start_optimize(recipe, collection)
get_service_status()
lint_source(path)
list_tasks()
get_task_status(task_id)
cancel_task(task_id)
list_pipeline_state()
purge_pipeline_state(...)
```

### Removed tools

- `start_build` → `add_recipe(optimize=true)`
- `start_preprocess` → `add_recipe(preprocess=true)`
  with config `add_source.ingest: false` if needed
- `start_enrich` → option of add_recipe

### Total: ~16 tools (was 17, clearer)

## Options cascade

```
MCP param → config.yaml add_source → pipeline defaults
```

```yaml
# config.yaml
# add_source:
#   enrich: []             # [context, qa, meta]
#   preprocess: true
#   optimize: false
```

## Error handling

- Format not supported → error with supported list
- Missing dependency → error with pip install
- Missing service (LLM, STT) → error naming config key
- Incompatible technique → skip with warning
- Partial success (parse OK, enrich KO) → ingest
  anyway, report failure

Task result:
```python
{"file_count": 1, "chunk_count": 12,
 "warnings": ["stt_correction skipped"],
 "errors": []}
```

## Internal pipeline

All three add tools converge:

```
add_source / add_sources / add_recipe
  → build source list
  → Phase 1: parse all (start Docling, parse N, stop)
  → Phase 2: caption all (start VLM, caption N, stop)
  → Phase 3: enrich all (start LLM, enrich N, stop)
  → Phase 4: ingest all (start TEI, embed+index N, stop)
  → Phase 5: optimize (if requested)
```

Factorized: one start/stop per service, not per source.

`run_build` refactored to use this pipeline internally.

## MVPs

1. **MVP1**: add_source with preprocess (all formats,
   1 source)
2. **MVP2**: add_sources batch + add_recipe
3. **MVP3**: remove start_build/start_preprocess/
   start_enrich, options cascade

## Dependencies

- E3.19 (directories + default collection)
- E3.26 (options naming)

## DoD

- add_source with any format → correct chunks
- add_sources with JSON → batch indexed
- add_recipe replaces start_build
- start_build/start_preprocess/start_enrich removed
- Factorized start/stop per service
- Options cascade verified
- Error handling for all incompatible combinations
- All validated via MCP LLM with existing test fixtures
