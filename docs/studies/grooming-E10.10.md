# Grooming E10.10 — Evaluate Nomic v2 MoE locally

- **Status:** Grooming — en attente de validation
- **Date:** 2026-08-31
- **Type:** [E] Étude

## Context

The openshift workspace has deployed Nomic v2 MoE
on the SNO via TEI (E13.25). The model is a
475M-param Mixture of Experts (2-of-8 routing,
137M active per token), 951 Mo safetensors, ~1.2
Go VRAM FP16. It fits on the RTX 500 Ada laptop
GPU (4094 MiB).

Question: can lore-mcp use Nomic v2 MoE in local
GPU mode instead of going through the SNO API?
Benefits: lower latency, frees SNO GPU for the
LLM.

## DoD

1. Load Nomic v2 MoE with sentence-transformers
   on RTX 500 Ada in FP16 mode
2. Benchmark latency (ms/query, ms/batch) vs
   bge-m3 on same hardware
3. Index a test corpus with both models
4. Compare retrieval quality via `lore-mcp eval`
   (embedding metrics: score_spread, source_diversity)
5. If possible, run `lore-mcp optimize --models`
   with both models to get a head-to-head
   comparison
6. Document results in a study
   (`docs/studies/eval-nomic-v2.md`)

## Execution modes

Two approaches for running multiple models:

### In-process (mode: auto) — for evaluation

sentence-transformers loads models one at a time.
On RTX 500 Ada (3.7 GB VRAM):
- bge-m3 FP32: 2.8 GB → fits alone
- Nomic v2 MoE FP16: ~1.2 GB → fits alone
- Both simultaneously: won't fit

For `optimize --models`, models must be loaded
sequentially, unloading the previous one. This
requires `Embedder.unload()` (not yet
implemented — E10.10 scope).

### TEI containers (mode: api) — for production

The user runs TEI (Text Embeddings Inference)
containers and lore-mcp connects via API.

#### Running TEI with Nomic v2 MoE

```bash
podman run -d --name tei-nomic \
  -p 8081:80 \
  --gpus all \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id nomic-ai/nomic-embed-text-v2-moe \
  --dtype float16
```

#### Running TEI with Granite Embedding

```bash
podman run -d --name tei-granite \
  -p 8082:80 \
  --gpus all \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id ibm-granite/granite-embedding-278m-multilingual \
  --dtype float16
```

#### Running TEI with bge-m3

```bash
podman run -d --name tei-bge \
  -p 8083:80 \
  --gpus all \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id BAAI/bge-m3 \
  --dtype float16
```

#### models.yaml for multi-model optimize

```yaml
models:
  - name: nomic-ai/nomic-embed-text-v2-moe
    mode: api
    api_url: http://localhost:8081/v1/embeddings
  - name: ibm-granite/granite-embedding-278m-multilingual
    mode: api
    api_url: http://localhost:8082/v1/embeddings
  - name: BAAI/bge-m3
    mode: api
    api_url: http://localhost:8083/v1/embeddings
```

Note: on a single GPU, run one TEI at a time
or use CPU TEI for smaller models. TEI manages
GPU memory internally.

## DoD (revised)

1. Verify Nomic v2 MoE and Granite model IDs
   and licenses on HuggingFace
2. Document TEI container launch in
   `docs/configuration.md`
3. Add `Embedder.unload()` for in-process model
   switching (free GPU memory between models)
4. Benchmark latency (in-process + TEI) vs bge-m3
5. Compare quality via `lore-mcp eval`
6. Run `lore-mcp optimize --models` with all 3
7. Document results in `docs/studies/eval-nomic-v2.md`

## Prerequisites

- Nomic v2 MoE: `nomic-ai/nomic-embed-text-v2-moe`
  (Apache 2.0, verified)
- Granite Embedding: `ibm-granite/granite-embedding-278m-multilingual`
  (Apache 2.0, verified)
- bge-m3: `BAAI/bge-m3` (MIT, already used)
- RTX 500 Ada (4094 MiB) or TEI containers
- `lore-mcp eval` and `optimize --models` working

## Expected output

Study document (`docs/studies/eval-nomic-v2.md`):
- Model specs (dims, size, params, license)
- Latency benchmarks (GPU FP16, CPU, TEI)
- Quality comparison (embedding metrics)
- VRAM requirements per model
- Recommendation: default model, use cases
- TEI deployment recipes

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
