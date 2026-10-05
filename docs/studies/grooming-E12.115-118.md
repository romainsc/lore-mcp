# Grooming E12.115-118 — 4 bugs from validation

## E12.115 — add_source does not support directories

add_source(file=".") treats "." as a file path.

Fix: in add_source, detect if file_path.is_dir().
If so, scan_directory → generate entries →
process each file. Return summary.

DoD: add_source(file="src/") indexes all
supported files. Test. CI green.

## E12.116 — FormatRegistry missing config formats

.yml, .yaml, .toml, Containerfile not in
FormatRegistry defaults.

Fix: add to FormatRegistry._load_defaults():
- .yml, .yaml → "code" (narration structurée
  par clé top-level)
- .toml → "code" (narration par [section])
- Dockerfile, Containerfile → "code" (narration
  par stage FROM)
- .cfg, .ini → "code" (narration par [section])

Backend "code" with dedicated narration for each
format in narrate.py:
- _narrate_yaml(): parse YAML, h2 per top-level
  key, h3 sub-sections, values as list items
- _narrate_toml(): parse TOML, h2 per [section],
  h3 per sub-table
- _narrate_dockerfile(): split on FROM, h2 per
  stage with base image and stage name

Validated by experiments: approach C (structured
narration) produces 3-9 headings, structure 0.9-1.0
vs approach A (passthrough) 0 headings structure 0.0.

DoD: scan_directory finds .yml/.yaml/.toml.
Narrated output has headings. Quality gate
structure > 0. Tests. CI green.

## E12.117 — CLI build --orig-dir scan empty

scan_directory finds files but build indexes 1.
Root cause: when no recipe, scan → recipe, but
the scan result may not be correctly passed to
the build pipeline.

Investigation needed in build.py / CLI path.

DoD: lore-mcp build --orig-dir . indexes all
supported files. Test. CI green.

## E12.118 — add_source enrich="" no-op

enrich="" is falsy → if enrich: block skipped →
config defaults apply.

Fix: treat "none" as explicit disable:
```python
if enrich == "none":
    prep_cfg.enrich_techniques = []
elif enrich:
    prep_cfg.enrich_techniques = enrich.split(",")
```

Same fix in add_sources and add_recipe.

DoD: add_source(enrich="none") produces no
enrichment. Test. CI green.
