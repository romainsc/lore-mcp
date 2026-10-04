# Grooming E12.107 — URL-only sources not found in orig_dir

## Bug

`resolve_source_fields()` extracts URL basename
without extension (e.g. `open-source-ai-definition`
from `https://example.com/open-source-ai-definition`).

When the file is pre-downloaded, `_fetch_url`
adds an extension from Content-Type (e.g.
`.html`). The pipeline then searches for
`open-source-ai-definition` but the file is
`open-source-ai-definition.html`.

10/21 sources fail in E2.06 validation.

## Root cause

No extension-aware fallback when looking up
source files in `_phase1_worker`.

## Fix

In `_phase1_worker`, before the "file not found"
check: if `orig_name` has no extension, glob
for `orig_name.*` in orig_dir and downloads_dir.
If found, update `orig_name` and
`resolved["file"]`.

```python
if not (_orig_dir / orig_name).exists() and not Path(orig_name).suffix:
    for candidate in sorted(_orig_dir.glob(f"{orig_name}.*")):
        orig_name = candidate.name
        resolved["file"] = orig_name
        break
```

Only triggers when `orig_name` has no extension
(has a dot) — files with extensions are matched
exactly as before.

## DoD

- URL-only source with pre-downloaded `.html`
  file found via extension fallback
- Exact-match behavior unchanged for files with
  extensions
- Test: `_phase1_worker` with `url:` source and
  pre-downloaded `name.html` → status ok
- CI green

## MVP

Single fix in `_phase1_worker`.
