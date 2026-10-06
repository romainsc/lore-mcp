# Grooming E12.123 — Robust preprocess→ingest handoff

## Problem

After preprocess, the ingest step must use the
prep recipe (which has `path: server.md`) to find
preprocessed files. Currently:

- `add_sources._do_adds`: uses original recipe
  (with `file: server.py`) → all files "not found"
- `add_source._do_add`: uses stem glob
  (`server*.md`) → fragile for common stems
  (e.g., two `__init__.py` in different packages)
- `add_recipe._do_recipe`: correct (uses
  `run_build` which switches to prep recipe)

Both `add_source` and `add_sources` also leave
an orphaned recipe-prep in `/tmp/` because
`preprocess_recipe_out` is not set.

## Root cause

`run_build` (used by `add_recipe`) does the
correct handoff:
```python
config.preprocess_recipe_out = str(prep_path)
preprocess_sources(recipe_path, docs_dir, config)
recipe_path = str(prep_path)  # switch
docs_dir = str(Path(_build_dir) / "prep")
```

`_do_add` and `_do_adds` skip this switch.

## Fix

### Part A: `_do_adds` — use prep recipe

```python
if preprocess:
    prep_cfg = copy.copy(cfg)
    prep_cfg.build_dir = str(col_dir)
    prep_recipe = col_dir / (
        Path(tmp.name).stem + "-prep.yaml"
    )
    prep_cfg.preprocess_recipe_out = str(prep_recipe)
    prep_cfg.output_level = "quiet"
    prep_cfg.orig_dir = _orig
    if enrich == "none":
        prep_cfg.enrich_techniques = []
    elif enrich:
        prep_cfg.enrich_techniques = enrich.split(",")
    preprocess_sources(
        tmp.name, _orig or str(col_dir), prep_cfg
    )
    ingest_recipe = str(prep_recipe)
else:
    ingest_recipe = tmp.name

prep_dir = col_dir / "prep"
source_dir = str(prep_dir) if prep_dir.exists() \
    else (_orig or "")

embedder = _get_embedder()
result = ingest_with_manifest(
    ingest_recipe, source_dir, str(col_dir),
    embedder, cfg.chunk_size, cfg.chunk_overlap,
    purge_absent=False,
)
```

### Part B: `_do_add` — use prep recipe to find file

Replace the fragile stem glob with a recipe-based
lookup:

```python
if preprocess:
    ...
    prep_recipe = col_dir / (
        Path(tmp.name).stem + "-prep.yaml"
    )
    prep_cfg.preprocess_recipe_out = str(prep_recipe)
    preprocess_sources(tmp.name, docs_dir, prep_cfg)
    _cleanup_services()

    # Read prep recipe for exact output path
    import yaml as _yaml
    prep_data = _yaml.safe_load(
        prep_recipe.read_text(encoding="utf-8")
    )
    prep_sources = prep_data.get("sources", [])
    if prep_sources:
        prep_path = prep_sources[0].get("path", "")
        md_file = prep_dir / prep_path
    if not md_file.exists():
        md_file = file_path  # fallback
```

### Part C: enriched recipe includes orig_dir

In `preprocess/__init__.py`, line 1166:
```python
enriched = {
    "collection": recipe.get("collection", ""),
    "level": recipe.get("level", ""),
    "sources": enriched_sources,
}
if recipe.get("orig_dir"):
    enriched["orig_dir"] = recipe["orig_dir"]
```

## DoD

- `_do_adds` uses prep recipe for ingest
- `_do_add` uses prep recipe to find exact file
  (no stem glob)
- `preprocess_recipe_out` set in both tools
  (no orphaned temp files)
- Enriched recipe includes `orig_dir`
- Test: add_sources with preprocess=True on
  .py files → all indexed
- Test: add_source on `preprocess/__init__.py`
  → correct file found (not another __init__)
- Existing tests pass
- CI green

## Effort

Moyen — 2 tools + 1 preprocess fix + tests.
