# Design — Config & LLM registry

- **Status:** Référence
- **Date:** 2026-09-18
- **Module:** `config.py`

## Config architecture

Single `config.yaml` replaces all LORE_* env vars.
No env var fallback. Manifest = sources (portable).
Config = pipeline settings (local, not committed).

```yaml
database:
  path: ./lore.db
  dir: ""                    # multi-collection

embedding:
  model: nomic-ai/nomic-embed-text-v2-moe
  mode: builtin              # builtin/builtin:gpu/cpu/api
  api_url: ""
  batch_size: 64

chunking:
  chunk_size: 1024
  chunk_overlap: 128

llm:                         # LLM registry (list)
  - name: granite-8b
    model: granite-3-2-8b-instruct
    api_url: https://...
    api_key: ...
    start: ./scripts/start.sh    # IS lifecycle
    stop: podman stop ...
    start_timeout: 300

enrich:
  techniques: [context, qa, meta]
  models: [granite-8b]       # references llm registry

parse:
  caption_models: [granite-docling, granite-vision]
  caption_selection: judge
  caption_judge: granite-8b

judge:
  models: [granite-8b]

reranking:
  model: ibm-granite/granite-embedding-reranker-english-r2

optimize:
  chunk_sizes: [512, 1024, 2048]
  chunk_overlaps: [64, 128]
  top_ks: [3, 5, 10]
  num_questions: 50
  embedding:                 # multi-model optimize
    - model: nomic-v2-moe
      mode: api
      api_url: http://...:8082
```

## LLM registry pattern

`llm:` is a list of model entries. Each entry:
- `name` (required) — unique identifier
- `model` — HuggingFace model ID or API model name
- `api_url` — OpenAI-compatible endpoint
- `api_key` — API authentication
- `start` / `stop` — IS lifecycle commands (E12.25)
- `start_timeout` — health check timeout (default 300s)
- `verify_ssl` — SSL verification (default true)

Other sections reference models by name:
- `enrich.models: [granite-8b]`
- `judge.models: [granite-8b]`
- `parse.caption_models: [granite-docling, granite-vision]`
- `parse.caption_judge: granite-8b`

`LoreConfig.get_llm(name)` looks up by name,
raises KeyError if not found.

## Backward compatibility

- `llm:` as dict (old format) → converted to
  single-item registry with name "default"
- `parse.models` (old field) → still read,
  used if `caption_models` absent

## Convenience properties

For legacy code that reads first LLM:
- `cfg.llm_model` → first registry entry's model
- `cfg.llm_api_url` → first registry entry's url
- `cfg.llm_api_key` → first registry entry's key
- `cfg.llm_verify_ssl` → first entry's verify_ssl

## `LoreConfig.from_file(path)`

Reads YAML, maps sections to dataclass fields.
Validates `embedding:` key (rejects old `models:`).
Returns populated `LoreConfig`.

## Cross-references

- `docs/configuration.md` — user-facing reference
- `docs/studies/grooming-E10.30.md` — unified config
- `docs/studies/grooming-E10.32.md` — LLM registry
- `docs/studies/design-captioning-pipeline.md` — captioning config
- `docs/studies/design-build-pipeline.md` — build config

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
