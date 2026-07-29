# RAG quality observations from production testing

## Redundancy problem

When querying a corpus of 194 technical documents
(42843 chunks, 2048/128 recursive chunking,
bge-m3 1024d, cosine similarity), consecutive
chunks from the same document frequently appear
in the top-K results because their embeddings
are very similar.

### Example

Query: "Llama Stack embedding provider
configuration"

| Rank | Score  | Source file | Useful? |
|------|--------|-------------|---------|
| 1    | 0.7012 | Working_with_Llama_Stack | Yes — client usage |
| 2    | 0.6588 | Working_with_Llama_Stack | Redundant with #1 |
| 3    | 0.6583 | Working_with_Llama_Stack | Yes — provider env vars |
| 4    | 0.6558 | Working_with_Llama_Stack | Redundant with #1 |
| 5    | 0.6523 | Working_with_Llama_Stack | Background context |

3 out of 5 results are redundant (neighboring
sections of the same document with similar
embeddings). Only 2 chunks bring genuinely
distinct information.

### Impact

- Wastes context window on duplicate content
- Misses relevant chunks from OTHER documents
  that would appear at ranks 6-10
- Gets worse with larger documents (API
  reference docs produce many similar chunks)

### Recommended solutions (by priority)

1. **Per-source cap**: limit results to N chunks
   per source file (e.g. max 2 per file). Simple,
   effective, easy to implement in SQL.

2. **MMR (Maximal Marginal Relevance)**: re-rank
   results to penalize similarity between already
   selected chunks. Better quality but more
   complex (requires pairwise similarity
   computation on the result set).

3. **Chunk deduplication at index time**: detect
   near-duplicate chunks during ingestion and
   merge or skip them. Prevents the problem at
   the source but adds ingestion complexity.

### SQL implementation sketch (option 1)

```sql
-- Per-source cap: max 2 chunks per file
WITH ranked AS (
  SELECT
    content, source_file,
    1 - (embedding <=> $1) AS score,
    ROW_NUMBER() OVER (
      PARTITION BY source_file
      ORDER BY embedding <=> $1
    ) AS rank_in_file
  FROM chunks
  ORDER BY embedding <=> $1
  LIMIT $2 * 3  -- fetch 3x to have room
)
SELECT content, source_file, score
FROM ranked
WHERE rank_in_file <= 2
ORDER BY score DESC
LIMIT $2;
```

For sqlite-vec, the same logic applies using
window functions (supported in SQLite 3.25+).

## top_k observations

Empirical comparison of top_k=3 vs top_k=5:

- top_k=3: the 3 most similar chunks. Risk of
  missing relevant content from other documents.
- top_k=5: adds 2 more chunks (~4 KB extra).
  Negligible cost in Claude's context window.
  Sometimes brings useful complementary context
  (troubleshooting, configurations), sometimes
  just more redundancy.

**Recommendation**: top_k=5 with per-source cap
of 2. This gives diversity across documents
while keeping the most relevant chunks from each.

## Preprocessing observations

### base64 image data

Markdown files converted from PDFs by Docling
contain base64-encoded images. A 70 KB text
document can weigh 1 MB with embedded images.
Lines containing "base64," should be filtered
BEFORE chunking (otherwise chunks are mostly
binary noise).

Exception: if image captioning has been applied,
the captions (text descriptions) should be kept
and only the raw base64 data removed.

### NUL characters

Some PDF-converted documents contain NUL bytes
(\x00) that crash both PostgreSQL and SQLite
inserts. Always strip NUL before inserting.

### Large API reference documents

Documents like "Monitoring_APIs-en-US.md"
(47947 lines, 8535 chunks) dominate the index.
These produce many similar chunks (API endpoint
descriptions follow repetitive patterns). Consider:
- Lower weight for API reference docs
- Or separate index for API docs vs. conceptual
  docs
