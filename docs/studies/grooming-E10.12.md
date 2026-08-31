# Grooming E10.12 — TEI container documentation

- **Status:** Grooming — en attente de validation
- **Date:** 2026-08-31

## Context

Option B (user-provided IS) needs clear
documentation. Users who want to run embedding
models as persistent services need ready-to-use
container recipes.

## Change

Add a section in `docs/configuration.md`:
"Running external embedding servers".

### Recipes

Nomic v2 MoE:
```bash
podman run -d --name tei-nomic \
  -p 8081:80 \
  ghcr.io/huggingface/text-embeddings-inference:120-1.9.3 \
  --model-id nomic-ai/nomic-embed-text-v2-moe \
  --dtype float16
```

Granite R2 311M:
```bash
podman run -d --name tei-granite \
  -p 8082:80 \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id ibm-granite/granite-embedding-311m-multilingual-r2 \
  --dtype float16
```

bge-m3 (current project default, included as
technical reference baseline — validated by
AutoRAG E1.08 benchmark):
```bash
podman run -d --name tei-bge \
  -p 8083:80 \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id BAAI/bge-m3 \
  --dtype float16
```

### models.yaml example

```yaml
models:
  - name: nomic-ai/nomic-embed-text-v2-moe
    mode: api
    api_url: http://localhost:8081/v1/embeddings
  - name: ibm-granite/granite-embedding-311m-multilingual-r2
    mode: api
    api_url: http://localhost:8082/v1/embeddings
  - name: BAAI/bge-m3
    mode: api
    api_url: http://localhost:8083/v1/embeddings
```

### GPU note

On a single GPU, run one TEI container at a time
(stop the previous before starting the next).
For CPU mode, add `--device cpu` to the podman
run command.

## DoD

1. New section in `docs/configuration.md`
2. Three TEI container recipes (Nomic, Granite R2,
   bge-m3)
3. models.yaml example for multi-model optimize
4. GPU sharing note

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
