# Study E12.88: Docling export_to_markdown Options

> Date: 2026-09-29
> Status: Verified (tested on test-redist corpus)

## Methodology

Tested on two sources from the test-redist corpus:
- **governing_ai_for_humanity_final_report_en.pdf**
  (54 pictures, 8 tables, 285K chars)
- **aout-2026.xlsx** (0 pictures, 3 tables, 11K chars)

Baseline: `export_to_markdown(image_mode=ImageRefMode.EMBEDDED)`
(current lore-mcp default).

## Results

### Size comparison

| Option | governing_ai (chars) | delta | aout-2026 (chars) | delta |
|---|---|---|---|---|
| **default** | 284,946 | — | 11,251 | — |
| traverse_pictures | 321,269 | +12.7% | 11,251 | 0% |
| compact_tables | 259,060 | -9.1% | 2,721 | -75.8% |
| strict_text | 284,946 | 0% | 11,251 | 0% |
| labels=text_only | 95,371 | -66.5% | 0 | -100% |

### Option analysis

#### 1. traverse_pictures — MEDIUM priority

**What it does**: exports text content nested inside
picture elements (children RefItems). The PDF has 54
pictures, some with 2-9 text children (captions, labels,
axis text from charts).

**Impact**: +36K chars (+12.7%) for governing_ai. The
added content is mostly chart text, figure captions,
and diagram labels — fragmented single words/lines
(`=`, `pad`, `©`, `United`, `Nations`). Quality is low
for RAG — noisy OCR fragments from chart elements.

**Recommendation**: **Leave disabled.** The added content
is noise — OCR fragments from figures that don't form
coherent searchable text. If future Docling versions
improve picture text extraction, reconsider.

#### 2. compact_tables — HIGH priority

**What it does**: strips padding whitespace from table
cells. `| About the Advisory Body          |   4 |`
becomes `| About the Advisory Body | 4 |`.

**Impact**: -9.1% for PDF (modest), **-75.8% for XLSX**
(dramatic). The XLSX is pure table — compact reduces it
from 11K to 2.7K chars. For RAG, this directly reduces
chunk sizes for table-heavy documents, fitting more
semantic content per chunk.

**Table readability**: identical information, just no
padding. Markdown renderers produce the same visual
output. No content loss.

**Recommendation**: **Enable.** Pure gain — smaller
chunks, same information, better chunk density for
table-heavy documents. No downside.

#### 3. strict_text — DEPRECATED

**What it does**: was supposed to strip formatting
markers. Now deprecated in our Docling version (2.107.0)
— the parameter is accepted but ignored with a warning.

**Impact**: zero (identical output to default).

**Recommendation**: **Ignore.** Deprecated parameter.

#### 4. labels filter — LOW priority (research)

**What it does**: exports only elements matching the
specified label set. `labels={"text", "paragraph"}`
strips headings, tables, pictures, lists — only body
text paragraphs remain.

**Impact**: -66.5% for PDF (heading structure lost),
-100% for XLSX (all tables, no text). Destroys document
structure that is critical for chunking and retrieval.

**Recommendation**: **Do not use for indexing.** Useful
for a specialized "text-only" export for specific
analyses, but destroys the structure that
MarkdownTextSplitter relies on for chunk boundaries.

#### 5. included_content_layers — VERIFIED OK

**What it does**: controls which content layers are
exported. Default is `{ContentLayer.BODY}`.

**Verification**: FURNITURE layer contains page headers/
footers (page numbers, repeated document title).
For governing_ai: 2,419 chars of furniture vs 280,653
body. Content: `"September 2024"`, `"Final Report"`,
page numbers — noise for RAG.

**Default behavior is correct**: BODY only excludes
furniture. No change needed.

## Summary

| Option | Recommendation | Priority | Action |
|---|---|---|---|
| compact_tables | **Enable** | HIGH | Add to default export call |
| traverse_pictures | Disable | — | Leave as-is |
| strict_text | N/A | — | Deprecated, ignored |
| labels | Do not use | — | Destroys structure |
| content_layers | Default OK | — | BODY only is correct |

## Recommendation

Enable `compact_tables=True` in `parse_to_markdown()`
export call. Single line change, pure gain for
table-heavy documents (XLSX, PDF with data tables).

```python
# Current:
result = doc.export_to_markdown(image_mode=ImageRefMode.EMBEDDED)

# Proposed:
result = doc.export_to_markdown(
    image_mode=ImageRefMode.EMBEDDED,
    compact_tables=True,
)
```
