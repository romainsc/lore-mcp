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

## Fix

Add `gc.collect()` before `empty_cache()`:

```python
def unload(self) -> None:
    if self._model is not None:
        del self._model
        self._model = None
        import gc
        gc.collect()
        if torch and torch.cuda.is_available():
            torch.cuda.empty_cache()
    self._api_dim = None
```

`gc.collect()` forces Python to release circular
references and tensor buffers immediately, so
`empty_cache()` can actually reclaim the VRAM.

## DoD

1. `gc.collect()` added to `unload()`
2. Test: mock torch.cuda.empty_cache called after
   gc.collect
3. Documentation updated

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
