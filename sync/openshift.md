# Sync lore-mcp → openshift

> Dernière MàJ : 2026-09-08 (sync 34)
> Source : session lore-mcp
> Ce fichier est maintenu par le dépôt lore-mcp.
> Il est lu par le dépôt openshift au `sync`.

## État du projet

### Statistiques

- 15 modules Python (dont preprocess/), 323 tests
- 9 EPUBs (architecture, code-guide,
  implementation-reference, configuration,
  tutorial, ADRs, ai-guidelines, research,
  quality observations)
- Release tag : v0.1.0-dev

### Backlog par statut

**`Revue`** (27 items) : E0.01-09, E1.01-04,
E2.01-02, E3.01-03, E4.01, E9.01-05

**`Implémenté`** (29 items, en attente validation) :
E6.04-05, E10.01-04, E10.06-07, E10.09-21, E10.23,
E10.24-28, E11.01

**`Implémenté`** : E3.06

**`En cours`** : E12.02 (preprocessing tool MVP1)

**`À faire`** (35 items) :
E2.03, E3.04-05, E4.02-04, E5.01-08, E6.01-03,
E6.06-08, E6.10, E7.01-03, E10.05, E10.08, E10.22,
E12.01-10

### Contrat d'interface

**MCP tools :**
- `search_docs(query, top_k=5, collection="")` —
  recherche sémantique (cross-corpus ou ciblée)
- `list_indexed_sources(collection="")` — fichiers
  indexés avec comptage
- `list_collections()` — collections disponibles

**CLI subcommands :**
- `lore-mcp` — serveur MCP (stdio ou `--transport sse`)
- `lore-mcp preprocess manifest.yaml --orig-dir ... --output-dir ...` — preprocessing sources
- `lore-mcp lint manifest.yaml --docs-dir ...` — analyse qualité
- `lore-mcp eval --db ... --config ...` — évaluation RAG
- `lore-mcp optimize --config ... --source-dir ...` — optimisation
- `lore-mcp build manifest.yaml --config ... --docs-dir ... --output-dir ...` — build complet

**Variables d'environnement :**
- `LORE_DB_PATH` : fichier .db (mono-collection)
- `LORE_DB_DIR` : répertoire de .db (multi-collection)
- `LORE_MODEL` : modèle d'embedding (défaut: nomic-embed-text-v2-moe)
- `LORE_EMBED_MODE` : `builtin` (défaut), `builtin:gpu`, `builtin:cpu`, `api`
- `LORE_API_URL` : endpoint /v1/embeddings
- `LORE_API_MODEL` : nom modèle côté API
- `LORE_API_VERIFY` : vérification SSL (true/false)
- `LORE_API_CA_BUNDLE` : chemin CA
- `LORE_CHUNK_SIZE` : taille chunk (défaut: 1024)
- `LORE_CHUNK_OVERLAP` : overlap (défaut: 128)
- `LORE_BATCH_SIZE` : taille batch embedding (défaut: 64)
- `LORE_LLM_URL` : endpoint juge LLM (pour RAGAS)
- `LORE_LLM_MODEL` : modèle juge (défaut: granite-8b-instruct)

**Config YAML** (clé `embedding:`, pas `models:`) :
```yaml
embedding:
  - name: nomic-ai/nomic-embed-text-v2-moe
    mode: builtin
judge:
  model: granite-8b-instruct
  api_url: http://localhost:11434/v1
metrics: [score_spread, source_diversity, mrr]
optimize:
  chunk_sizes: [512, 1024, 2048]
  chunk_overlaps: [64, 128]
  top_ks: [3, 5, 10]
  num_questions: 50
```

**Transport :** stdio (subprocess) ou SSE (HTTP)

