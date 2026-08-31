# Grooming E10.10 — Rename mode `auto` → `local`

- **Status:** Grooming — en attente de validation
- **Date:** 2026-08-31

## Context

`LORE_EMBED_MODE=auto` is misleading — it suggests
automatic selection across all backends. In reality
it loads the model in-process via sentence-transformers
and picks GPU or CPU based on hardware. The name
should reflect the mechanism, not imply intelligence.

## Change

Rename `auto` to `local` everywhere:

- `embedder.py`: default mode, `_select_device_dtype`,
  `assess()`, all conditionals
- `server.py`: `_get_embedder` default, `search_docs`
  backend display
- `CLAUDE.md`: env var table
- `docs/configuration.md`: LORE_EMBED_MODE doc
- `docs/architecture.md`: fallback chain description
- `README.md`: env var table
- Tests: all references to `mode="auto"`

No backward compatibility — `auto` is removed.
Still in dev (v0.1.0-dev), no external users.

Valid modes after change: `local` (default),
`gpu`, `cpu`, `api`.

## DoD

1. All `auto` references replaced by `local`
2. `Embedder(mode="auto")` raises ValueError
3. Tests updated
4. Documentation updated

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
