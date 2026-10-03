# Grooming E3.40 — MCP tool: get_config

## Context

No MCP tool currently exposes lore-mcp's active
configuration. An LLM using the server has no
way to know: which embedding model is active,
what chunk params are configured, where the
data directory is, what enrichment techniques
are enabled, etc.

Research (2026-10-03) confirms:
- No MCP standard for config exposition
- Community pattern: `get_config` tool returning
  structured YAML (docmd pattern)
- YAML is the most LLM-readable format for
  hierarchical config (consensus)
- JSON acceptable, natural text discouraged

## Design

### New MCP tool: `get_config`

```python
@mcp.tool()
def get_config() -> str:
    """Return active configuration in YAML format.

    Shows: embedding model, chunk params, data
    directory, search defaults, enrichment
    settings, registered models. API keys are
    masked.
    """
```

### Output format: YAML with section comments

```yaml
# Active lore-mcp configuration
database:
  dir: /home/user/.local/share/lore-mcp
  default_collection: default

embedding:
  model: nomic-ai/nomic-embed-text-v2-moe
  mode: builtin:gpu
  batch_size: 32

chunking:
  chunk_size: 1024
  chunk_overlap: 128

search:
  top_k: 5
  hybrid: true
  reranking_model: ""
  mmr_lambda: 0.5
  window_size: 0
  per_source_cap: 0

llm:
  - name: tei
    model: nomic-ai/nomic-embed-text-v2-moe
    api_url: http://localhost:8081/v1/embeddings
    api_key: "***"  # masked
  - name: ollama
    model: granite3.3:8b
    api_url: http://localhost:11434/v1/chat/completions

enrich:
  techniques: [context, meta]

parse:
  ocr_engine: tesseract
  ocr_lang: [fra]
```

### Secrets masking

Any field matching `*key*`, `*token*`,
`*password*`, `*secret*` → `"***"`.

### Implementation

1. Read `LoreConfig` via `_get_config()`
   (already available in server.py)
2. Build a dict from config attributes
3. Mask secrets
4. `yaml.dump()` with `default_flow_style=False`
5. Return as string

### What to expose

| Section | Source | Fields |
|---------|--------|--------|
| database | `config.data_dir`, `config.default_collection` | dir, default_collection |
| embedding | `config.embedding_model`, `config.embedding_mode` | model, mode, batch_size |
| chunking | `config.chunk_size`, `config.chunk_overlap` | chunk_size, chunk_overlap |
| search | `config.top_k`, etc. | top_k, hybrid, reranking_model, mmr_lambda, window_size, per_source_cap |
| llm | `config.llm_registry` | name, model, api_url, api_key (masked) |
| enrich | `config.enrich_techniques` | techniques |
| parse | `config.ocr_engine`, `config.ocr_lang` | ocr_engine, ocr_lang |

### What NOT to expose

- Internal paths (_config_path, intermediates_dir)
- Runtime state (embedder instance, db cache)
- Force flags, output_level (ephemeral CLI args)

## DoD

- `get_config` MCP tool returns YAML string
- All secrets masked
- Test: call get_config, verify YAML parseable,
  verify secrets masked
- Tool description explains what each section is
- CI green

## MVP

Single MVP — the tool is small.

## Dependencies

None (LoreConfig already exists).

## Risks

Low. Read-only tool, no side effects.
