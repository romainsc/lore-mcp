# Grooming E10.17 — Configurable batch size

- **Status:** Validé
- **Date:** 2026-09-01

## DoD

1. `LORE_BATCH_SIZE` env var (default 64)
2. `ingest.py`: read from env, replace hardcoded
3. Tests TDD
4. Documentation updated

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
