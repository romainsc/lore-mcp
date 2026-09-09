# Grooming E12.18 — CLI `lore-mcp enrich` standalone

- **Status:** Validé
- **Date:** 2026-09-09

## Problem

LLM enrichment is only available as `--enrich`
option on preprocess. Users who already have
clean markdown want to enrich without re-running
parse+clean.

## Principles

- **Input files are never modified** — enrich
  writes to `--output-dir`, never in-place
- `--enrich` on preprocess remains as shortcut

## Enrich options

| Option | What | Impact (Anthropic, E14.17) |
|--------|------|--------------------------|
| `context` | LLM adds context paragraph per section | −35% retrieval failures (alone) |
| `qa` | LLM generates 2-3 questions per section | Improved query↔chunk matching |
| `props` | LLM decomposes into atomic propositions (E12.13) | +22.5% retrieval |
| `meta` | LLM generates summaries + keywords (E12.14) | +9.2-14.8pts RAG |

Combined impacts (E14.17 Anthropic):
- context alone: −35%
- context + hybrid BM25 (E5.03): −49%
- context + hybrid BM25 + reranking (E5.06): −67%

## CLI

```bash
# Standalone
lore-mcp enrich manifest-prep.yaml \
  --docs-dir /corpus/prep/ \
  --output-dir /corpus/enriched/ \
  --enrich context,qa \
  --llm-url $LORE_LLM_URL \
  --llm-model granite-3-2-8b-instruct

# Shortcut via preprocess
lore-mcp preprocess manifest.yaml \
  --docs-base-dir /corpus/ \
  --orig-subdir orig --prep-subdir enriched \
  --enrich context,qa
```

## Code

`enrich_context()` and `enrich_qa()` already
exist in `enrich.py`. The new command is CLI
routing only — no new logic.

## DoD

1. `lore-mcp enrich` subcommand in server.py
2. `--output-dir` required, input never modified
3. `--enrich` on preprocess still works
4. Test: standalone enrich produces same result

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
