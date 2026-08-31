# Grooming E11.01 — `lore-mcp build`

- **Status:** Grooming — en attente de validation
- **Date:** 2026-08-31
- **Epic:** E11. Build workflow

## Context

Today the user must chain 4 manual steps to
produce an optimized .db: optimize parameters,
read the report, re-index with the winning
config, generate metadata files. The desired UX
is a single command that takes a manifest + model
configs and produces the final .db with its
metadata.

## Input files

### manifest.yaml (existing format, E6.05)

```yaml
collection: ia-libre
level: libre
sources:
  - path: intro.md
    title: "Introduction to AI Serving"
    author: "Romain Chantereau"
    license: "CC-BY-SA-4.0"
  - path: config.md
    title: "Configuration Guide"
```

### models.yaml (existing format, E10.09)

```yaml
models:
  - name: BAAI/bge-m3
    mode: auto
  - name: nomic-embed-text-v1.5
    mode: api
    api_url: https://vllm-nomic/v1/embeddings
```

## Output

In `--output-dir`:
- `<collection>.db` — optimized index
- `<collection>.json` — machine-readable metadata
- `<collection>.bib` — BibTeX bibliography
- `<collection>.md` — human-readable description
- `build-report.json` — optimization report (all
  combinations tested, winning config, scores)

## CLI

```bash
lore-mcp build manifest.yaml \
  --models models.yaml \
  --docs-dir /path/to/sources/ \
  --output-dir /path/to/output/ \
  --num-questions 50
```

Optional flags:
- `--skip-optimize` — use defaults or env vars,
  don't run optimization
- `--chunk-size` / `--chunk-overlap` — override
  instead of optimizing
- `--metrics score_spread,mrr` — select metrics

## Pipeline

```
manifest.yaml + models.yaml
        ↓
1. Parse manifest (sources, biblio)
2. Parse model configs (endpoints)
3. Optimize (if not --skip-optimize):
   - For each (model × chunk × overlap × top_k):
     index, score, compare
   - Select winning combination
4. Final index with winning config:
   - ingest_with_manifest (preserves biblio)
   - Winning model + chunk params
5. Generate metadata:
   - .json, .bib, .md from the final .db
6. Write build-report.json
```

## DoD

1. `lore-mcp build` CLI subcommand
2. Full pipeline: optimize → index → metadata
3. Single command produces ready-to-distribute
   .db + metadata files
4. --skip-optimize for fast builds
5. Build report includes winning config + all
   scores
6. Tests TDD
7. Documentation (architecture.md, configuration.md,
   code-guide.md, README.md)
8. EPUBs regenerated

## Dependencies

- E6.05 manifest + metadata (done)
- E10.09 multi-model optimize (done)
- E10.06/07 deterministic .db naming (done)

## MVPs

- **MVP1**: `lore-mcp build` with --skip-optimize
  (index + metadata only, no optimization)
- **MVP2**: `lore-mcp build` with optimization
  (full pipeline)

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
