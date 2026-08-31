# Grooming E10.10 — Multi-model local support

- **Status:** Grooming — en attente de validation
- **Date:** 2026-08-31
- **Type:** [P] Implementation

## Context

lore-mcp's `mode: auto` is misleadingly named —
it's actually `sentence-transformers` in-process
mode. Two changes needed:

1. Rename `auto` to reflect what it does
2. Add `Embedder.unload()` so multi-model
   optimize can switch models without VRAM leak
3. Document TEI container setup (option B) for
   users who want external IS

Models are provided by the user via models.yaml.
No hardcoded model comparison — models are
specified in the file.

## Changes

### 1. Rename mode: auto → local

`auto` is misleading — it suggests automatic
backend selection across all options. In reality
it only picks between GPU and CPU via
sentence-transformers in-process.

Rename:
- `auto` → `local` (loads model in-process)
- Keep `gpu`, `cpu` as explicit local variants
- Keep `api` for external endpoints
- `auto` stays as a deprecated alias for `local`

Env var `LORE_EMBED_MODE`: `local` (default),
`gpu`, `cpu`, `api`.

### 2. Embedder.unload()

Free GPU/CPU memory when switching models:

```python
def unload(self) -> None:
    if self._model is not None:
        del self._model
        self._model = None
        if torch and torch.cuda.is_available():
            torch.cuda.empty_cache()
```

`run_optimize` calls `unload()` between models.

### 3. TEI documentation (option B)

Add to `docs/configuration.md` a section on
running external IS containers. Examples:

Nomic v2 MoE:
```bash
podman run -d --name tei-nomic \
  -p 8081:80 \
  ghcr.io/huggingface/text-embeddings-inference:120-1.9.3 \
  --model-id nomic-ai/nomic-embed-text-v2-moe \
  --dtype float16
```

Granite multilingual:
```bash
podman run -d --name tei-granite \
  -p 8082:80 \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id ibm-granite/granite-embedding-278m-multilingual \
  --dtype float16
```

models.yaml:
```yaml
models:
  - name: nomic-ai/nomic-embed-text-v2-moe
    mode: api
    api_url: http://localhost:8081/v1/embeddings
  - name: ibm-granite/granite-embedding-278m-multilingual
    mode: api
    api_url: http://localhost:8082/v1/embeddings
```

## DoD

1. Rename `auto` → `local` (backward compat alias)
2. `Embedder.unload()` — free model memory
3. `run_optimize` calls `unload()` between models
4. TEI container documentation in configuration.md
5. Tests TDD
6. Docs + EPUBs

## MVPs

- **MVP1**: `unload()` + `run_optimize` model
  switching
- **MVP2**: rename `auto` → `local` + backward
  compat
- **MVP3**: TEI documentation in configuration.md

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
