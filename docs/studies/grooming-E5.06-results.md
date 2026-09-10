# E5.06 Results — Reranking model evaluation

- **Date:** 2026-09-10

## Viable models (libre + multilingual FR+EN)

| Model | License | Params | CPU 15 pairs | NDCG@10 |
|-------|---------|--------|-------------|---------|
| BAAI/bge-reranker-v2-m3 | Apache 2.0 | 568M | ~500ms | ~0.553 |
| mmarco-mMiniLMv2-L12-H384-v1 | Apache 2.0 | 33M | ~75ms | ~0.50 |

## Eliminated

- jinaai/jina-reranker-v2-base-multilingual:
  CC-BY-NC-4.0 (non-commercial) — non-compliant
- cross-encoder/ms-marco-MiniLM-L6-v2:
  English only — no French

## Recommendation

Both models as options in config.yaml. Default:
bge-reranker-v2-m3 (best quality). Alternative:
mmarco-mMiniLMv2 (17x smaller, 7x faster).
E10.29 optimize benchmarks both per corpus.

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
