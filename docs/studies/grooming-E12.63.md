# Grooming E12.63 — Resumable pipeline with persistent checkpoints

- **Status:** Prêt (revised 2026-09-24)
- **Date:** 2026-09-24

## Problem

Full pipeline takes 5-8h (STT 2h + captioning 3h
+ enrich 1h + build 30min). A reboot, Ctrl+C, or
OOM killer loses all progress.

## Solution (revised)

Two mechanisms:
- **Report file** = checkpoint + livrable
- **Intermediates** in XDG_STATE_HOME (default)
  or explicit directory

### Report as checkpoint

`--report` (optional): path to report file.
Default: `./preprocess-report.json`.
Written progressively during run. Contains per-
source and per-image status. If the file exists
on startup → resume from where it stopped.
`--force` ignores it.

### Intermediates directory

`--intermediates-dir` (optional): where to store
phase files (phase1-parse.md, caption-*.md,
docling.json, is-logs). If absent → default to
`XDG_STATE_HOME/lore-mcp/<hash>/`.

Intermediates are always persistent (needed for
resume). Conserved after success (reusable for
different params). Purge via `lore-mcp state`
(E12.66).

### State directory (default intermediates)

```
~/.local/state/lore-mcp/
└── <collection-hash>/
    ├── phase1-parse/
    ├── phase2-caption/
    ├── phase3-enrich/
    └── is-logs/
```

collection-hash = SHA-256 of manifest + config.

### CLI

```bash
# Default: report in ./ intermediates in XDG
lore-mcp build ... --preprocess

# Named report
lore-mcp build ... --preprocess --report run.json

# Resume (report exists)
lore-mcp build ... --preprocess --report run.json

# Intermediates visible
lore-mcp build ... --preprocess \
  --intermediates-dir ./intermediates/

# Force restart
lore-mcp build ... --preprocess --report run.json --force
```

### Container

Volume mount for intermediates:
```bash
podman run \
  -v ~/.local/state/lore-mcp:/home/app/.local/state/lore-mcp:Z \
  ...
```

```dockerfile
ENV XDG_STATE_HOME=/home/app/.local/state
```

### Resume logic

1. Read report file if exists
2. Per phase, per source: skip status != pending
3. After each source → write report (fsync)
4. --force ignores existing report

## DoD

1. --report for checkpoint + livrable
2. --intermediates-dir (default XDG_STATE_HOME)
3. Resume from existing report
4. Progressive write after each source
5. Intermediates conserved after success
6. Container volume mount
7. Tests
6. Volume mount in Containerfile
7. --force ignores checkpoint
8. Tests

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
