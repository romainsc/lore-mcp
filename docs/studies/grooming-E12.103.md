# Grooming E12.103 — add_recipe collection override ignored

## Bug

`add_recipe(collection="X")` in server.py reads
the collection parameter (line 826-832) and uses
it for `col_dir`. But `run_build()` re-reads
the recipe file and uses `recipe["collection"]`
(build.py:122):

```python
# server.py:826-832
if collection:
    col_name = collection
else:
    col_name = recipe_data.get("collection", ...)

# build.py:122
recipe = parse_recipe(recipe_path)
collection = recipe["collection"]  # ignores override
```

Result: the .db is created in the overridden
directory but named with the recipe's collection,
causing a mismatch.

## Fix

Pass `collection` override through config to
`run_build`:

```python
# server.py — before calling run_build:
if collection:
    build_cfg.collection_override = col_name
```

In build.py, after `parse_recipe()`:

```python
collection = getattr(config, "collection_override", "") or recipe["collection"]
```

## DoD

- `add_recipe(collection="custom")` produces
  `custom.db` with collection name "custom"
- Recipe's original collection name preserved
  when no override
- Test: add_recipe with collection override,
  verify .db name
- CI green

## MVP

Single fix — wire collection override through
config into run_build.
