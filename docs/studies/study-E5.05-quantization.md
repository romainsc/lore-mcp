# Study E5.05 — int8/binary quantification

- **Date:** 2026-09-22
- **Status:** Study complete, implementation deferred

## sqlite-vec quantization support

| Type | Size/vector (768d) | Recall (cosine) | Notes |
|------|:---:|:---:|---|
| float32 | 3072 B | 100% | current default |
| int8 | 768 B (4x) | ~99.5% | use INT8 not UINT8 for cosine |
| bit | 96 B (32x) | ~95% | best as pre-filter for re-ranking |

**Critical**: for cosine similarity, use INT8 not
UINT8. UINT8 shifts values (subtracts minimum),
destroying angle information → 33.8% recall.
INT8 preserves sign → 99.5% recall.

## Nomic v2 MoE quantization

Nomic-embed-text-v2-moe supports:
- **Matryoshka**: 768 → 256 dimensions (3x compact)
- **Binary quantization**: native support (32x)
- **Combinable**: Matryoshka 256d + int8 = 256 B

Usage with sentence-transformers:
```python
model = SentenceTransformer(
    "nomic-ai/nomic-embed-text-v2-moe",
    trust_remote_code=True,
    truncate_dim=256,
)
```

## Recommendations by corpus size

| Corpus | Strategy | Size/vector | Recall |
|--------|----------|:---:|:---:|
| <50K chunks | float32 768d | 3 KB | 100% |
| 50K-500K | int8 768d | 768 B | ~99% |
| >500K | Matryoshka 256d + int8 | 256 B | ~95% |

## Implementation (when needed)

Add `embedding_quantization: float32|int8|bit` to
config.yaml. Change vec0 column type in
`create_tables()`:

```sql
-- int8
CREATE VIRTUAL TABLE chunks_vec USING vec0(
  embedding int8[768] distance_metric=cosine
);

-- bit
CREATE VIRTUAL TABLE chunks_vec USING vec0(
  embedding bit[768] distance_metric=hamming
);
```

Note: bit vectors use hamming distance, not
cosine. Requires different scoring.

## Conclusion

float32 is sufficient for current corpus sizes
(thousands of chunks). Quantization is a
straightforward schema change when .db size
becomes a concern.

## Sources

- sqlite-vec scalar quantization:
  https://alexgarcia.xyz/sqlite-vec/guides/scalar-quant.html
- sqlite-vector quantization benchmarks:
  https://github.com/sqliteai/sqlite-vector/blob/main/QUANTIZATION.md
- Nomic v2 MoE model card:
  https://huggingface.co/nomic-ai/nomic-embed-text-v2-moe

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
