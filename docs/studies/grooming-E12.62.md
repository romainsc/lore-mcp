# Grooming E12.62 — Directory-as-collection

- **Status:** Prêt
- **Date:** 2026-09-23 (revised)

## Problem

Indexing a project's docs requires writing a
manifest listing every file. Tedious for large
projects. Want to clone a repo and build a .db.

## Use case

```bash
git clone https://github.com/romainsc/lore-mcp
lore-mcp build manifest.yaml --docs-dir lore-mcp/ \
  --output-dir out/ --preprocess --config config.yaml
```

## Solution

The manifest is the source of truth. Traversal
is manifest-driven, not filesystem-driven.

### Entry types in manifest

**File entry**: a specific file with metadata.

```yaml
- orig: README.md
  title: "lore-mcp README"
```

**Directory entry**: recursive scan of a subtree.
Metadata on the entry becomes defaults for all
files found inside.

```yaml
- orig: docs/
  license: CC-BY-SA-4.0
  lang: eng
```

### Resolution rules

1. **File entry** in manifest → use its declared
   metadata
2. **Directory entry** in manifest → scan
   recursively. For each file found:
   - If the file has its own entry in manifest
     → file entry takes priority
   - Otherwise → infer metadata from file,
     inherit directory entry as defaults
3. **File in orig-dir but not in any manifest
   entry (file or directory)** → ignored
4. **No manifest at all** → scan entire orig-dir
   (equivalent to a single directory entry for .)

### Example manifest

```yaml
collection: lore-mcp-docs
level: libre
sources:
  # Directory entry — entire subtree
  - orig: docs/
    license: CC-BY-SA-4.0
    lang: eng

  # File entry — overrides for a specific file
  - orig: docs/preprocessing.md
    title: "Guide de preprocessing RAG"
    lang: fra

  # Simple file entry
  - orig: README.md

  # Another directory
  - orig: src/
    license: AGPL-3.0-or-later
```

docs/preprocessing.md matches both directory and
file entries → file entry wins (title FR).
Other files in docs/ inherit CC-BY-SA-4.0 + eng.
Files in src/ inherit AGPL-3.0-or-later.
CONTRIBUTING.md at root is in no entry → ignored.

### Auto-metadata (for files without explicit entry)

- title: front matter > first heading > filename
- lang: langdetect on first 1000 chars
- license: front matter if present, else inherit
  from directory entry
- author: front matter if present

### CLI

```bash
# With manifest (directory entries)
lore-mcp build manifest.yaml \
  --docs-dir /path/to/repo/ \
  --output-dir out/ --preprocess \
  --config config.yaml

# Without manifest — scan everything
lore-mcp build --docs-dir /path/to/repo/ \
  --output-dir out/ --preprocess \
  --config config.yaml
```

## DoD

1. Directory entries in manifest scanned
   recursively
2. File entries override directory defaults
3. Files not in any manifest entry ignored
4. No manifest → scan all
5. Directory defaults inherited (lang, license)
6. Preserves directory tree (E12.61)
7. Validated: index lore-mcp's own repo
8. Tests

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
