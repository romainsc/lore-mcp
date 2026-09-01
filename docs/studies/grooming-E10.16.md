# Grooming E10.16 — Fix OOM multi-model GPU

- **Status:** Grooming — en attente de validation
- **Date:** 2026-08-31

## Context

When `run_optimize` switches between embedding
models on a single GPU (e.g. RTX 500 Ada 3.7 GB),
`unload()` calls `del self._model` and
`torch.cuda.empty_cache()`. But Python's garbage
collector hasn't released the tensor references
yet — `empty_cache()` has nothing to free. The
next model tries to load and OOMs.

## Fix (two parts)

### Part 1: gc.collect in unload (done, e10.16)

```python
def unload(self) -> None:
    if self._model is not None:
        del self._model
        self._model = None
        gc.collect()
        if torch and torch.cuda.is_available():
            torch.cuda.empty_cache()
    self._api_dim = None
```

### Part 2: unload all before final reindex

After optimize finishes, all embedders must be
unloaded before the winning model is reloaded
for final indexing. In `build.py:run_build()`,
between optimize and final ingest:

```python
for emb in embedders.values():
    emb.unload()
```

Without this, the last model from the optimize
loop is still in VRAM when the winning model
tries to load → OOM if they're different models.

## DoD (updated)

1. `gc.collect()` added to `unload()` ✅ done
2. Test: gc.collect before empty_cache ✅ done
3. `build.py`: unload all embedders before final
   reindex
4. Test: build multi-model completes on limited
   VRAM (mock)
5. Documentation updated

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
