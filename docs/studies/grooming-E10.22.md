# Grooming E10.22 — Demo mode

- **Status:** Validé
- **Date:** 2026-09-01

## Context

A Platform component should be understandable.
New users need to see what lore-mcp does at each
step — not just the final result. Demo mode is a
pedagogical tool that explains the system by
running it transparently.

## Flags

- `--demo`: explain each action before executing.
  Show intermediate data (chunk count, embedding
  dimension, scores, timing).
- `--step`: pause between each atomic action.
  User presses Enter to continue. Implies --demo.

## Output example (--demo)

```
[DEMO] Step 1/5: Preprocessing
  Reading intro.md (2.4 KB)
  Stripping NUL characters... 0 found
  Stripping base64 lines... 0 removed
  Result: 2.4 KB (unchanged)

[DEMO] Step 2/5: Chunking
  Splitter: RecursiveCharacterTextSplitter
  chunk_size=1024, overlap=128
  Separators: ## > ### > \n\n > \n > space
  Result: 3 chunks (avg 812 chars)

[DEMO] Step 3/5: Embedding
  Model: nomic-ai/nomic-embed-text-v2-moe
  Mode: builtin (GPU FP16, RTX 500 Ada)
  Batch size: 3 (1 batch)
  Result: 3 vectors × 768 dimensions (normalized)

[DEMO] Step 4/5: Storage
  Database: ./output/test-libre.db
  Table: chunks_vec (vec0, cosine distance)
  Inserting 3 chunks with rowid sync...
  Result: 3 rows in chunks + chunks_vec

[DEMO] Step 5/5: Metadata
  Source: intro.md → title="Introduction", author="RC"
  Stored in sources table
```

With `--step`, each `[DEMO]` block pauses:
```
[DEMO] Step 2/5: Chunking
  ...
  Press Enter to continue...
```

## Implementation

- `DemoReporter` class: receives events from
  ingest/eval/optimize, formats pedagogical output
- Injected via optional parameter (no demo =
  no overhead)
- `--demo` and `--step` flags on build, eval,
  optimize subcommands
- `input("Press Enter to continue...")` for step
  mode

## DoD

1. `DemoReporter` class
2. `--demo` flag on build/eval/optimize
3. `--step` flag (implies --demo, pauses)
4. Pedagogical output for: preprocess, chunk,
   embed, store, evaluate, optimize
5. Shows intermediate data
6. Tests TDD (mock input for step mode)
7. Documentation updated

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
