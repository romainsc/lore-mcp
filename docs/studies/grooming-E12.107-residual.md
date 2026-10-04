# Grooming E12.107 residual — YouTube video ID with forced extension

## Investigation (2026-10-04)

### Download path (works correctly)

- `_fetch_url` adds extension from Content-Type
  and returns full path (line 106) → `orig_name`
  updated with correct extension (line 323)
- `download_video` uses `%(id)s.%(ext)s` →
  real extension (.webm, .mkv, .mp4) → returned
  in `video_path` → `orig_name` updated (line 293)

Both paths produce correct filenames after
download. No issue there.

### Pre-downloaded files (the actual bug)

`resolve_source_fields` produces `{vid}.mp4`
for YouTube URLs (line 76). But pre-downloaded
files may be `{vid}.webm` or `{vid}.mkv`.

When searching orig_dir:
1. `_orig_dir / "{vid}.mp4"` → not found
2. Glob fallback: `{vid}.mp4` HAS an extension
   → condition `not Path(orig_name).suffix` is
   False → fallback skipped
3. Source reported as missing

## Fix

Remove forced `.mp4` extension for YouTube URLs.
Use video ID without extension:

```python
result["file"] = vid if vid else PurePosixPath(parsed.path).name
```

The extension fallback glob (`{vid}.*`) then
matches any format. After download, `orig_name`
is updated with the real extension.

## DoD

- YouTube video ID without forced extension
- Pre-downloaded .webm/.mkv found via glob
- Download path still works (yt-dlp returns
  real extension)
- Tests updated
- CI green
