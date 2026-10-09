# Sync lore-mcp → openshift

> Dernière MàJ : 2026-10-09 (sync 48)
> Source : sessions lore-mcp 3-9 oct
> Ce fichier est maintenu par le dépôt lore-mcp.
> Il est lu par le dépôt openshift au `sync`.

## État du projet

### Statistiques

- 19 modules Python (dont preprocess/), 713 tests
- Branche active : feat/E12-preprocessing-tool
- Release tag : v0.1.0
- 22 outils MCP (add_source, add_sources, add_recipe,
  add_directory, remove_source, search_docs,
  list_indexed_sources, list_collections,
  preprocess_source, preprocess_sources_tool,
  preprocess_directory, start_eval, start_optimize,
  get_service_status, get_version, get_config,
  lint_source, list_tasks, get_task_status,
  cancel_task, list_pipeline_state,
  purge_pipeline_state)

### Implémenté cette itération (3-7 oct)

**Refactoring architecture** :
- E1.05 MVP2-4 : ChunkStore, Evaluator, Parser classes
  (90 fonctions encapsulées, SQL/DB isolé)
- E3.29 source_id comme PK (cascade DOI/ISBN/URL/file,
  migration auto)
- E12.67 Phase hash 2/3 (captioning + enrichment)

**MCP tools** :
- E3.43 Preprocess-only tools (preprocess_source,
  preprocess_sources_tool, preprocess_directory)
- E12.127 Params passthrough (dict `params` dans
  LLM registry → API, STT/LLM/VLM)
- E12.131 speakers param + E12.132 keep_intermediates

**Audio/Diarization** :
- E12.125 Speaker diarization (pyannote + diarize,
  dual backend, LLM speaker_id)
- E12.134 Subtitle detection + timeout proportionnel
- E12.135 Lazy stop (cleanup_services retiré des tasks)
- E12.136 Diarization error surfacing

**Bug fixes** : E12.122 guard _get_db, E12.123
preprocess→ingest handoff, E12.126 cleanup
intermediates, E12.128-E12.129 preprocess service
lifecycle + STT placeholder detection

### Évaluation MOSS-Transcribe-Diarize (E12.139)

Modèle Apache 2.0, Level 2, 0.9B params.
Single-pass transcription + diarization + timestamps.
50+ langues, 1er INTERSPEECH 2026.

**Résultats** :
- FR transcription correcte, 3 speakers détectés
- CPU RTF ~1x (viable pour audio <30 min)
- GPU OOM sur RTX 500 4GB (nécessite >8 GB VRAM)

**Verdict** : GO pour intégration comme option
complémentaire (pas remplacement).

## Demande à IA Serving

### NOUVEAU — Service MOSS-Transcribe-Diarize

**Besoin** : servir MOSS-Transcribe-Diarize 0.9B
comme service d'inférence API (conteneur), au
même titre que TEI, Canary STT, Granite Vision.

**Modèle** : OpenMOSS-Team/MOSS-Transcribe-Diarize
- Apache 2.0, Level 2, ungated, 0.9 GB
- Nécessite : transformers, torch, moss-transcribe-diarize
- VRAM : ~2 GB (bf16), GPU >8 GB pour audio >5 min
- API : custom (build_transcription_messages +
  generate_transcription), pas OpenAI-compatible

**Utilisation** : lore-mcp appelle le service pour
transcription + diarization en un pass. Remplace
le pipeline multi-étapes (Canary + pyannote) pour
les cas multi-speakers.

**Priorité** : moyenne — le pipeline multi-étapes
fonctionne, MOSS est une optimisation.

**Question** : quel framework de serving pour un
modèle transformers custom ? vLLM ? TGI ? Wrapper
FastAPI ?

### PR Docling #4392

Toujours en attente merge (reviewer IBM).
Workaround local RGBA en place.

### Implémenté cette itération (8-9 oct)

**Diarization quality chain** (E12.148-E12.152) :
- E12.148 ffmpeg filter labels contigus
- E12.149 Service start fail fast
- E12.150 reconstruct_timeline proportionnel
- E12.151 Texte propre + word boundaries +
  title=None pour per-speaker STT
- E12.152 Merge turns adjacents + auto-detect
  lang per speaker

## Transfert d'étude — Diarization reconstruction

### Contexte

Étude study-E12.153-diarization-reconstruction.md
réalisée dans lore-mcp. Devrait être traitée dans
openshift (étude Veille).

### Recherche effectuée

7 itérations, 3 sèches consécutives. 6 sources
primaires (pyannoteAI, WhisperX INTERSPEECH 2023,
Vast.ai, Fora Soft, NVIDIA NeMo, DISPLACE 2024).

### Résultats clés

**Architecture validée** : per-speaker STT est le
consensus pour multilingue. L'architecture
lore-mcp est correcte.

**3 bugs d'implémentation identifiés** :
1. Canary ne fait PAS d'auto-détection de langue
   — `source_lang` obligatoire, défaut EN
2. Reconstruction devrait utiliser les timestamps
   STT + seg_table (rel→abs), pas proportionnel
3. `_extract_stt_segments` détruit les timestamps
   réels (crée `end = start + 10.0`)

**6 concepts émergents à évaluer** :
1. SpeechBrain VoxLingua107 (Apache 2.0, 93.3%,
   107 langues) — détection langue pré-STT
2. Hungarian Algorithm — mapping optimal
   speaker→nom (scipy, BSD)
3. Crossfade entre segments concaténés (ffmpeg)
4. ±250ms tolérance alignement turn boundaries
5. Canary-Qwen 2.5B — modèle plus récent
6. Joint models (MOSS-TD, Sortformer) — bypass
   reconciliation

### Demande

Évaluer dans openshift/Veille :
- SpeechBrain VoxLingua107 : niveau (Level 1-2?),
  bench CPU latency, accuracy FR vs EN
- Canary-Qwen 2.5B : niveau, licence, bench FR
- Hungarian Algorithm vs LLM pour speaker mapping
- Crossfade impact sur qualité STT

Étude source : `docs/studies/study-E12.153-diarization-reconstruction.md`
dans le repo lore-mcp branche feat/E12-preprocessing-tool.

## Prochaines étapes

- E12.153 Reconstruction par timestamps (dépend
  de l'étude ci-dessus)
- E12.140 Intégration MOSS quand service disponible
- E12.124 Upstream contributions Docling (4 candidats)
- Sessions validation E2.07-E2.10
