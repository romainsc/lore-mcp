# Grooming E12.62 — Directory-as-collection

- **Status:** Prêt
- **Date:** 2026-09-23

## Problem

Indexing a project's docs requires writing a
manifest listing every file. Tedious for large
projects. Want to clone a repo and build a .db.

## Use case

```bash
git clone https://github.com/romainsc/lore-mcp
lore-mcp build --docs-dir lore-mcp/ \
  --output-dir out/ --preprocess --config config.yaml
```

Index all of lore-mcp (code, docs, tests, config)
as a searchable RAG corpus.

## Solution

Manifest is optional. Without manifest, scan
directory recursively. With partial manifest,
merge: manifest entries take priority, scanned
files fill the gaps.

### Resolution cascade

1. File in manifest → use manifest metadata
2. File in directory, not in manifest → auto
   (title from front matter/heading, lang via
   langdetect)
3. File in manifest, not in directory → error
   or fetch if URL + --allow-download

### Recursive scan

All supported formats in the directory tree.
Respects E12.61 (preserve tree structure).
detect_format via mimetypes (E12.50).

### Auto-metadata

For scanned files without manifest entry:
- title: front matter > first heading > filename
- lang: langdetect on first 1000 chars
- license: front matter if present
- author: front matter if present

### CLI

```bash
# Clone and index
lore-mcp build --docs-dir /path/to/repo/ \
  --output-dir out/ --preprocess \
  --allow-download --config config.yaml

# With partial manifest (overrides)
lore-mcp build partial.yaml \
  --docs-dir /path/to/repo/ \
  --output-dir out/ --preprocess \
  --config config.yaml
```

## DoD

1. build --docs-dir without manifest works
2. Recursive scan of all supported formats
3. Partial manifest merges with scan
4. Auto-metadata extraction
5. Preserves directory tree (E12.61)
6. Validated: index lore-mcp's own repo
7. Tests

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
