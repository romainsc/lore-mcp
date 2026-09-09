# Grooming E12.18 — CLI `lore-mcp enrich` standalone

- **Status:** En attente validation
- **Date:** 2026-09-09

## Problem

LLM enrichment is only available as `--enrich`
option on preprocess. Users who already have
clean markdown want to enrich without re-running
parse+clean.

## Solution

Add `lore-mcp enrich` subcommand in `server.py`.
Reads manifest-prep, applies enrichment to files
in `--docs-dir`, writes enriched files in place
or to `--output-dir`.

```bash
lore-mcp enrich manifest-prep.yaml \
  --docs-dir /corpus/prep/ \
  --enrich context,qa \
  --llm-url $LORE_LLM_URL \
  --llm-model granite-3-2-8b-instruct
```

### Code reuse

`enrich.py:enrich_context()` and `enrich_qa()`
already exist. The new command is CLI routing
only — no new logic.

## DoD

1. `lore-mcp enrich` subcommand in server.py
2. Reads manifest, enriches each source file
3. `--enrich` on preprocess still works (shortcut)
4. Test: standalone enrich produces same result

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
