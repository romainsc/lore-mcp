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

## Prerequisites

- Nomic v2 MoE model available on HuggingFace
  (check model ID and license)
- RTX 500 Ada with at least 1.5 GB free VRAM
- `lore-mcp eval` and `optimize --models` working
  (E10.02, E10.09 — implemented)

## Expected output

A study document with:
- Model specs comparison (dims, size, params)
- Latency benchmarks (GPU FP16, CPU)
- Quality comparison (embedding metrics on same
  corpus)
- Recommendation: keep bge-m3, switch to Nomic,
  or use both (different use cases)

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
