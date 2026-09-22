# Grooming E12.43 — OCR engine: Tesseract + langue par source

- **Status:** À valider
- **Date:** 2026-09-21

## Problem

RapidOCR (PaddleOCR) utilise des modèles chinois
par défaut. Artefacts OCR sur le français
(`I'homme`). RapidOCR est Level 3 (training data
non publié) — non conforme politique libre.

## Analyse licences OCR (2026-09-21)

| Moteur | Level | FR natif |
|--------|:-----:|:--------:|
| Tesseract | **1-2** ✓ | `fra` ✓ |
| RapidOCR | 3 ✗ | `ch` |
| EasyOCR | 3 ✗ | `fr` |

## Solution

### Langue par source dans le manifest

```yaml
# manifest.yaml
sources:
  - orig: DUDH_2008.png
    lang: fra
  - orig: governing_ai.pdf
    lang: eng
```

### Config OCR

```yaml
# config.yaml
parse:
  ocr_engine: tesseract        # défaut, Level 1-2 libre
  ocr_config:                  # spécifique au moteur
    lang: [fra, eng]
    # scale: 4.0              # optionnel
    # psm: 3                  # optionnel
```

Alternative (non libre, Level 3) :
```yaml
parse:
  ocr_engine: rapidocr
  ocr_config:
    lang: [ch]
```

Docling traduit `ocr_engine` + `ocr_config` en
l'option Docling appropriée :
- `tesseract` → `TesseractCliOcrOptions(**ocr_config)`
- `rapidocr` → `RapidOcrOptions(**ocr_config)`
- `easyocr` → `EasyOcrOptions(**ocr_config)`

Le regex `_fix_ocr_artifacts` ne s'applique que
quand `ocr_engine == "rapidocr"` (le seul qui
produit des artefacts `I'` sur le français).

### Cascade de résolution langue OCR

1. Manifest `lang` par source → langue OCR
2. Config `ocr_config.lang` → fallback
3. Défaut moteur (`eng` pour Tesseract)

### Lien avec E12.36 (enrichissement)

`lang` du manifest → template enrichissement.
`langdetect` en fallback si `lang` absent.

### Config Docling

```python
opts = PdfPipelineOptions()
opts.ocr_options = TesseractOcrOptions(
    lang=source_langs,  # ["fra"] ou ["eng"]
)
```

Utilise `tesserocr` (binding C) pour les
données de confiance et bounding boxes.
`TESSDATA_PREFIX=/usr/share/tesseract/tessdata`
nécessaire.

### Prérequis système

```bash
# Fedora
sudo dnf install tesseract tesseract-devel \
  tesseract-langpack-fra tesseract-langpack-eng \
  leptonica-devel
```

**Ne PAS installer `tesseract-osd`** — l'OSD
(Orientation and Script Detection) cause des
régressions sur les documents multi-colonnes
découpés en régions par Docling. L'OSD détecte
une mauvaise orientation sur les petites régions
→ texte inversé/charabia. Problème connu :
Docling #1657, Tesseract #1926. Quand les
langues sont spécifiées (`fra`, `eng`), l'OSD
n'apporte rien (la détection de script n'est
pas nécessaire).

Sans `tesseract-osd`, Tesseract et tesserocr
dégradent gracieusement : skip OSD, OCR normal.

### Dépendance Python

```
tesserocr  # binding C pour Tesseract
```

Ajouté dans pyproject.toml (extras `[pdf]`).

### Résultats test (2026-09-21)

Tesseract CLI + `lang=['fra', 'eng']` sans OSD
sur DUDH_2008.png :
- `I'` : **0 occurrences** ✓
- `l'` : **40 occurrences** ✓
- Texte français correct
- 11841 chars

### Impact

- Supprime le regex `_fix_ocr_artifacts`
- Conforme Level 1-2
- Nouveau champ `lang` dans le manifest (ISO 639-3)
- `langdetect` reste en fallback pour E12.36
- Fallback RapidOCR si Tesseract absent

## DoD

1. Champ `lang` accepté dans le manifest
2. Docling configuré avec Tesseract + langue
3. DUDH sans artefacts `I'homme`
4. Config `ocr_engine` / `ocr_lang` en fallback
5. Enrichissement utilise `lang` du manifest
6. Regex `_fix_ocr_artifacts` supprimé
7. `tesserocr` dans pyproject.toml
8. Doc: ne pas installer `tesseract-osd`
9. Fallback RapidOCR si Tesseract absent
10. Tests passent

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
