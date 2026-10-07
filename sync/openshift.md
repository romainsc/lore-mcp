# Sync lore-mcp → openshift

> Dernière MàJ : 2026-10-07 (sync 47)
> Source : sessions lore-mcp 3-7 oct
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

## Prochaines étapes

- E12.137 Long audio CPU diarization
- E12.138 Code-switching (consensus pipeline)
- E12.140 Intégration MOSS quand service disponible
- E12.124 Upstream contributions Docling (4 candidats)
- Sessions validation E2.07-E2.10
