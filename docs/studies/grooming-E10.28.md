# Grooming E10.28 — Detailed eval report

- **Status:** En attente validation
- **Date:** 2026-09-02

## Problem

The `--verbose` console output truncates
questions, ground truths, and answers. The
`--output` JSON report contains raw data but
is not human-readable. There is no way to review
the full evaluation results for quality analysis.

## Solution

Generate a markdown report file alongside the
JSON report during build/optimize. The report
is structured for human review.

### Report structure

```
# Evaluation Report — <collection>
Generated: <date>

## 1. Questions

| # | Question | Source | Ground truth |
|---|----------|--------|--------------|
| 1 | <full>   | <file> | <full>       |

## 2. Model: <model_name_1>

### Config: chunk=512/64 top_k=3

| # | Question | Answer (retrieved) | Sources | Scores |
|---|----------|--------------------|---------|--------|
| 1 | <full>   | <full context>     | <files> | <all>  |

**Aggregate:** avg=0.48, hit=1.00, mrr=0.90...

### Config: chunk=512/64 top_k=5
...

## 3. Model: <model_name_2>
...

## Appendix: Scoring methodology

- **hit**: 1 if ground truth found in any chunk
- **mrr**: reciprocal rank of first relevant chunk
- **ndcg@5**: position-weighted relevance
- **recall@5**: fraction of relevant chunks found
- **word_overlap**: |GT ∩ chunk| / |GT|
- Relevance threshold: word_overlap ≥ 0.3
```

### Implementation

1. `generate_eval_report_md(questions, all_results,
   best_config, elapsed, path)` in `eval.py`
2. Store per-question `details` in `all_results`
   entries (currently discarded)
3. Call after optimization in `run_optimize` and
   after build in `run_build`
4. Output path: `{db_dir}/eval-report.md` for
   optimize, `{output_dir}/eval-report.md` for
   build
5. `--output` flag writes JSON as before, report
   is always generated

### Dependencies

- E10.27 (heading-based questions) — done
- E10.24 (output management) — done

### Scope

- Markdown file generation only
- No new CLI flag (always generated)
- No external dependencies

## DoD

1. Markdown report file generated at
   `eval-report.md` in the output directory
2. Chapter 1 — Questions: full question text,
   source file, full ground truth (no truncation)
3. Chapter per model: model name as `##` heading,
   section per config (`### chunk=X/Y top_k=Z`),
   each section contains:
   - Full table with: #, question (complete),
     answer (first retrieved context, complete),
     all sources, all individual scores
   - Aggregate scores line below the table
4. Best config highlighted (★) in aggregate
5. Appendix: each metric explained with formula
   or definition, relevance threshold documented
6. Report path printed in the build summary
7. Report generated automatically (no CLI flag)
8. Per-question `details` stored in `all_results`
   (currently discarded after scoring)
9. Tests TDD: report file exists, contains
   expected headings, questions appear in full,
   scores present, appendix present
10. Configuration and architecture docs updated

## Example output

