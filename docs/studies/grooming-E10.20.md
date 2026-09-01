# Grooming E10.20 — Observability

- **Status:** Validé
- **Date:** 2026-09-01

## Context

Current logs show `avg=0.xxxx` without context.
No progression, no identification of which
collection/model/config is running, no timing.
On a 36-config optimize with 6 collections,
the output is a wall of unlabeled numbers.

## Structured log format

Default (summary):
```
[ia-libre] [nomic-v2] [12/36] chunk=1024/128 top_k=5: avg=0.8234 (2.3s)
[ia-libre] complete: 36 configs, best=chunk=1024/64 top_k=5 avg=0.8456 (42s)
[3/6 collections] [18/36 configs] elapsed: 1m42s
```

Verbose (`--verbose`):
```
[ia-libre] [nomic-v2] [12/36] chunk=1024/128 top_k=5
  hit=0.80 word_overlap=0.72 mrr=0.65 score_spread=0.43
  sources: intro.md(3), config.md(2)
  avg=0.8234 (2.3s)
```

## Implementation

- Progress tracker class with collection/model/
  config counters and timing
- Injected into run_optimize, run_build, run_eval
- `--verbose` flag on all CLI subcommands
- Summary at end of each collection and overall

## DoD

1. Structured logs with context in optimize/build
2. Progression counters
3. Timing per config and total
4. `--verbose` flag for detailed per-question output
5. Summary at end of each collection
6. Tests TDD
7. Documentation updated

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
