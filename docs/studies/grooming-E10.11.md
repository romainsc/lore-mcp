# Grooming E10.11 — `Embedder.unload()`

- **Status:** Grooming — en attente de validation
- **Date:** 2026-08-31

## Context

When `run_optimize` iterates over multiple models,
each Embedder keeps its model in GPU memory. On a
laptop with 3.7 GB VRAM, the second model can't
load because the first is still occupying memory.

## Change

Add `Embedder.unload()`:

```python
def unload(self) -> None:
    if self._model is not None:
        del self._model
        self._model = None
        self._api_dim = None
        if torch and torch.cuda.is_available():
            torch.cuda.empty_cache()
```

Call `unload()` in `run_optimize` when switching
from one model to the next. Also call in
`_optimize_ingest` to ensure clean state.

## DoD

1. `Embedder.unload()` implemented
2. `run_optimize` calls `unload()` between models
3. Test: after unload, model is None, embed()
   reloads
4. Test: GPU memory freed (mock torch.cuda)

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
