# Grooming E12.08 — Transversal LLM capability

- **Status:** Implémenté (study)
- **Date:** 2026-09-09

## Problem

Several preprocessing steps benefit from LLM:
parse tier 3 (complex docs), contextual retrieval,
Q&A mode, proposition indexing, metadata enrichment.
No shared LLM client exists in the preprocessing
module.

## Recommendation

### LLM client

Use `LORE_LLM_URL` (already configured for RAGAS
judge) or Claude API via `anthropic` SDK. The
client is shared across all LLM-consuming steps.

### Techniques by ROI (E14.17)

| Technique | Impact | Cost | Priority |
|-----------|--------|------|----------|
| Contextual retrieval | −49% failures | ~$1/M tokens | High |
| Q&A mode | Improved query match | ~$0.5/M tokens | High |
| Proposition indexing | +22.5% retrieval | ~$2/M tokens | Medium |
| Metadata enrichment | +9.2-14.8pts | ~$0.5/M tokens | Medium |
| Parse tier 3 | Complex doc rescue | Variable | Low (rare) |

### Complex document definition

A document is "complex" when standard parsers
produce poor output. Detection criteria:
1. Lint score on parser output = `poor`
2. Text density < 0.3 after conversion
3. Image-to-text ratio > 50%

These documents should be flagged for LLM-assisted
conversion (E12.09 `--enrich` flag).

### Implementation approach (E12.09)

```bash
lore-mcp preprocess manifest.yaml \
  --docs-base-dir /corpus/ \
  --orig-subdir orig --prep-subdir prep \
  --enrich context,qa
```

Config YAML:
```yaml
preprocess:
  enrich: [context, qa]
  llm_url: http://localhost:11434/v1
  llm_model: granite-8b-instruct
```

Or via Claude API (requires `anthropic` package).

### Dependencies

- `LORE_LLM_URL` + `LORE_LLM_MODEL` (existing
  config for RAGAS judge)
- Or `anthropic` SDK (optional dep)
- E12.09 implements the actual enrichment

## DoD

1. Study artifact with technique ranking,
   complex doc criteria, implementation approach
2. E12.09 can use this as spec

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
