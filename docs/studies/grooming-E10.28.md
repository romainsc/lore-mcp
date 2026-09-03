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

1. Markdown report with full Q&A per model/config
2. Scoring methodology appendix
3. Report path printed in summary
4. Tests TDD
5. Documentation updated

## MVP

1. Questions chapter with full content
2. One chapter per model, one section per config
3. Appendix

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
