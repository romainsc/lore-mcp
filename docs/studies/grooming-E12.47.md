# Grooming E12.47 — Minimal function signatures

- **Status:** Prêt
- **Date:** 2026-09-22

## Problem

`preprocess_sources` has 18 parameters,
`run_build` has 22 parameters. Now that both
resolve params from `LoreConfig`, the individual
parameters are redundant.

## Solution

Reduce to structural minimum. All pipeline
parameters move into `LoreConfig`.

### Target signatures

```python
def preprocess_sources(
    manifest_path: str,
    docs_base_dir: str,
    config: LoreConfig,
) -> list[dict]:

def run_build(
    manifest_path: str,
    docs_dir: str,
    output_dir: str,
    config: LoreConfig,
) -> dict:
```

### Parameters moving to LoreConfig

From `preprocess_sources`:
- `orig_dir` → `config.preprocess_orig_dir`
- `prep_dir` → `config.preprocess_prep_dir`
- `manifest_out` → `config.preprocess_manifest_out`
- `force` → `config.force`
- `output_level` → `config.output_level`
- `keep_intermediates` → `config.keep_intermediates`
- `enrich` → already `config.enrich_techniques`
- `llm_entry` → already resolved from config
- `caption_*` → already resolved from config
- `ocr_*` → already in config
- `judge_entry` → already resolved from config

From `run_build`:
- `skip_optimize` → `config.skip_optimize`
- `preprocess` → `config.preprocess`
- `force` → `config.force`
- `output_level` → `config.output_level`
- `embedder/embedders` → resolved from config
- `chunk_sizes`, etc. → already in config
- `judge_*` → already resolved from config
- `report_path` → `config.report_path`

### New LoreConfig fields

```python
# Runtime flags (set by CLI, not config.yaml)
force: bool = False
output_level: str = "default"
keep_intermediates: bool = False
skip_optimize: bool = False
preprocess: bool = False
preprocess_orig_dir: str = "."
preprocess_prep_dir: str = "prep"
preprocess_manifest_out: str = ""
report_path: str = ""
```

### Migration

1. Add runtime fields to `LoreConfig`
2. CLI sets them on config before passing
3. Simplify `preprocess_sources` signature
4. Simplify `run_build` signature
5. Migrate tests to use `LoreConfig` fixture
6. Remove `_run_preprocess` plumbing in server.py

## DoD

1. `preprocess_sources`: 3 params
2. `run_build`: 4 params
3. All tests pass with LoreConfig fixture
4. server.py CLI handlers simplified

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
