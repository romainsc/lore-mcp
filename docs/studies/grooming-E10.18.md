# Grooming E10.18 — Embedding API resilience

- **Status:** Validé
- **Date:** 2026-09-01

## Principle

Never skip silently. Either succeed (with retry)
or fail explicitly.

## Error handling

| Error | Action | Max retries |
|-------|--------|-------------|
| 422 (batch too large) | Halve batch, retry | Until batch=1 |
| 429 (rate limit) | Wait Retry-After or exp backoff | 5 |
| 500 (server error) | Exp backoff | 3 |
| 503 (unavailable) | Exp backoff (longer) | 5 |
| Timeout | Exp backoff | 3 |
| Connection refused | Exp backoff | 3 |
| 401/403 (auth) | Fail fast, stop build | 0 |
| 404 (model not found) | Fail fast, stop build | 0 |
| File error (encoding) | Log warning + add to errors + continue | 0 |

Consecutive error threshold: if N files fail
consecutively after all retries (default N=3),
stop the build — likely systemic problem.

## MVPs

- MVP1: retry with backoff (429/500/503/timeout)
- MVP2: batch reduction on 422
- MVP3: fail fast + consecutive threshold

## DoD

1. Retry with backoff in `_embed_api`
2. Batch reduction on 422
3. Fail fast on 401/404
4. Consecutive error threshold
5. Explicit log at each retry
6. File errors in final report
7. Tests TDD
8. Documentation

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
