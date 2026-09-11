---
title: Sample Markdown Document
author: lore-mcp project
license: AGPL-3.0-or-later
date: 2026-09-10
---

# Sample Markdown Document

This document tests the markdown passthrough path
in lore-mcp preprocessing. It contains structured
content with headings, lists, tables, and code blocks.

## Installation

Install lore-mcp from PyPI:

```bash
pip install lore-mcp[parse]
```

For GPU support, ensure CUDA toolkit is available.

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| chunk_size | 1024 | Chunk size in characters |
| chunk_overlap | 128 | Overlap between chunks |
| embedding_model | nomic-v2-moe | Embedding model name |

## Features

- Multi-format parsing (PDF, HTML, DOCX)
- Hybrid search (vector + FTS5)
- LLM enrichment (context, Q&A, metadata)
- Quality gate (lint)

### Preprocessing pipeline

The preprocessing pipeline converts raw sources
to clean markdown ready for indexing:

1. **Parse** — convert format to markdown
2. **Clean** — normalize text (NFC, HTML strip)
3. **Enrich** — optional LLM enrichment
4. **Validate** — quality gate

## License

This document is part of the lore-mcp project,
licensed under AGPL-3.0-or-later.
