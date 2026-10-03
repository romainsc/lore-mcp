# Grooming E12.104 — YouTube URL name collision

## Bug

`resolve_source_fields()` in recipe.py extracts
the basename from the URL path:

```python
# recipe.py:70
result["file"] = PurePosixPath(parsed.path).name
```

For YouTube URLs like
`https://youtube.com/watch?v=VCqIfIXmFMM`,
the path is `/watch` → basename is `watch`.
Three different YouTube URLs all resolve to
`watch.md`, causing silent overwrites.

The yt-dlp path (E12.81) uses the video ID
as filename, but `resolve_source_fields` runs
before yt-dlp and doesn't know about video
platform URLs.

## Fix

Add YouTube/video platform detection in
`resolve_source_fields()`:

```python
if "file" not in result:
    url = result.get("url")
    if not url:
        raise ValueError(...)
    parsed = urlparse(url)
    # Extract video ID for known platforms
    if "youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc:
        from urllib.parse import parse_qs
        if "youtu.be" in parsed.netloc:
            vid = parsed.path.strip("/")
        else:
            vid = parse_qs(parsed.query).get("v", [""])[0]
        if vid:
            result["file"] = f"{vid}.mp4"
        else:
            result["file"] = PurePosixPath(parsed.path).name
    else:
        result["file"] = PurePosixPath(parsed.path).name
```

This aligns `resolve_source_fields` with the
yt-dlp naming convention (E12.73/E12.81).

## DoD

- 3 YouTube URLs produce 3 distinct filenames
- Video ID used as filename for YouTube URLs
- Non-YouTube URLs unaffected
- Test: resolve_source_fields with 3 YouTube
  URLs, verify unique filenames
- CI green

## MVP

Single fix in `resolve_source_fields()`.
