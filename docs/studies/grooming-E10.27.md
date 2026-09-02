# Grooming E10.27 — Heading-based evaluation

- **Status:** Validé
- **Date:** 2026-09-02

## Problem

The current extractive question generator
(`_generate_extractive`) extracts sentences from
indexed chunks. This creates two biases:

1. **Chunking bias**: ground truth is tied to the
   first chunking config — different configs split
   text differently, penalizing alternatives.
2. **Trivial retrieval**: the ground truth sentence
   exists verbatim in a chunk, so hit=1.0 almost
   always. No real discrimination.

## Solution

Generate QA pairs from the **source documents**
before any chunking, using document structure
(markdown headings).

### Approach: heading → section

For each markdown heading (`## Title`), create:
- **Query**: the heading text (e.g. "Scalability &
  Performance")
- **Ground truth**: the section content (text
  between this heading and the next)
- **Source file**: the document file

This is the **Inverse Cloze Task (ICT)** variant
used by BEIR-style benchmarks.

### Metrics

Replace current metrics with standard IR metrics:
- **NDCG@k**: primary (position-weighted relevance)
- **Recall@k**: secondary (coverage)
- Keep **MRR** for backward comparison

A retrieved chunk is "relevant" if it comes from
the same source file AND has word overlap > 0.3
with the section content (fuzzy matching).

### Implementation

1. `generate_questions_from_sources(docs_dir)` —
   parse markdown files, extract heading/section
   pairs, return QA list
2. `generate_questions_from_db` falls back to
   extractive only if `docs_dir` not available
3. `run_optimize` passes `docs_dir` to question
   generation (already available)
4. Add `ndcg_at_k()` and `recall_at_k()` to
   eval.py metrics
5. Update ProgressReporter tables for new metrics

### No dependency added

All metrics computed manually (no ir_measures
dependency). NDCG formula is ~10 lines.

## DoD

1. Questions generated from source doc headings
2. Ground truth = section content (pre-chunking)
3. NDCG@k + Recall@k computed and displayed
4. MRR kept for comparison
5. Extractive fallback when docs_dir unavailable
6. Tests TDD
7. Works with `--verbose` tables

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
