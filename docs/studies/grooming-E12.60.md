# Grooming E12.60 — Purge all legacy env var references

- **Status:** Prêt
- **Date:** 2026-09-23

## Problem

15 references to LORE_* env vars remain in code.
Error messages reference env vars instead of
config.yaml. No legacy to maintain — pre-release.

## Scope

- build_config.py: os.environ.get fallbacks
- eval.py: LORE_LLM_URL, LORE_LLM_MODEL
- enrich.py: error message mentions LORE_LLM_URL
- server.py: CLI help texts mention LORE_*
- configuration.md: "Legacy environment variables"

## DoD

1. 0 LORE_* in code (except TESSDATA_PREFIX)
2. 0 os.environ.get / os.getenv
3. Error messages reference config.yaml
4. Docs updated
5. Tests pass, CI green

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
