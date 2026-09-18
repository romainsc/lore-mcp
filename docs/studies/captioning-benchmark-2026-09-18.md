# Image captioning model benchmark

- **Date:** 2026-09-18
- **Test images:** PPTX Parcoursup (49 images, 4 types: BD, slide, timeline, screenshot)

## Models tested

| Model | License | Size | Local GPU (3.7GB) |
|-------|---------|------|:-:|
| RapidOCR (PaddleOCR v6) | Apache 2.0 | CPU | N/A |
| granite-docling-258M | Apache 2.0 | 258M | ✓ (~1GB) |
| SmolVLM-256M-Instruct | Apache 2.0 | 256M | ✓ (~0.5GB) |
| Molmo2-O-7B | Apache 2.0 | 7B | ✗ (CPU only) |
| Claude (reference) | Proprietary | API | N/A |

## Results per image type

### BD/Comic (img_00)

| Model | Output | Quality |
|-------|--------|:-------:|
| OCR | "JE SUIS EXTRÊMEMENT MOTIVEE" (partial, fragmented) | ★★☆ |
| granite-docling | (empty) | ✗ |
| SmolVLM | "a cartoon image of a man and a woman sitting on chairs" | ★☆☆ |
| Molmo | Approximate dialogue, wrong characters, meta-commentary | ★★☆ |
| Claude | Exact dialogue, correct characters, humor context | ★★★ |

### Slide with highlighted text (img_05)

| Model | Output | Quality |
|-------|--------|:-------:|
| OCR | Full text extracted, no structure | ★★☆ |
| granite-docling | **Full text + markdown structure** (headings, bullets) | ★★★ |
| SmolVLM | Not tested | — |
| Molmo | "French-language webpage", "red circles" (wrong) | ★☆☆ |
| Claude | Exact text + highlighting description | ★★★ |

### Timeline (img_06)

| Model | Output | Quality |
|-------|--------|:-------:|
| OCR | Partial text, dates | ★★☆ |
| granite-docling | (empty — "Screenshot" label only) | ✗ |
| SmolVLM | Not tested | — |
| Molmo | "chart", misses timeline structure | ★☆☆ |
| Claude | 3 stages with exact dates, colors, layout | ★★★ |

### Screenshot Parcoursup (img_11)

| Model | Output | Quality |
|-------|--------|:-------:|
| OCR | Full text | ★★☆ |
| granite-docling | **Full text + UI structure** (filters, counts) | ★★★ |
| SmolVLM | Not tested | — |
| Molmo | Correct identification, approximate content | ★★☆ |
| Claude | Exact text + UI description + map | ★★★ |

## Conclusions

1. **No single model covers all image types** — multi-model
   is required
2. **granite-docling** excels on document images (slides,
   screenshots) but fails on visual images (BD, timelines)
3. **SmolVLM-256M is unusable** for RAG — too generic
4. **Molmo 7B** provides usable descriptions but with
   hallucinations and meta-commentary; too slow on CPU
5. **OCR + granite-docling + VLM** is the optimal combination
6. **Docling's 26-class classifier** should route images to
   the appropriate model

## Recommended architecture

```
Image → Docling classifier (26 types)
  → logo/icon/qr_code    → skip
  → screenshot/table      → granite-docling (structured)
  → photograph/comic      → VLM (Molmo/granite-vision)
  → chart/diagram         → OCR + VLM
  → all                   → OCR first (always)
```

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
