# Grooming E12.34 — CUDA check in subprocess

- **Status:** Prêt
- **Date:** 2026-09-19

## Problem

`torch.cuda.is_available()` in the main process
allocates 3 MiB VRAM (CUDA driver context) that
cannot be freed. This pollutes the VRAM before
phase 2 IS start (22 MiB → 25 MiB). On a 4 Go
GPU at the edge of capacity, every MiB counts.

## Solution

Run the CUDA diagnostic check in a short-lived
subprocess. When it exits, the 3 MiB are freed.

```python
import subprocess
import json

def _check_cuda() -> bool:
    """Check CUDA in subprocess to avoid VRAM leak."""
    try:
        result = subprocess.run(
            [sys.executable, "-c",
             "import torch; import json; "
             "print(json.dumps({'cuda': torch.cuda.is_available()}))"],
            capture_output=True, text=True, timeout=10,
        )
        return json.loads(result.stdout)["cuda"]
    except Exception:
        return False
```

Called once at pipeline start. Result logged
at debug level. No VRAM consumed in main.

## DoD

1. CUDA check runs in subprocess
2. VRAM identical before and after the check
3. Result (cuda, device, vram_mb) logged at
   debug level
4. Existing tests pass

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
