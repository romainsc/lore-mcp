# Design — Image captioning pipeline

- **Status:** Référence
- **Date:** 2026-09-18
- **Scope:** E12.16, E12.28, inline + standalone

## Principes fondamentaux

1. **OCR-first** : l'OCR (RapidOCR) est toujours
   exécuté en premier. Il fournit le texte fidèle
   sans hallucination.

2. **OCR enrichit le VLM** : le texte OCR est
   injecté dans les prompts du VLM (classify et
   caption) pour améliorer la qualité de la
   détection de type et de la description.

3. **Description unifiée** : le VLM produit UNE
   description qui positionne le texte dans son
   contexte visuel. Le VLM utilise le texte OCR
   comme référence et ajoute le texte que l'OCR
   a raté (stylisé, handwriting, BD). Le résultat
   est une narration cohérente, pas OCR + VLM
   concaténés.

4. **Le VLM ne commente pas l'OCR** : les prompts
   interdisent toute méta-commentary ("The OCR
   text captures...", "it's worth noting..."). Le
   post-traitement regex supprime les résidus.

5. **Alt text = contexte** : un alt text réel
   enrichit les prompts (classify + caption). Il
   n'est jamais un motif de skip.

6. **Multi-model** : tous les modèles configurés
   traitent toutes les images. Chaque modèle
   produit son propre résultat. Un juge LLM
   sélectionne ou fusionne.

7. **OCR = candidat du juge** : le texte OCR
   brut est un candidat au même titre que les
   captions VLM. Le juge peut le choisir si aucun
   VLM ne fait mieux.

## Flux par image

```
Image (fichier ou base64 inline)
│
├─ 1. OCR (RapidOCR, pleine résolution)
│     → texte fidèle, cached
│
├─ 2. Pour chaque modèle caption configuré :
│     │
│     ├─ 2a. Classify
│     │   Prompt : texte OCR + alt text (si réel)
│     │           + "What type: photo, chart,
│     │             diagram, table, screenshot,
│     │             scan, infographic, slide,
│     │             timeline, comic, or other."
│     │   → type détecté (1 mot)
│     │
│     ├─ 2b. Caption
│     │   Prompt : contexte source + alt text
│     │           + texte OCR (référence)
│     │           + type détecté
│     │           + prompt spécialisé par type
│     │           + "Use OCR text as reference.
│     │             Produce unified description.
│     │             Add text OCR missed.
│     │             Do NOT comment on OCR."
│     │   → description unifiée
│     │
│     ├─ 2c. Post-traitement
│     │   → _clean_vlm_output() (regex)
│     │
│     └─ 2d. Écriture progressive
│           → phase2-caption-{model-name}.md
│
├─ 3. Sélection (juge LLM)
│     Candidats : OCR brut + caption modèle 1
│                 + caption modèle 2 + ...
│     Le juge sélectionne par NOM (pas par
│     reproduction). Chaque candidat est présenté
│     avec un preview (2000 chars max). Le juge
│     retourne le nom du gagnant + justification.
│     Le texte complet du gagnant est récupéré
│     du dict. max_tokens = 200 (pas 1024).
│     → texte final = candidat sélectionné intact
│
└─ 4. → phase 3 (clean + enrich)

Note : granite-docling-258M n'est PAS un modèle
de captioning. C'est un convertisseur de pages
(DocTags) qui doit être utilisé via Docling
VlmPipeline en phase 1, pas en phase 2.
Voir E12.30.
```

## Prompts

### Classify prompt

Sans OCR :
```
What type of image is this? Answer with exactly
one word: photo, chart, diagram, table,
screenshot, scan, infographic, slide, timeline,
comic, or other.
```

Avec OCR :
```
OCR extracted this text from the image:
{ocr_text}

What type of image is this? Answer with exactly
one word: photo, chart, diagram, table,
screenshot, scan, infographic, slide, timeline,
comic, or other.
```

Avec alt text réel :
```
Original alt text: {alt_text}
OCR extracted this text from the image:
{ocr_text}

What type of image is this? ...
```

### Caption prompt

Sans OCR :
```
[Context from surrounding text: ...]
[Source description: ...]
{prompt spécialisé par type}
Write in English. Be factual and specific.
```

Avec OCR :
```
[Context from surrounding text: ...]
[Source description: ...]
[Original alt text: ...]
OCR extracted this text from the image:
---
{ocr_text}
---
Image type: {type}. {prompt spécialisé}
Use the OCR text as reference for printed text.
Produce a unified description that positions the
text in its visual context. Add any text the OCR
may have missed (stylized, handwritten, embedded
in graphics). Describe layout, colors,
highlighting.
Do NOT comment on the OCR quality or accuracy.
Do NOT produce meta-analysis. Only describe the
image.
Write in English. Be factual and specific.
```

### Prompts spécialisés par type

| Type | Prompt |
|------|--------|
| chart | Transcribe data: axes, series, values, units, title, legend |
| diagram | Components, connections, labels, relationships |
| table | Transcribe to markdown: headers, rows, cells |
| scan | Transcribe text, preserve structure and headings |
| screenshot | Application, UI elements, text, data displayed |
| infographic | Data, labels, categories, statistics, messages |
| slide | Headings, bullet points, highlighted elements, layout, colors |
| timeline | Milestones, dates, stages, sequence, relationships |
| comic | Each panel: characters, dialogue, actions, sequence |
| photo/other | Subject, scene, objects, text, information conveyed |

## Standalone vs inline

### Standalone (fichier image .png/.jpg)

- Phase 1 : Docling parse → OCR (peut produire
  du texte via RapidOCR interne)
- Phase 2 : le fichier image est envoyé au VLM
  via `caption_image()` → suit le flux ci-dessus
- L'OCR vient de la phase 1 (texte Docling)

### Inline (base64 dans le markdown)

- Phase 1 : Docling parse → markdown avec
  `![Image](data:image/...;base64,...)`
- Phase 2 : `caption_inline_images()` itère
  chaque image base64 → suit le flux ci-dessus
- L'OCR est fait sur le base64 décodé

### Différence clé

La même logique OCR→classify→caption s'applique.
La seule différence est la source de l'image
(fichier vs base64) et de l'OCR (Docling vs
RapidOCR direct).

## Résilience

- Skip images < 10KB (icônes, logos)
- Content-hash dedup (même image N fois = 1 appel)
- Circuit breaker : 5 échecs consécutifs → stop
- Per-image try/except : pipeline ne crash jamais
- Fallback : VLM échoue → OCR seul comme candidat
- Pas de resize : l'image est envoyée telle
  quelle. Si un modèle ne supporte pas la
  résolution, c'est un problème de configuration
  IS, pas de lore-mcp

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
