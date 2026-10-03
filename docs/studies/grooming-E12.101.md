# Grooming E12.101 — Download to build_dir, not orig_dir

## Context

CLAUDE.md §12 rule: "Input files are never
modified — all commands write to output
directories, never modify files provided as
input."

## Bug

`_phase1_worker()` in `preprocess/__init__.py`
downloads files to `_orig_dir`, which is the
user's source directory (read-only by contract):

1. **Line 278**: `download_video(source_url,
   str(_orig_dir), ...)` — yt-dlp video download
   writes to orig_dir
2. **Line 287**: `md_path = _orig_dir / md_name`
   — captions written to orig_dir
3. **Line 307**: `_fetch_url(source_url,
   _orig_dir / orig_name)` — HTTP download
   writes to orig_dir

The same issue exists in the main
`preprocess_sources()` (line 785 — video
download in STT phase) but that one writes to
`_prep_dir` which is correct.

## Impact

- User's source directory gets modified with
  downloaded files mixed in with originals
- If user re-runs preprocess, the downloaded
  files look like pre-existing originals
- Violates the immutability contract

## Fix

### MVP1 — Download to work dir

Replace download destination from `_orig_dir`
to a downloads subdirectory in the work area.

In `_phase1_worker()`:

```python
_downloads_dir = Path(prep_dir) / "downloads"
_downloads_dir.mkdir(parents=True, exist_ok=True)
```

Then replace:
- Line 274: `video_dest = _orig_dir / video_name`
  → `_downloads_dir / video_name`
- Line 278: `download_video(..., str(_orig_dir))`
  → `download_video(..., str(_downloads_dir))`
- Line 287: `md_path = _orig_dir / md_name`
  → `_downloads_dir / md_name`
- Line 307: `_fetch_url(source_url, _orig_dir / orig_name)`
  → `_fetch_url(source_url, _downloads_dir / orig_name)`

After download, the pipeline already updates
`resolved["file"]` and `orig_name` — the
subsequent `src_path = _orig_dir / orig_name`
(line 322) must also search `_downloads_dir`:

```python
src_path = _orig_dir / orig_name
if not src_path.exists():
    src_path = _downloads_dir / orig_name
```

### MVP2 — Same fix in preprocess_sources()

The `preprocess_sources()` function in the main
process also has URL download logic (lines
548-560 of the current code). Apply the same
pattern: download to `_inter_dir / "downloads"`.

Note: line 785 (`download_video` in STT phase)
already uses `_prep_dir` — correct, no change.

## DoD

- Downloads go to `build_dir/.work/downloads/`
  (or `prep_dir/downloads/` in legacy mode)
- `_orig_dir` is never written to
- Existing tests pass (download tests use
  tmp_path as orig_dir — should still work)
- Test: verify orig_dir is not modified after
  preprocess with URL sources
- CI green

## Dependencies

None.

## Risks

- Downloads may not be found on resume if the
  work dir is cleaned. Mitigation: downloads
  dir is inside `.work/` which is preserved
  by default (only cleaned with `--purge`).
- Path resolution for downloaded files changes
  — need to verify `detect_format` and the
  parse path still find the file.
