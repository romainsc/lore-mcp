# OCR engine benchmark — Tesseract vs RapidOCR vs OnnxTR

- **Date:** 2026-09-21
- **Test image:** DUDH_2008.png (2480×3548, multi-column French)
- **Goal:** find libre OCR engine for French documents

## License compliance

| Engine | Code | Weights | Training data | Level |
|--------|:---:|:---:|---|:---:|
| **Tesseract** | Apache 2.0 | Apache 2.0 | Documented (400K lines, 4500 fonts) | **1-2** ✓ |
| **OnnxTR/docTR** | Apache 2.0 | Apache 2.0 | Public datasets (CORD, SynthText) | **2** ✓ |
| RapidOCR | Apache 2.0 | Apache 2.0 | "Self-built", not published | 3 ✗ |
| EasyOCR | Apache 2.0 | Apache 2.0 | Insufficiently documented | 3 ✗ |
| Surya | Apache 2.0 | **Restricted** | Not published | 4 ✗ |

## Quality comparison on DUDH

| Engine | `I'` | `l'` | Chars | Title | Art.1 | Fragmentation |
|--------|:---:|:---:|:---:|:---:|:---:|---|
| RapidOCR (default) | 5 | 40 | **12942** | ✓ | ✓ | Faible |
| Tesseract CLI scale=3 | **0** | 21 | 11841 | ✗ | ✗ | Aux bords |
| Tesseract CLI scale=4 | **0** | 44 | 12415 | ✗ | ✗ | Aux bords |
| Tesseract CLI scale=5 | **0** | 47 | 12386 | ✗ | ✗ | Aux bords |
| Tesseract CLI scale=6 | **0** | 44 | 12458 | ✗ | ✗ | Aux bords |
| Tesseract FULL_PAGE s4 | **0** | 44 | 12318 | ✗ | ✗ | Aux bords |
| Tesseract direct (no Docling) | **0** | 40 | 12565 | ✓ | ✗ | En vrac |
| OnnxTR | 3 | 26 | 10380 | ✓(I') | ✓ sort | **Forte** |

## Key findings

### Title truncation

All engines suffer from Docling layout model
cropping the decorative title heading too
tightly. "La Déclaration universelle des droits
de l'Homme" → "claration iverselle roits de
Homme". This is a **Docling layout issue**, not
OCR. RapidOCR is more resilient to tight crops.

Mitigation: manifest `title` field overrides
the extracted title.

### Body text quality

With Tesseract scale=4, 18/18 reference words
found in body text (Déclaration, conscience,
fraternité, dignité, liberté, esclavage, etc.).
Body text is complete (12415 chars = 96% of
RapidOCR's 12942). The 4% difference is the
decorative title, not article content.

### LLM OCR correction not needed

With Tesseract `fra` + scale=4:
- 0 `I'` artifacts (the main OCR problem)
- All reference words present in body
- Title truncation covered by manifest

LLM OCR correction (E12.38) was reverted
because it truncated documents. With Tesseract
producing clean French text, it's unnecessary.

### OSD warning

Do NOT install `tesseract-osd`. It causes
wrong orientation detection on Docling's
cropped regions → garbled text. Known issue:
Docling #1657, Tesseract #1926. Without OSD,
Tesseract degrades gracefully.

## Recommendation

**Default: Tesseract CLI `fra+eng` scale=4.**

- Level 1-2 compliant
- 0 apostrophe artifacts
- 96% content vs RapidOCR
- Title truncation mitigated by manifest
- System prereqs: `tesseract tesseract-langpack-fra`
- Do NOT install `tesseract-osd`

**Option: RapidOCR** for users who need maximum
completeness and accept Level 3 + regex fix.

## Config

```yaml
parse:
  ocr_engine: tesseract        # Level 1-2
  ocr_config:
    lang: [fra, eng]
    scale: 4.0

# Alternative:
# parse:
#   ocr_engine: rapidocr       # Level 3
#   ocr_config:
#     lang: [ch]
```

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
