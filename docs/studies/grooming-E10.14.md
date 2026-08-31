# Grooming E10.14 — Wire BuildConfig into CLI

- **Status:** Grooming — en attente de validation
- **Date:** 2026-08-31

## Context

BuildConfig (E10.13) exists but is not wired into
the CLI. The `--config` flag is missing from
`lore-mcp build` and `optimize`. Users must use
`--models` + env vars instead of a unified file.

## DoD

1. `--config build-config.yaml` flag on `build`
   and `optimize` subcommands
2. BuildConfig overrides `--models`, env vars
   for judge, and CLI optimize params
3. CLI flags still override config file values
4. Tests TDD
5. Documentation updated

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
