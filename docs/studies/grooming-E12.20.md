# Grooming E12.20 — Auto-manifest and full-auto mode

- **Status:** Prêt
- **Date:** 2026-09-10

## Problem

The user must write a manifest before using
lore-mcp. The primary use case is simpler:
"I have a directory of files, lore-mcp does
everything."

## Solution

Make manifest optional. If absent, lore-mcp
scans the directory, generates a manifest,
preprocesses, and indexes.

### CLI

```bash
# Full auto — no manifest
lore-mcp build \
  --docs-dir /my/files/ \
  --output-dir /db/ \
  --config config.yaml

# With manifest — existing behavior
lore-mcp build manifest.yaml \
  --docs-dir /corpus/ \
  --output-dir /db/ \
  --config config.yaml
```

### Scan logic

When no manifest argument:
1. Scan `--docs-dir` for supported extensions
   (.md, .html, .pdf, .docx, .pptx, .xlsx,
   .epub, .csv, .json, .xml)
2. For each file: resolve fields (orig = filename,
   path = basename.md, title = extracted)
3. Generate manifest YAML in `--output-dir`
4. Proceed with preprocess → build

### Generated manifest

```yaml
# generated-manifest.yaml (written to output-dir)
collection: my-files
level: libre
sources:
  - title: Architecture Guide
    license: Apache-2.0
    orig: architecture.pdf
    path: architecture.md
  - title: Tutorial
    orig: tutorial.html
    path: tutorial.md
```

Metadata (title, author, license) extracted from
front matter or document content after conversion.

### All modes remain valid

| Mode | Manifest | Behavior |
|------|----------|----------|
| Full auto | Absent | Scan + generate + preprocess + build |
| Manual manifest | Provided | Use manifest, preprocess + build |
| External preprocess | Provided + clean files | Build only |
| Preprocess only | Provided | Preprocess, no build |

### Implementation

- `server.py:main()`: manifest argument becomes
  optional on build
- New function `scan_directory()` in
  `preprocess/__init__.py` or `manifest.py`:
  list files, resolve fields, write manifest YAML
- `run_build()`: if no manifest, call scan first

## DoD

1. `build` without manifest scans and generates
2. Generated manifest contains extracted metadata
3. All existing modes unchanged
4. Test: build from raw directory without manifest

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
