# Grooming E12.31 — Subprocess isolation for parse

- **Status:** Prêt
- **Date:** 2026-09-19

## Problem

Docling (phase 1) initializes a PyTorch CUDA
context during parse (~128 MiB). This context
cannot be freed without killing the Python
process. After `unload_docling()` with
gc.collect + torch.cuda.empty_cache, VRAM goes
from 822→150 MiB but not to 22 MiB.

The 128 MiB difference puts granite-vision NF4
at the exact edge of OOM on high-res images
(DUDH 2480×3548). Non-reproducible 507 errors.

Measured:
- Before parse: 22 MiB used, 3798 MiB free
- After unload: 150 MiB used, 3670 MiB free
- With subprocess: 22 MiB used, 3798 MiB free

## Solution

Run phase 1 (parse) in a subprocess. When it
exits, the CUDA context is fully released.
Phase 2 (caption) starts with pristine VRAM.

### Architecture

```
Main process (orchestrator)
│
├─ Phase 1: fork subprocess
│     → Docling parse ALL sources
│     → Write phase1-parse.md files to disk
│     → Exit (CUDA context freed)
│
├─ Read phase1-parse.md files back
│
├─ Phase 2: caption (main process, clean VRAM)
│     → start IS, caption, stop IS
│
├─ Phase 3: clean + enrich
│
└─ Phase 4: validate + write
```

### Implementation

Use `multiprocessing` with a simple pattern:

```python
import multiprocessing

def _run_phase1(manifest, orig_dir, prep_dir, 
                manifest, orig_dir, prep_dir, report_path):
    """Run in subprocess — parse all sources."""
    # Docling loads here, CUDA context here
    parsed = {}
    errors = []
    for source in manifest["sources"]:
        text = parse_to_markdown(str(src_path))
        _write_phase(prep_dir, target, 
                     "phase1-parse", text)
        parsed[path] = {"orig": ..., "status": "ok",
                        "text_file": "...phase1-parse.md"}
    # Write report to disk
    json.dump({"parsed": parsed, "errors": errors},
              open(report_path, "w"))
    # Process exits → CUDA freed

def preprocess_sources(...):
    # Phase 1 in subprocess
    report_path = prep_dir / "phase1-report.json"
    p = multiprocessing.Process(
        target=_run_phase1,
        args=(manifest, orig_dir, prep_dir,
              str(report_path)))
    p.start()
    p.join()
    # VRAM is now 22 MiB
    
    # Read results from disk
    report = json.load(open(report_path))
    for key, meta in report["parsed"].items():
        text = (prep_dir / meta["text_file"])
                .read_text()
        parsed[key] = {..., "text": text}
    
    # Phase 2+ in main process (clean VRAM)
    ...
```

### Data exchange — all on disk

No Queue, no pickle. The subprocess writes:

1. `{name}.phase1-parse.md` — parsed text
   (already implemented by E12.27)
2. `phase1-report.json` — metadata + errors

```json
{
  "parsed": {
    "doc.md": {
      "orig": "doc.pdf",
      "path": "doc.md",
      "title": "...",
      "status": "ok",
      "text_file": "doc.phase1-parse.md"
    }
  },
  "errors": [
    {"file": "gone.pdf", "status": "missing"}
  ]
}
```

The main process reads `phase1-report.json` +
phase1-parse.md files. OCR text is read from the
files, not serialized in JSON. Consistent with
E12.27 progressive output principle.

If the subprocess crashes, partial files remain
for debugging.

### Edge cases

- Parse errors: written to phase1-report.json
  (not exceptions across process boundary)
- Subprocess crash: main process checks exit code
  and reads whatever phase1 files exist
- unload_docling not needed: subprocess exit
  handles VRAM release

## DoD

1. Phase 1 runs in subprocess
2. VRAM after phase 1 = 22 MiB (same as before)
3. Phase1 files written to disk (unchanged)
4. Parse errors reported correctly
5. Existing tests pass
6. DUDH test: granite-vision has 3798 MiB free

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
