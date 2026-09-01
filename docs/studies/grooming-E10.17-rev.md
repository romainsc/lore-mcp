# Grooming E10.17 rev — Smart batch size management

- **Status:** Validé
- **Date:** 2026-09-01

## Changes from original E10.17

Original: just LORE_BATCH_SIZE env var.
Revised: per-model batch_size in config + smart
reduction + memoization.

## DoD

1. `batch_size` optional in embedding config YAML
2. Default: LORE_BATCH_SIZE env var or 64
3. On 422: binary search between 1 and failed
   size to find max accepted
4. Memoize discovered max on the Embedder for
   all subsequent calls
5. Tests TDD
6. Documentation

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
