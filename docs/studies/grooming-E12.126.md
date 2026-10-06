# Grooming E12.126 — Cleanup intermediates

## Problem

Preprocessing creates `prep/` and `.work/`
directories that persist after indexation.
For MCP tools and CLI build, these are internal
intermediates, not deliverables. For CLI
preprocess, `prep/` is the deliverable.

## Behavior matrix

| Path | MCP tools | CLI `build` | CLI `preprocess` | `--keep-intermediates` |
|------|-----------|-------------|-----------------|----------------------|
| `prep/` | Delete | Delete | **Keep** (deliverable) | Keep |
| `.work/` | Delete | Delete | Delete | Keep |

- **Delete**: after successful completion only
- **Keep on failure**: all intermediates preserved
  for diagnostic
- **`--keep-intermediates`**: override, keep all

## Fix

### MCP tools (server.py)

In `_do_add`, `_do_adds`, `_do_recipe`:
after successful ingest, cleanup intermediates.

```python
if not keep_intermediates:
    import shutil
    prep_dir = col_dir / "prep"
    if prep_dir.exists():
        shutil.rmtree(prep_dir)
    work_dir = col_dir / ".work"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    # Clean prep recipe
    if prep_recipe.exists():
        prep_recipe.unlink()
```

### CLI build (build.py)

After successful build (after metadata output):
```python
if not config.keep_intermediates:
    import shutil
    prep_dir = Path(_build_dir) / "prep"
    if prep_dir.exists():
        shutil.rmtree(prep_dir)
    work_dir = Path(_build_dir) / ".work"
    if work_dir.exists():
        shutil.rmtree(work_dir)
```

### CLI preprocess (preprocess/__init__.py)

After successful phase 4 write:
```python
if not keep_intermediates:
    import shutil
    if _inter_dir.exists():
        shutil.rmtree(_inter_dir)  # .work/ only
    # prep/ preserved — it's the deliverable
```

## DoD

- MCP tools: prep/ + .work/ deleted after success
- CLI build: prep/ + .work/ deleted after success
- CLI preprocess: .work/ deleted, prep/ preserved
- --keep-intermediates: all preserved
- Failure: all preserved
- Tests
- CI green

## Effort

Petit — cleanup logic in 3 places + tests.