```markdown
# Evaluation Report — ia-libre

Generated: 2026-09-02T21:30:00Z
Best config: ★ nomic-ai/nomic-embed-text-v2-moe
chunk=2048/128 top_k=5 avg=0.2147

## 1. Questions (10)

### Q1 — Embedding engine

- **Source:** architecture.md
- **Ground truth:**

The embedding engine supports GPU, API, and CPU
backends with automatic fallback. Models are
loaded lazily on first query. The fallback chain
is: GPU (CUDA) → remote API → CPU.

### Q2 — Vector storage

- **Source:** architecture.md
- **Ground truth:**

SQLite with sqlite-vec provides single-file
portable vector storage. The vec0 virtual table
stores float arrays for cosine distance search.

---

## 2. ibm-granite/granite-embedding-311m-multilingual-r2

### chunk=512/64 top_k=3

| # | Question | Answer (retrieved) | Sources | hit | mrr | ndcg@5 | recall@5 | word_overlap |
|---|----------|--------------------|---------|-----|-----|--------|----------|--------------|
| 1 | Embedding engine | The embedding engine supports GPU, API, and CPU backends with automatic fallback. Models are loaded lazily on first query. | architecture.md | 1.00 | 1.00 | 1.00 | 1.00 | 0.92 |
| 2 | Vector storage | SQLite with sqlite-vec provides single-file portable vector storage. The vec0 virtual table stores float arrays. | architecture.md | 1.00 | 1.00 | 1.00 | 1.00 | 0.88 |

**Aggregate scores:**

| Metric | Avg | Min | Max |
|--------|-----|-----|-----|
| hit | 1.00 | 1.00 | 1.00 |
| mrr | 0.90 | 0.50 | 1.00 |
| ndcg@5 | 0.85 | 0.63 | 1.00 |
| recall@5 | 1.00 | 1.00 | 1.00 |
| word_overlap | 0.90 | 0.85 | 0.92 |
| **avg** | **0.1691** | | |

### chunk=512/64 top_k=5

| # | Question | Answer (retrieved) | Sources | hit | mrr | ndcg@5 | recall@5 | word_overlap |
|---|----------|--------------------|---------|-----|-----|--------|----------|--------------|
| 1 | Embedding engine | The embedding engine supports GPU, API, and CPU backends with automatic fallback. Models are loaded lazily on first query. | architecture.md | 1.00 | 1.00 | 1.00 | 1.00 | 0.92 |
| 2 | Vector storage | The vec0 virtual table stores float arrays for cosine distance. Single-file portable storage via sqlite-vec. | architecture.md, store.py | 1.00 | 0.50 | 0.63 | 1.00 | 0.85 |

**Aggregate scores:**

| Metric | Avg | Min | Max |
|--------|-----|-----|-----|
| hit | 1.00 | 1.00 | 1.00 |
| mrr | 0.75 | 0.50 | 1.00 |
| ndcg@5 | 0.82 | 0.63 | 1.00 |
| recall@5 | 1.00 | 1.00 | 1.00 |
| word_overlap | 0.89 | 0.85 | 0.92 |
| **avg** | **0.1677** | | |

---

## 3. nomic-ai/nomic-embed-text-v2-moe

### chunk=2048/128 top_k=5 ★

| # | Question | Answer (retrieved) | Sources | hit | mrr | ndcg@5 | recall@5 | word_overlap |
|---|----------|--------------------|---------|-----|-----|--------|----------|--------------|
| 1 | Embedding engine | The embedding engine supports GPU, API, and CPU backends with automatic fallback. Models are loaded lazily on first query. The fallback chain is GPU then API then CPU. | architecture.md | 1.00 | 1.00 | 1.00 | 1.00 | 0.95 |
| 2 | Vector storage | SQLite with sqlite-vec provides single-file portable vector storage. The vec0 virtual table stores float arrays for cosine distance search. No server, no network dependency. | architecture.md | 1.00 | 1.00 | 1.00 | 1.00 | 0.97 |

**Aggregate scores:** ★ Best config

| Metric | Avg | Min | Max |
|--------|-----|-----|-----|
| hit | 1.00 | 1.00 | 1.00 |
| mrr | 1.00 | 1.00 | 1.00 |
| ndcg@5 | 1.00 | 1.00 | 1.00 |
| recall@5 | 1.00 | 1.00 | 1.00 |
| word_overlap | 0.96 | 0.95 | 0.97 |
| **avg** | **0.2147** | | |

---

## Appendix: Scoring methodology

### Relevance

A retrieved chunk is considered **relevant** if
its word overlap with the ground truth exceeds
the threshold:

    word_overlap(ground_truth, chunk) ≥ 0.3

Word overlap = |words(GT) ∩ words(chunk)| /
|words(GT)|

### Metrics

| Metric | Definition |
|--------|-----------|
| **hit** | 1.0 if at least one retrieved chunk is relevant, else 0.0 |
| **mrr** | 1/(rank of first relevant chunk). 1.0 = first result, 0.5 = second, 0.33 = third |
| **ndcg@5** | Normalized Discounted Cumulative Gain at k=5. Measures ranking quality: relevant chunks ranked higher score better. Perfect ranking = 1.0 |
| **recall@5** | (relevant chunks in top-5) / (total relevant chunks). 1.0 = all relevant chunks found |
| **word_overlap** | Best word overlap across all retrieved chunks (see Relevance above) |
| **avg** | Arithmetic mean of all metrics for the config |
```

## MVP

1. Questions chapter with full content
2. One chapter per model, one section per config
   with full Q&A table and aggregate scores
3. Best config marked with ★
4. Appendix with metric definitions

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
