# Grooming E10.19 — RAGAS guard (bidirectional)

- **Status:** Validé
- **Date:** 2026-09-01

## Context

Two misconfigurations are possible:
1. Judge LLM configured but no RAGAS metrics
   requested → judge is loaded/paid for but never
   used. User doesn't realize.
2. RAGAS metrics requested but no judge → already
   handled by E10.15 (fail fast).

E10.19 adds the missing direction: warn when the
judge is configured but won't be used.

## Behavior

| Config | Metrics requested | Result |
|--------|-------------------|--------|
| No judge | No RAGAS metrics | OK — default metrics |
| No judge | RAGAS metrics | **Error** (E10.15, existing) |
| Judge configured | RAGAS metrics | OK — use RAGAS |
| Judge configured | No RAGAS metrics | **Warning**: "Judge LLM configured but no RAGAS metrics requested. The judge will not be used. Add RAGAS metrics (faithfulness, context_recall, answer_correctness) to the metrics list to use the judge." |

## Implementation

Update `validate_metrics_prerequisites()` in
`eval.py`:
- Current: checks RAGAS metrics → requires judge
- Add: checks judge config → warns if no RAGAS
  metrics requested

Call the validation in `run_eval`, `run_optimize`,
and `run_build` (via BuildConfig).

## DoD

1. Warning log when judge configured without
   RAGAS metrics
2. Error preserved when RAGAS without judge
3. Validation called in eval/optimize/build
4. Tests TDD
5. Documentation updated

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
