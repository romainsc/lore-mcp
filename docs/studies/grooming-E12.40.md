# Grooming E12.40 — Title resolution cascade

- **Status:** À valider
- **Date:** 2026-09-20

## Problem

PPTX title is "w" (from core_properties.title).
The cascade actuelle :
1. Front matter title (contenu)
2. Premier heading (contenu)
3. Nom du fichier (fallback)

Manque : le titre du manifest (priorité max)
et les métadonnées du fichier source (PPTX
core_properties, PDF metadata).

Le `# w` reste dans le contenu markdown même
quand le manifest déclare un meilleur titre.

## Solution

### Cascade de résolution du titre

1. **Manifest** `title` field — priorité max,
   déclaré par l'utilisateur
2. **Métadonnées fichier** — core_properties
   (PPTX/DOCX), PDF metadata, etc. Extraites
   par Docling ou python-pptx/python-docx
3. **Contenu** — front matter YAML, premier
   heading du markdown
4. **Nom du fichier** — fallback (stem sans
   extension)

### Application au contenu

Quand le titre résolu (étape 1 ou 2) est
différent du premier heading dans le markdown :
remplacer le heading.

```python
if resolved_title != first_heading:
    text = text.replace(
        f"# {first_heading}",
        f"# {resolved_title}",
        1  # first occurrence only
    )
```

### Extraction métadonnées fichier

Pour PPTX/DOCX, les métadonnées sont
accessibles via python-pptx/python-docx
(déjà des dépendances de Docling). Mais
appeler ces librairies dans le processus main
peut réintroduire des imports lourds.

Alternative : Docling expose les métadonnées
du document via `doc.origin` ou
`doc.description`. Vérifier si c'est
disponible et suffisant.

### Impact sur le pipeline

- Le manifest `title` surcharge déjà les
  métadonnées dans `resolved` (existant)
- L'extraction métadonnées fichier s'ajoute
  comme étape 2 dans `extract_source_metadata`
- Le remplacement du heading se fait en phase 3
  (clean) ou après l'extraction du titre

## DoD

1. Cascade titre : manifest > métadonnées
   fichier > contenu > nom fichier
2. Premier heading markdown remplacé si titre
   résolu est différent
3. PPTX "# w" remplacé par le titre manifest
   ou le nom du fichier
4. Tests pass

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
