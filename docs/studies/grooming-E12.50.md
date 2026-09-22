# Grooming E12.50 — Format detection via mimetypes

- **Status:** Prêt
- **Date:** 2026-09-22

## Problem

_FORMAT_MAP lists extensions manually. New formats
require manual additions. Audio/video have many
variants (.wma, .aac, .mov, .wmv, etc.).

## Solution

Use mimetypes.guess_type() (stdlib) for audio/video.
Keep explicit map for library-specific backends.

```python
import mimetypes

_BACKEND_MAP = {
    ".md": "markdown",
    ".html": "html", ".htm": "html",
    ".pdf": "docling", ".docx": "docling",
    ".pptx": "docling", ".xlsx": "docling",
    ".epub": "docling",
    ".png": "docling", ".jpg": "docling",
    ".jpeg": "docling", ".tiff": "docling",
    ".csv": "markitdown",
    ".json": "markitdown", ".xml": "markitdown",
}

def detect_format(filename):
    ext = Path(filename).suffix.lower()
    if ext in _BACKEND_MAP:
        return _BACKEND_MAP[ext]
    mime, _ = mimetypes.guess_type(filename)
    if mime:
        if mime.startswith("audio/"):
            return "audio"
        if mime.startswith("video/"):
            return "video"
    raise FormatNotSupported(...)
```

## DoD

1. _FORMAT_MAP renamed _BACKEND_MAP
2. Audio/video detected via mimetypes
3. All existing tests pass
4. No new dependency

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
