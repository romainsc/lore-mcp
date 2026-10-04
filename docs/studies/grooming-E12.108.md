# Grooming E12.108 — 2 sources missing from preprocess report

## Bug

21 sources in recipe, 19 in preprocess report.
`aout-2026.xlsx` and `worldcup.json` silently
dropped — not in ok, missing, or error lists.

## Hypothesis

The Docling batch path (`docling_batch` list)
collects sources for batch conversion. If
`parse_batch_docling` fails or returns no result
for a source, and the error handling doesn't
add it to `parsed_meta` or `errors`, the source
disappears from the report.

Likely: the source is added to `docling_batch`
(line 338-346) but the batch result doesn't
include it, and the post-batch loop (line 401)
skips it silently.

## Investigation result (2026-10-04)

Docling batch error handling (lines 410-428) is
correct — errors are recorded in both `errors`
and `parsed_meta`.

The root cause is likely E12.107: URL-only sources
resolve to extensionless filenames, and the
pre-downloaded files have extensions. The sources
are not found and disappear because:
1. `detect_format` was called with `path.name`
   (no path) so puremagic content detection
   could not run
2. `parse_to_markdown` had the same issue

Both are now fixed (E12.107): `detect_format`
receives full path in both `_phase1_worker` and
`parse_to_markdown`.

## Additional fix

Sources with `status != "ok"` in `parsed_meta`
but not in `errors` are silently dropped from
the final `reports` list (line 1104 skips them
without adding to reports). Added
`reports.append(...)` for missing/error sources
that reach phase 4 without `cleaned`.

## DoD

- All sources appear in final report
- Test: 3 sources (1 ok, 2 missing) → 3 entries
- CI green
