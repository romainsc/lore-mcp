# OCR comparison on scanned multi-column document

- **Date:** 2026-09-15
- **Test image:** DUDH_2008.png (Déclaration Universelle des Droits de l'Homme, multi-column layout)
- **Goal:** find an OCR engine that preserves reading order on multi-column French documents

## Engines tested

| Engine | Version | License | Result |
|--------|---------|---------|--------|
| RapidOCR (via Docling) | PP-OCRv6 | Apache 2.0 | Faithful text, **wrong column order** |
| docTR (CRNN + db_resnet50) | 0.12 | Apache 2.0 | Heavy word fragmentation ("reconr ais sance") |
| docTR (PARSeq + layout) | 0.12 | Apache 2.0 | Less fragmentation, still unusable |
| granite-docling-258M | 258M | Apache 2.0 | Correct reading order, **massive hallucinations** ("écrigèrent dès en défini" for "égaux en dignité") |
| Molmo2-O-7B (VLM) | 7B | Apache 2.0 | Refused: "image too small and blurry" |
| PaddleOCR PP-StructureV3 | 3.7 | Apache 2.0 | Not tested: PaddlePaddle unavailable for Python 3.14 |
| Surya OCR | — | Weights: restricted | Not tested: model weights non-libre (free <$5M revenue only) |

## Detailed observations

### RapidOCR (current — best result)

Article Premier correctly extracted:
> Tous les êtres humains naissent libres et égaux en dignité et en droits.
> Ils sont doués de raison et de conscience et doivent agir les uns envers
> les autres dans un esprit de fraternité.

Multi-column mixing in preamble:
> sont engagés à assurer, en coopération I'homme et des libertés
> fondamentales. haute importance pour remplir Considérant que les
> Etats Membres se...

Minor OCR artifacts: `I'homme` instead of `l'homme`.

### granite-docling-258M (worst for French)

Article Premier:
> Tous les êtres humains naissent libres et **écrigèrent dès en défini**
> et en droits. Ils sont **désolés** de raison et de conscience et
> doivent agir les uns **en** les autres dans un **fréprit de statuariat**.

Every article contains fabricated French words. The model appears trained
primarily on English documents. Reading order is correct but text is
unusable.

### docTR

Word-level fragmentation makes the output unusable regardless of
recognition model (CRNN or PARSeq) or layout detection setting.
The `detect_layout=True` parameter (LW-DETR) did not improve results.

### Molmo2-O-7B

General-purpose VLM, not designed for document transcription. Refused
to process a dense text page, citing image quality.

## Conclusion

**RapidOCR remains the best option.** The multi-column reading order
problem is a post-processing concern (E12.23), not an OCR engine
concern. No tested alternative produces both faithful text AND correct
reading order on French multi-column documents.

PaddleOCR PP-StructureV3 with its explicit `block_order` output is
the most promising untested alternative, blocked by Python 3.14
compatibility. Worth revisiting when PaddlePaddle supports 3.14.

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
