# Grooming E12.105 — Build uses wrong chunk params

## Bug

Build report shows chunk_size=512/overlap=64
instead of config.yaml values (1024/128).

In `run_build()` (build.py:85-86):

```python
chunk_sizes = config.optimize_chunk_sizes   # [512, 1024, 2048]
chunk_overlaps = config.optimize_chunk_overlaps  # [64, 128]
```

Then later (build.py:156-157):

```python
winning_chunk_size = chunk_sizes[0]     # 512
winning_chunk_overlap = chunk_overlaps[0]  # 64
```

When `skip_optimize=True` (the default for
add_recipe), optimization is skipped but the
"winning" params default to `chunk_sizes[0]`
which is `512` (first optimize candidate), not
`config.chunk_size` which is `1024`.

## Root cause

The optimize sizes list is used as default for
the final build, even when optimization is
skipped. The code conflates "optimization
search space" with "default build params".

## Fix

When optimization is skipped, use
`config.chunk_size` / `config.chunk_overlap`
directly:

```python
if skip_optimize:
    winning_chunk_size = config.chunk_size
    winning_chunk_overlap = config.chunk_overlap
else:
    winning_chunk_size = chunk_sizes[0]
    winning_chunk_overlap = chunk_overlaps[0]
```

## DoD

- Build without optimize uses config.chunk_size
  (1024) and config.chunk_overlap (128)
- Build with optimize still uses first candidate
  as starting point
- Test: run_build with skip_optimize, verify
  chunk params in .db meta match config
- CI green

## MVP

Single fix in `run_build()`.