**Manifest YAML** (point d'entrée unique) :

Le manifest est le fichier central du workflow
lore-mcp. Il déclare les sources de façon
abstraite (pas de chemins locaux). lore-mcp ne
modifie jamais le manifest — il produit une copie
enrichie (suffixe `-prep`).

**CHANGEMENT sync 33** : format manifest v2.
Les manifests existants doivent être mis à jour.

Manifest auteur (read-only, jamais modifié) :
```yaml
# manifest.yaml — les sources sont identifiées
# par leurs métadonnées, pas par des chemins
collection: openshift-libre
level: libre

sources:
  # Identité = metadata. orig/path = opérationnel
  - title: Architecture Guide
    license: Apache-2.0
    url: https://docs.example.com/arch.pdf
    orig: architecture.pdf       # fichier local (optionnel si url)

  - title: Project Guide
    author: RC
    orig: guide-v2.html          # format natif
    path: guide.md               # renommage en sortie (optionnel)

  - url: https://docs.example.com/spec.pdf
    # orig et path générés automatiquement

  - title: Release Notes
    orig: notes.md               # déjà markdown (nettoyage seul)
```

Manifest enrichi (généré par `preprocess`) :
```yaml
# manifest-prep.yaml — généré, ne pas éditer
collection: openshift-libre
level: libre

sources:
  - title: Architecture Guide     # extrait du doc
    license: Apache-2.0
    url: https://docs.example.com/arch.pdf
    orig: architecture.pdf
    path: architecture.md         # généré

  - title: Project Guide          # extrait du doc
    author: RC
    orig: guide-v2.html
    path: guide.md                # explicite
```

**Cascade de résolution des champs :**

| Champ | Si absent | Source |
|-------|-----------|--------|
| `orig` | Basename de `url` | Manifest ou URL |
| `path` | Basename de `orig` + `.md` | Généré |
| `title` | Front matter ou 1er heading | Extrait du document |
| `author` | Front matter | Extrait du document |
| `license` | Front matter | Extrait du document |
| `date` | Front matter | Extrait du document |

Ni `orig` ni `url` → erreur.
Champs biblio : Dublin Core (ISO 15836).
Licences : identifiants SPDX.

**CLI et répertoires :**

```bash
# 1. Preprocess : convertir + nettoyer
lore-mcp preprocess manifest.yaml \
  --docs-base-dir /corpus/ \
  --orig-subdir raw/ \          # facultatif, défaut: .
  --prep-subdir clean/ \        # facultatif, défaut: .
  --manifest-out manifest-prep.yaml  # facultatif

# Chemins résolus :
#   orig: /corpus/raw/architecture.pdf
#   prep: /corpus/clean/architecture.md

# 2. Lint (sur les fichiers préprocessés)
lore-mcp lint manifest-prep.yaml \
  --docs-dir /corpus/clean/

# 3. Build (même manifest enrichi)
lore-mcp build manifest-prep.yaml \
  --docs-dir /corpus/clean/ \
  --output-dir /db/
```

**Formats orig supportés** (E12.03, à venir) :
- `.md` : passthrough (nettoyage seul)
- `.pdf`, `.docx` : Docling (MIT, 97.9%)
- `.html` : trafilatura (Apache 2.0, F1 0.966)
- Tier 3 : LLM pour documents complexes (opt-in)

**Standards :**
- Biblio : Dublin Core (ISO 15836)
- Licences : SPDX
- Format : YAML custom (aucun standard RAG ne
  couvre listing + biblio + preprocessing + build
  — vérifié : DCAT, BagIt, DataCite, LlamaIndex,
  LangChain, Haystack, Docling)

**Action consommateur** : mettre à jour les
manifests existants vers le format v2. Remplacer
les métadonnées (title, url, license, author)
comme identité de la source. `orig` et `path`
sont des détails opérationnels (générés si
absents), pas l'identité de la source

### Fonctionnalités clés

- Multi-collection (`LORE_DB_DIR`, nommage
  `<theme>-<level>.db`)
- Métadonnées biblio (table sources, manifeste
  YAML, .json/.bib/.md en sortie)
- AutoRAG multi-modèle (`--config` avec
  plusieurs modèles d'embedding)
- Évaluation 3 niveaux (embedding, retrieval, LLM)
- Build workflow complet (manifest → optimized
  .db + metadata + report)
- Résilience API (retry backoff, batch reduction,
  fail fast)
- `Embedder.unload()` avec gc.collect()
- RAGAS 0.4.3 stub (langchain-community sunset)
- Modèle par défaut : Nomic v2 MoE (Level 2,
  Apache 2.0). ADR-005.

## Historique des demandes

Toutes les demandes reçues ont été traitées en
items de backlog conformément aux règles
cross-workspace. Statuts actuels visibles dans
la section backlog ci-dessus.

### RAGAS scoring (sync 25-26)
**E10.15 corrigé** — evaluate_retrieval appelle
_score_with_ragas quand métriques RAGAS demandées
+ juge configuré. compute_retrieval_metrics
remplace _score_retrieval (ajoute mrr).
Régression --config corrigée (E10.21).
214 tests.

### Wiring audit fix (sync 28)
6 items corrigés — fonctions mortes câblées :
- E10.19: check_ragas_guard appelé dans run_eval
- E10.20: ProgressReporter instancié dans run_optimize
- E10.09: compute_embedding_metrics résultat stocké
- E10.14: metrics/judge passés à evaluate_retrieval
- E10.18: ConsecutiveErrorThreshold utilisé dans ingest
- E10.13: defaults utilisés en skip-optimize
220 tests (6 tests d'intégration pipeline ajoutés).

### RAGAS API fix + fail fast (sync 29)
E10.15 — trois corrections RAGAS 0.4.3 :
- `score(**kwargs)` au lieu de `single_turn_score()`
  (API changée en 0.4.3)
- `AsyncOpenAI` au lieu de `OpenAI` (score()
  appelle ascore() en interne)
- `_RagasEmbeddingsWrapper` : encapsule notre
  `Embedder` pour `AnswerCorrectness` (similarité
  sémantique, poids 25%)
- Fail fast : `_probe_judge()` vérifie la
  connectivité du juge avant le build (évite 36×
  warnings silencieux)
- `verify_ssl` câblé dans toute la chaîne RAGAS
  (juge en HTTPS auto-signé)
- `check_ragas_guard` ajouté dans `run_optimize`
  (était seulement dans `run_eval`)

### Output management wiring (sync 29)
E10.24 — output_level câblé de bout en bout :
- `configure_logging` ne détruit plus le format
  Rich (supprimé `basicConfig(force=True)`)
- output_level transmis : CLI → server → build
  → optimize → ProgressReporter
- 3 modes distincts :
  - `--progress` : ligne `\r` avec %, temps, ETA
  - default : en-tête boxé, table finale avec ★
  - `--verbose` : questions en tableau markdown,
    résultats par requête (question, réponse,
    sources, scores), milestones temps réel
- `--num-questions` CLI prévaut sur le config
- E10.25 créé : verify_ssl par modèle d'embedding
- E10.26 créé : filtrage qualité questions extractives

### Tutorial TEI Podman (sync 29)
Réponse aux avertissements sync 14 (TEI local
GPU, CUDA 13 incompatible) et info sync IS
embedding Podman local :
- Section "GPU prerequisites" ajoutée (nvidia-
  container-toolkit, CDI, choix du tag par arch)
- Commandes corrigées : `--device
  nvidia.com/gpu=all`, `--security-opt=label=
  disable`, volume cache HF, `127.0.0.1`
- Tag par architecture GPU (sm_89 → 89-latest,
  sm_120 → 120-1.9.3)
- Multi-modèle simultané documenté
- Note CUDA 13.x incompatibilité
245 tests.

### Heading-based eval + report (sync 30)
E10.27 — questions d'évaluation générées depuis
les headings des documents sources (avant
chunking). Élimine le biais de chunking.
NDCG@5 + Recall@5. Métriques IR standard.

E10.28 — rapport markdown détaillé (`--report`).
Questions intégrales, chapitres par modèle,
tableau de scores + blockquote réponses, agrégats
min/avg/max, appendice méthodologie. Images
strippées (regex, alt-text préservé, gère les
crochets imbriqués).

E10.25 — `verify_ssl: false` par modèle
d'embedding dans le config YAML.

### Preprocessing + qualité (sync 30)
- `preprocess()` : regex `![alt](src)` → alt-text
  (remplace le filtrage ligne par ligne de base64)
- Questions issues du manifest uniquement (plus
  de rglob sur tout docs_dir)
- `#` strippés des headings (meilleure similarité
  cosine mesurée : 0.69 vs 0.61 avec `##`)
- Hook pre-commit : bloque commits directs sur
  main (`.githooks/pre-commit`, versionné)

### Nouveaux items (sync 30)
- E6.06 [E] Multi-format ingestion (PDF, HTML,
  DOCX, EPUB)
- E6.07 [E] Analyse qualité sources (lint md)
- E6.02 élargi : étude markdown_hero, chunkana,
  rag-chunk
278 tests.

### Preprocessing guide — Platform enabling (sync 31)
E3.06 [D] en cours — guide de preprocessing pour
préparer les sources markdown avant indexation RAG.
Documentation self-service pour les consommateurs
Platform (AI Serving, Veille).

Contenu : impact mesuré du preprocessing (~60%
qualité RAG vs ~15% modèle), headings comme signal
structurel (strip `#` des queries, 0.69 vs 0.61
cosine), gestion images (alt-text préservé, base64
strippé), détection bruit (séquences numériques,
contenu trivial), checklist qualité texte, pièges
courants (slides, OCR, HTML résiduel).

Livrable : `docs/preprocessing.md`, cross-référencé
depuis architecture et tutorial.

### Réception E14.17 — preprocessing RAG (sync 31)
Étude Veille E14.17 reçue et intégrée. Impacts :

**Validations :**
- Pipeline lore-mcp (recursive chunking + heading
  path + embedding + sqlite-vec) = pipeline minimal
  recommandé ✓
- Recursive chunking > semantic chunking (69% vs
  54%, FloTorch 2026) ✓
- Plage 512-1024 tokens validée (context cliff
  >~2500 tokens) ✓
- Multi-collection validée ("3 targeted stores >
  1 noisy store") ✓
- Overlap comme hyperparamètre → `lore-mcp
  optimize` est l'approche correcte ✓

**Scope confirmé :** lore-mcp = étapes 4-6 (split,
enrich, index). Étapes 1-3 (parse, clean, dedup)
= upstream (consommateur).

**BGE-m3 = level 4** (training data non publiée).
Déjà traité : migration vers Nomic v2 MoE
(level 2, Apache 2.0) effective (ADR-005).

**Priorités backlog ajustées :**
- E5.03 hybrid search FTS5+vec → priorité haute
  (+13pts recall@10 mesuré)
- Reranking cross-encoder → nouvel item à créer
  (+5-15pts nDCG@10)
- Adjacent-chunk retrieval → nouvel item à créer

**Hors scope lore-mcp :** enrichissements LLM
(contextual retrieval, Q&A mode, proposition
indexing) → faisables via Claude en amont, pas
de code lore-mcp nécessaire.

**E3.06** enrichi : l'étude E14.17 fournit les
données sourcées pour le guide preprocessing.

### E3.06 terminé + E12 preprocessing tool (sync 32)

**E3.06 `Implémenté`** — guide preprocessing
complet (`docs/preprocessing.md`, 7 sections) :
best practices, techniques upstream (contextual
retrieval, Q&A mode, déduplication), données
E14.17 intégrées avec attribution.

**E12 — Preprocessing tool** (epic, 10 items) :
CLI `lore-mcp preprocess` implémentant les étapes
1-3 du pipeline RAG (parse, clean, dedup).
Module `src/lore_mcp/preprocess/` (séparable).

**MVP1 implémenté** (E12.02) :
- `clean_text()` : NFC, HTML strip, NUL, image→
  alt text, strip `#` des headings (préserve
  code blocks)
- CLI : `lore-mcp preprocess manifest.yaml
  --orig-dir /raw/ --output-dir /clean/`
- 308 tests.

**Manifest enrichi** (changement contrat) :
- Nouveau champ `orig` par source : nom du
  fichier original dans `--orig-dir`
- Nouveau champ `url` par source : URL pour
  fetch (placeholder, pas encore implémenté)
- Un seul manifest pour preprocess → lint → build
- Champs biblio alignés Dublin Core (ISO 15836)
- Licences au format SPDX
- Voir section "Manifest YAML" dans le contrat
  d'interface ci-dessus pour le format complet

**CLI unifiée** : `--docs-base-dir` renommé en
`--docs-dir` partout (lint, build, optimize,
preprocess). Pas de backward compat avant v1.

**Nouveaux items backlog** (E14.17) :
- E5.06-08 : reranking, adjacent-chunk retrieval
- E5.03 priorisé (hybrid search, +13pts)
- E6.08 : parent-child chunking (+15-25%)
- E6.10 : per-source chunking params
- E12.01-10 : epic preprocessing tool complet

### Manifest v2 — format source-first (sync 33)

**Changement de contrat** : le format manifest
passe en v2. Les manifests existants doivent être
mis à jour.

**Avant (v1)** : `path` (chemin fichier markdown)
était le seul identifiant. Problème : ce fichier
n'existe pas avant le preprocessing.

**Après (v2)** : une source est identifiée par
ses métadonnées (title, url, license, author).
`orig` (fichier natif) et `path` (fichier .md
de sortie) sont des champs opérationnels,
générés automatiquement si absents.

**Principes :**
- Le manifest ne contient pas de chemins locaux —
  les entrées sont abstraites
- lore-mcp ne modifie jamais le manifest —
  il produit une copie enrichie (`-prep` suffixe)
- Les champs biblio (title, author, license)
  sont extraits du document après conversion
- `--docs-base-dir` + `--orig-subdir` +
  `--prep-subdir` remplacent `--orig-dir` +
  `--output-dir`

**Migration manifests existants** : remplacer
`path: doc.md` par `orig: doc.md` (si le source
est déjà en markdown). Supprimer les champs
biblio redondants avec le front matter (ils
seront extraits automatiquement).

Voir contrat d'interface ci-dessus pour le
format complet et les exemples.

### Manifest v2 implémenté (sync 34)

Le format manifest v2 (sync 33) est maintenant
**implémenté et documenté** de bout en bout.

**Code :**
- `manifest.py:resolve_source_fields()` :
  cascade orig→path→title implémentée
- `preprocess/__init__.py:preprocess_sources()` :
  pipeline complet avec extraction metadata et
  sortie manifest enrichi (`-prep` suffixe)
- CLI v2 : `--docs-base-dir`, `--orig-subdir`,
  `--prep-subdir`, `--manifest-out`
- 323 tests (12 cascade + 32 preprocess + existants)

**Docs alignées** (toutes en v2, plus de v1) :
- `docs/configuration.md` : référence manifest
  complète (champs, cascade, enriched manifest)
- `docs/architecture.md` : design manifest-driven
- `docs/tutorial.md` : workflow preprocess→build
- `docs/preprocessing.md` : best practices

**Le consommateur peut maintenant** :
1. Écrire un manifest v2 (déclarer les sources
   par leurs métadonnées, `orig`/`path` optionnels)
2. Exécuter `lore-mcp preprocess` pour convertir
   et nettoyer les sources
3. Utiliser le manifest enrichi (`-prep`) pour
   `lint` et `build`

**Formats orig supportés actuellement** :
`.md` uniquement (passthrough + nettoyage).
Les formats PDF/HTML/DOCX arrivent avec E12.03
(Docling + trafilatura, après étude E6.06).

**Standards :** champs biblio Dublin Core
(ISO 15836), licences SPDX, format YAML custom
(aucun standard RAG ne couvre ce cas d'usage)
