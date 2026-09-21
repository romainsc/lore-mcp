# Design — Refonte architecture : Docling-native

- **Status:** À valider
- **Date:** 2026-09-21
- **Scope:** E12.30, E12.28, E12.36-41
- **Référence:** docling-capabilities-analysis-2026-09-20.md

## Constat

lore-mcp réimplémente ~300 lignes de captioning
(VLM API call, classify, skip small, dedup) que
Docling fait nativement. Les items E12.36-41
ont produit des régressions car granite-8b ne
suit pas les instructions de prompt (langue,
préservation, correction OCR). Le pipeline est
trop complexe.

## Principes de la refonte

1. **Docling fait le travail lourd** : parse,
   OCR, captioning images, classification. On
   configure, on ne réimplémente pas.
2. **lore-mcp orchestre** : manifest, phases,
   IS lifecycle, progressive output, multi-model,
   judge, enrichissement, dedup, PII, qualité.
3. **Les notions avancées sont préservées** :
   multi-model, judge, OCR-first (comme option).
4. **Pas de prompt engineering fragile** : si le
   LLM ne suit pas une instruction de prompt
   (langue, préservation), ne pas s'appuyer
   dessus — utiliser une approche structurelle.

## Architecture cible

```
Phase 1: Parse + Caption primaire (subprocess)
│  Docling avec :
│  - standard pipeline (PDF/DOCX/PPTX/XLSX)
│  - do_picture_description = True
│  - PictureDescriptionApiOptions → IS primaire
│  - do_picture_classification = True
│  - ocr_lang configurable
│  - image_mode = EMBEDDED
│  → phase1-parse.md (texte + captions intégrés)
│  → subprocess exit (VRAM libérée)
│
Phase 2: Caption supplémentaires (optionnel)
│  Si multi-model configuré :
│  Pour chaque modèle additionnel :
│  - Start IS → caption toutes les images
│  - → phase2-caption-{model}.md
│  - Stop IS
│  Puis : judge sélectionne le meilleur
│  (candidats = texte phase 1 + chaque modèle)
│
Phase 3: Clean + Enrich
│  - clean_text (NFC, HTML, strip base64→alt)
│  - LLM enrichment (context, Q&A, meta)
│  - PII detection
│  → phase3-enrich.md
│
Phase 4: Validate + Write
│  - Dedup, quality gate
│  - Fichier final (sans suffixe)
│  - Manifest enrichi, rapport
```

## Phase 1 : Docling-native

### Configuration

```python
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    PictureDescriptionApiOptions,
)

opts = PdfPipelineOptions()
opts.do_picture_classification = True
opts.do_picture_description = True
opts.generate_picture_images = True
opts.enable_remote_services = True
opts.picture_description_options = (
    PictureDescriptionApiOptions(
        url="http://127.0.0.1:8092/v1/chat/completions",
        params={"model": "granite-vision"},
        prompt="Describe this image in detail...",
        timeout=180,
        picture_area_threshold=0.02,
    )
)
```

Lore-mcp traduit la section config YAML en
options Docling :

```yaml
parse:
  caption_primary: granite-vision  # IS pour Docling
  caption_additional: [molmo-7b]   # multi-model phase 2
  caption_judge: granite-8b
  ocr_lang: fr
```

### Ce que Docling gère en phase 1

- Parse multi-format
- OCR (RapidOCR, avec langue)
- Classification images (26 classes)
- Captioning images via API externe
- Skip petites images (area_threshold)
- Table extraction
- Export markdown avec captions intégrés

### Ce que lore-mcp gère en phase 1

- Résolution manifest (orig → path)
- Fetch URL si nécessaire
- Column reorder (bbox clustering, images OCR)
- Subprocess isolation (VRAM)
- Phase1 files sur disque
- Phase1-report.json

## Phase 2 : Multi-model (optionnel)

Si `caption_additional` est vide → pas de phase 2.
Le résultat Docling de phase 1 suffit.

Si multi-model :
1. Extraire les images du markdown phase 1
   (regex base64 ou images référencées)
