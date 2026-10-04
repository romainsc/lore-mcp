# Grooming E12.109 — Poor sources not indexed

## Investigation (2026-10-04)

### Root cause analysis

worldcup.json: markitdown produces raw JSON
(no conversion to text). heading_count=0,
structure_score=0.0, text_density=0.41 → "poor".
Justified — raw JSON has no headings, low
semantic structure for RAG.

aout-2026.xlsx: Docling produces table markdown
but no headings. heading_count=0,
structure_score=0.0, text_density=0.1 → "poor".
Justified — a calendar spreadsheet has little
semantic value.

Both sources are legitimately poor quality for
RAG. The quality gate is working correctly.
E3.31 (structured data to knowledge) would
address JSON/CSV with LLM narration.

### Current behavior

quality_gate(force=False) → passed=False →
file unlinked → reported as "poor" → not indexed.

### Desired behavior

All sources indexed by default, including poor.
User can opt OUT of indexing poor sources.
Rationale: the user explicitly listed these
sources in the recipe — they want them indexed.
Quality is a warning, not a gate.

## Fix

Invert the default: quality gate reports but
does NOT block by default. Add `skip_poor`
option (default False) to exclude poor sources.

In preprocess/__init__.py phase 4:

```python
skip_poor = getattr(config, "skip_poor", False)
qg = quality_gate(str(out_file))

if qg["verdict"] == "poor" and skip_poor:
    out_file.unlink()
    reports.append({...status: "poor"...})
    continue
# otherwise: index with warning in report
```

In config.py: add `skip_poor: bool = False`.

In server.py add_recipe: add optional
`skip_poor` param.

## DoD

- Default: all sources indexed (including poor)
- Poor sources logged with warning in report
- `skip_poor=true` excludes poor sources
- Quality gate verdict preserved in report
- Test: poor source indexed by default
- CI green
