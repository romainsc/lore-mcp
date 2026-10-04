# Grooming E12.107 dots — Dotted basenames break extension fallback

## Bug

Extension fallback in `_phase1_worker` (line 257)
has condition `not Path(orig_name).suffix`.

`Path("2606.03019v1").suffix` → `.03019v1`
— Python's `suffix` considers the last dot as
extension separator, regardless of content.

The guard was meant to avoid globbing files that
already have a real extension. But Python's
`suffix` is not a format detector.

## Fix

Remove the suffix guard entirely. The glob
should run whenever the exact file is not found.

```python
# Before:
if not (_orig_dir / orig_name).exists() and not Path(orig_name).suffix:

# After:
if not (_orig_dir / orig_name).exists():
```

The glob `f"{orig_name}.*"` works correctly:
- `2606.03019v1` → glob `2606.03019v1.*`
  → matches `2606.03019v1.html` ✓
- `spec.pdf` (already has extension, file exists)
  → existence check passes, glob never reached ✓
- `spec.pdf` (file doesn't exist) → glob
  `spec.pdf.*` → no match → falls through to
  missing/download path ✓

## DoD

- Dotted basenames found via glob
- Test: `2606.03019v1` finds `2606.03019v1.html`
- Existing tests pass
- CI green
