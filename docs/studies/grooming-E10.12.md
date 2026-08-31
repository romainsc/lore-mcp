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

## Default model change

bge-m3 is classified **Level 4 (Opaque)** per
the project's free AI policy (openshift
conformite-embedding study). It is excluded.

**New default: `nomic-ai/nomic-embed-text-v2-moe`**
(Level 2 — Libre quasi-reproducible, Apache 2.0,
multilingual, 768d).

bge-m3 remains documented as technical reference
baseline (historical benchmark) with explicit
derogation note.

Granite R2 311M documented as Red Hat alternative
(Level 3 — Transparent, Apache 2.0, 768d).

Changes:
- `DEFAULT_MODEL` in embedder.py
- CLAUDE.md technology table
- README.md
- architecture.md, configuration.md
- ADR-005: default model change

## DoD

1. Change DEFAULT_MODEL to nomic-embed-text-v2-moe
2. ADR-005: model change rationale
3. New section in `docs/configuration.md` for TEI
4. Three TEI container recipes (Nomic, Granite R2,
   bge-m3 as reference)
5. models.yaml example for multi-model optimize
6. GPU sharing note
7. Derogation note for bge-m3

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
