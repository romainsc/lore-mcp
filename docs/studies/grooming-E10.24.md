# Grooming E10.24 — Output management

- **Status:** Validé
- **Date:** 2026-09-01

## Five output levels

| Flag | lore-mcp output | Logging |
|------|-----------------|---------|
| `--quiet` | Nothing | ERROR |
| `--progress` | One line per milestone | WARNING |
| *(default)* | Full (header, ★ table, summary) | WARNING |
| `--verbose` | Full + per-file detail | WARNING |
| `--debug` | Verbose + internal logs | INFO |

## DoD

1. Mutually exclusive flags: --quiet/--progress/--verbose/--debug
2. ProgressReporter accepts output_level
3. run_optimize/run_build/run_eval use ProgressReporter
4. Silence third-party loggers by default
5. Tests TDD
6. Documentation

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
