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

## Pre-flight validation

Before any work, validate all models:

1. **API models**: probe the endpoint (existing
   `_probe_api`). Fail fast if unreachable.
2. **Local models**: check if already in HuggingFace
   cache (`~/.cache/huggingface/hub/models--<name>`).
   If not cached, report the estimated download
   size and require `--allow-download` flag.
3. **All models**: verify that `model_dim` can be
   determined (API probe or cached config.json).

If any model fails validation, report all
failures at once and exit — don't fail one by one.

## Resumability

The build/optimize pipeline can be interrupted
and resumed. State is persisted in the working
directory:

1. **Optimization state**: each tested config
   produces `opt-<model>-<size>-<overlap>.db` in
   `--db-dir`. On resume, configs with existing
   `.db` files are skipped.
2. **Questions**: generated questions are saved
   to `questions.json` in `--db-dir`. On resume,
   questions are loaded from this file instead of
   regenerated.
3. **Scores**: per-config scores appended to
   `scores.jsonl` in `--db-dir`. On resume,
   existing scores are loaded and only missing
   configs are evaluated.
4. **Final .db**: if the final `.db` already
   exists in `--output-dir`, skip re-indexing
   unless `--force`.

The `--resume` flag (default) loads existing
state. `--force` ignores existing state and
starts fresh.

## DoD

1. `lore-mcp build` CLI subcommand
2. Full pipeline: validate → optimize → index →
   metadata
3. Single command produces ready-to-distribute
   .db + metadata files
4. --skip-optimize for fast builds
5. Pre-flight model validation (probe endpoints,
   check cache, report download sizes)
6. Resumable pipeline (skip completed configs)
7. Build report includes winning config + all
   scores
8. Tests TDD
9. Documentation (architecture.md, configuration.md,
   code-guide.md, README.md)
10. EPUBs regenerated

## Dependencies

- E6.05 manifest + metadata (done)
- E10.09 multi-model optimize (done)
- E10.06/07 deterministic .db naming (done)

## MVPs

- **MVP1**: `lore-mcp build --skip-optimize`
  (validate + index + metadata, no optimization)
- **MVP2**: `lore-mcp build` with optimization
  (full pipeline, not resumable)
- **MVP3**: resumability (skip completed configs,
  persist questions/scores)

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
