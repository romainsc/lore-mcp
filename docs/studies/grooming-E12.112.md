# Grooming E12.112 — TEI restart after long VLM phase

## Bug

TEI container stays in state `Created` (never
starts). `--log-opt path=/tmp/is-logs/x.log`
fails when parent directory doesn't exist.

## Root cause

User config issue. The `start` command in
config.yaml does not create the log directory
before `podman run`.

## Rule

**Start commands must be self-contained.**
Everything provided by the user (start/stop
commands in config.yaml) must be autonomous
and coherent. lore-mcp executes the command
as-is — it does not parse, validate, or
compensate for missing prerequisites.

## Fix

### 1. Fix in user's config.yaml

Add `mkdir -p` before `podman run`:

```yaml
start: >-
  podman ps -q --filter name=tei-nomic-v2 | grep -q . && exit 0;
  podman rm -f tei-nomic-v2 2>/dev/null;
  mkdir -p /tmp/is-logs;
  podman run -d --name tei-nomic-v2
  ...
  --log-opt path=/tmp/is-logs/tei-nomic-v2.log
  ...
```

### 2. Document the rule

In docs/configuration.md and docs/tutorial.md,
add a section:

> **Start/stop commands must be self-contained.**
> The `start` command is executed as a single
> shell command. It must handle all prerequisites:
> create directories, remove stale containers,
> check if already running. lore-mcp does not
> validate or pre-process the command.

### 3. Fix bootstrap.yaml example

Ensure the example start command in
bootstrap.yaml includes `mkdir -p` for any
log directories.

## DoD

- Rule documented in configuration.md
- bootstrap.yaml example is self-contained
- No code change in lore-mcp
- User informed to fix their config.yaml
