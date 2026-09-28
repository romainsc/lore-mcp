# Grooming E12.91 + E12.92 + E12.93

## E12.91 — Add lang to sources table

Column `lang TEXT` in `CREATE TABLE sources`.
Populated from manifest/recipe at ingestion.
Migration: ALTER TABLE for existing .db.

## E12.92 — Rename orig → file, remove path

Direct replacement, no backward compat (pre-release).
`file` = what to process (in orig_dir).
`path` removed (derived: stem(file) + .md in build_dir/prep/).

## E12.93 — Rename manifest → recipe

### File structure

```yaml
collection: my-corpus
level: libre

defaults:
  lang: fra
  license: CC-BY-SA-4.0
  options:
    chunk_size: 1024
    chunk_overlap: 128
    enrich: [context, qa, meta]
    caption_models: [granite-vision]

sources:
  - title: "Document technique"
    file: doc1.pdf
  - title: "Slides"
    file: slides.pptx
    lang: eng
    options:
      chunk_size: 512
      enrich: [context]
```

### Cascade (3 levels)

```
source.options.X  →  defaults.options.X  →  config.yaml.X  →  hardcoded default
source.lang       →  defaults.lang       →  auto-detect
```

### Renames

| Before | After |
|---|---|
| manifest.py | recipe.py |
| parse_manifest() | parse_recipe() |
| manifest_path | recipe_path |
| manifest.yaml | recipe.yaml |
| CLI `manifest` arg | CLI `recipe` arg |
| manifest-test-redist.yaml | recipe-test-redist.yaml |
| --manifest-out | --recipe-out |

### config.yaml changes

config.yaml keeps pipeline defaults (unchanged).
recipe.defaults.options overrides per-collection.
source.options overrides per-source.
