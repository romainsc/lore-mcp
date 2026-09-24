# Grooming E12.63 — Resumable pipeline with persistent checkpoints

- **Status:** Prêt
- **Date:** 2026-09-24

## Problem

Full pipeline takes 5-8h (STT 2h + captioning 3h
+ enrich 1h + build 30min). A reboot, Ctrl+C, or
OOM killer loses all progress.

## Solution

Checkpoint state in XDG_STATE_HOME/lore-mcp/.
Resume from last checkpoint on restart. Purge
mechanism for abandoned states.

### State directory

```
~/.local/state/lore-mcp/
└── <collection-hash>/
    ├── checkpoint.json
    ├── phase1-parse/
    ├── phase2-caption/
    ├── phase3-enrich/
    └── is-logs/
```

collection-hash = SHA-256 of manifest + config
content. Different params = different state dir.

### Checkpoint format

```json
{
  "manifest_hash": "sha256...",
  "config_hash": "sha256...",
  "phases": {
    "phase1": {"completed": [...], "status": "done"},
    "phase1_stt": {"completed": [...], "status": "done"},
    "phase1_7_frames": {"completed": [...], "status": "in_progress"},
    "phase2_granite_vision": {"completed": [...]}
  }
}
```

### Resume logic

1. Read checkpoint.json if exists
2. If manifest_hash or config_hash changed → full restart
3. Skip completed sources per phase
4. After each source → write checkpoint (fsync)
5. --force ignores checkpoint

### Purge mechanism

```bash
lore-mcp state --list     # list all state dirs with age/size
lore-mcp state --purge    # delete states older than 7 days
lore-mcp state --purge-all  # delete all states
```

### Container

Volume mount:
```bash
podman run -v ~/.local/state/lore-mcp:/home/app/.local/state/lore-mcp:Z ...
```

Containerfile:
```dockerfile
ENV XDG_STATE_HOME=/home/app/.local/state
```

### --keep-intermediates

Copies intermediate files from state dir to
prep_dir for inspection. Without flag, state dir
is cleaned after successful completion (preserved
on interruption for resume).

## DoD

1. State in XDG_STATE_HOME/lore-mcp/
2. checkpoint.json for resume
3. Intermediates in state dir, not prep dir
4. --keep-intermediates copies to prep dir
5. lore-mcp state --list/--purge
6. Volume mount in Containerfile
7. --force ignores checkpoint
8. Tests

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
