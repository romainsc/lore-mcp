# Grooming E12.102 — Recipe orig_dir ignored by preprocess_sources

## Bug

`parse_recipe()` reads `orig_dir` from recipe
YAML (recipe.py:30). But `preprocess_sources()`
resolves orig_dir only from config:

```python
# line 512
_orig_dir_cfg = getattr(config, "orig_dir", "") or config.preprocess_orig_dir
```

`recipe["orig_dir"]` is never read. This breaks
recipe autoporteuse (E3.34) — the recipe declares
where its sources are, but the pipeline ignores
it.

## Fix

After `parse_recipe()` at line 548, read
`recipe.get("orig_dir")` and use it as fallback
when config has no orig_dir:

```python
recipe = parse_recipe(recipe_path)
recipe_orig_dir = recipe.get("orig_dir", "")
base = Path(docs_base_dir)

# Priority: config.orig_dir > recipe.orig_dir > docs_base_dir
_orig_dir_cfg = (
    getattr(config, "orig_dir", "")
    or config.preprocess_orig_dir
    or recipe_orig_dir
)
```

Same fix in `_phase1_worker()` — it also calls
`parse_recipe()` but ignores `orig_dir`.

## DoD

- Recipe `orig_dir` used when config has none
- Config orig_dir takes precedence over recipe
- Test: recipe with `orig_dir: /path`, verify
  sources resolved from that path
- CI green

## MVP

Single fix — add recipe fallback in both
`preprocess_sources` and `_phase1_worker`.
