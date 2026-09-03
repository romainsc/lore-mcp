# Grooming E10.25 — Per-model verify_ssl

- **Status:** En attente validation
- **Date:** 2026-09-02

## Problem

`verify_ssl` is currently only supported for the
judge LLM (`judge.verify_ssl` in build config).
Embedding models served via TEI behind a
self-signed certificate (e.g. OpenShift internal
CA) cannot disable SSL verification per model.

The global `LORE_API_VERIFY` env var applies to
all models uniformly, which is too coarse when
some models are on trusted endpoints and others
on self-signed ones.

## Solution

Add optional `verify_ssl` field per embedding
model in the build config YAML.

```yaml
embedding:
  - name: nomic-ai/nomic-embed-text-v2-moe
    mode: api
    api_url: https://tei-nomic.apps.sno.internal/v1/embeddings
    verify_ssl: false
  - name: ibm-granite/granite-embedding-311m-multilingual-r2
    mode: api
    api_url: http://127.0.0.1:8082/v1/embeddings
    # verify_ssl defaults to true
```

### Implementation

1. `Embedder.__init__`: accept optional
   `verify_ssl` parameter (overrides env var)
2. `_load_embedders_from_config_or_args`: read
   `verify_ssl` from each model config dict
3. `build_config.py`: no change needed (embedding
   configs are raw dicts passed through)
4. Tests TDD

### Scope

- Per-model `verify_ssl` in YAML config only
- No change to `LORE_API_VERIFY` env var (global
  fallback)
- No change to judge verify_ssl (already done)

## DoD

1. `verify_ssl: false` per model in build config
2. Embedder respects per-model setting
3. Global env var remains as fallback
4. Tests TDD
5. Configuration docs updated

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