2. Pour chaque modèle additionnel :
   - Start IS
   - Caption chaque image via API
   - Write phase2-caption-{model}.md
   - Stop IS
3. Judge : candidats = texte phase 1 (Docling) +
   captions modèles additionnels
4. Le juge sélectionne le meilleur par image

### OCR-first (option pour phase 2)

Si un modèle additionnel bénéficie du contexte
OCR, l'OCR extrait par Docling en phase 1 peut
être injecté dans le prompt du modèle phase 2.
C'est la valeur ajoutée lore-mcp — Docling ne
le fait pas.

## Phase 3 : Enrichissement

### Problèmes identifiés et solutions

**Langue** : "Respond in same language" ne
fonctionne pas avec granite-8b. Solution :
détecter la langue du document avec `langdetect`
(Apache 2.0, 55 langues), puis écrire le prompt
d'enrichissement dans la langue détectée.

Vérifié : granite-8b répond en français quand
le prompt est en français (test 2026-09-21).

Détection : `langdetect.detect(text[:500])`
une fois par document. Résultat : code ISO
("fr", "en", "de", etc.).

Pour les langues courantes (FR, EN, ES, DE, ...),
templates de prompt hardcodés. Pour les autres :
instruction "Write in {language_name}" en
fallback.

```python
from langdetect import detect

lang = detect(text[:500])  # "fr", "en", etc.
prompt = ENRICH_PROMPTS.get(lang, {}).get(
    "context",
    f"Write in {lang}. Add a contextual paragraph..."
)
```

Dépendance : `langdetect` (Apache 2.0, ~1 MB,
pip install langdetect).

**Préservation contenu** : ne pas envoyer le
texte complet au LLM pour réécriture. Enrichir
section par section et reconstruire. Le LLM
ajoute du texte, ne remplace pas.

**Correction OCR** : ne pas envoyer 12K chars
au LLM (il tronque). Si correction OCR par LLM
est nécessaire, découper en sections et corriger
section par section.

## Impacts

### Items à revoir

| Item | Impact |
|------|--------|
| E12.30 | C'EST cette refonte. Absorbe la config Docling. |
| E12.28 | Simplifié : primaire via Docling, additionnels en phase 2. |
| E12.36 | Remplacé : prompts par langue (structurel, pas instruction). |
| E12.38 | Revu : correction OCR par section, pas document entier. |
| E12.39 | Résolu : enrichir par ajout, pas réécriture. |
| E12.41 | Résolu : captioning primaire via Docling, pas nos prompts. |

### Items qui restent inchangés

| Item | Pourquoi |
|------|----------|
| E12.23 | Column reorder — Docling ne le fait pas. |
| E12.25 | IS lifecycle — Docling ne gère pas les conteneurs. |
| E12.26 | Séquentiel — orchestration lore-mcp. |
| E12.27 | Progressive output — Docling n'écrit pas par phase. |
| E12.31 | Subprocess — toujours nécessaire pour VRAM. |
| E12.32 | Traces debug — diagnostic lore-mcp. |
| E12.35 | Judge prompt + keep-intermediates. |
| E12.37 | Whole-document enrichment — fonctionne. |

### Code à supprimer

- `caption_inline_images()` (~150 lignes)
- `caption_image()` (~60 lignes)
- `_vlm_api_call()` (~50 lignes)
- `_build_classify_prompt()` (~20 lignes)
- `_ocr_from_b64()` (~20 lignes)
- `_b64_hash()`, `_MIN_IMAGE_SIZE_B64`
- `_clean_vlm_output()` regex
- `_CLASSIFY_PROMPT_BASE`, `_CAPTION_PROMPTS`
- `_GENERIC_ALT`

Total : ~350 lignes supprimées, remplacées par
~20 lignes de configuration Docling.

### Code à garder (phase 2 multi-model)

- Multi-model loop (simplified)
- Judge selection (`judge_captions`)
- IS lifecycle (`start_service`, `stop_service`)
- Progressive output (`_write_phase`)
- VLM API call (réutilisé uniquement en phase 2
  pour les modèles additionnels)

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
