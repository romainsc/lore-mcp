# Rapport de validation MCP — sessions "tests mcp" + "tests de validation"

Dernière mise à jour : 2026-10-07

## Résumé

Deux sessions de validation exhaustive du pipeline lore-mcp via MCP.
- Session 1 (2026-10-06) : 24 bugs identifiés (E12.101-E12.123), 18 corrigés.
  5 tests PASS, 1 partiel.
- Session 2 (2026-10-06/07) : 5 bugs supplémentaires (E12.128-E12.133), tous corrigés.
  Re-run complet + nouveaux tests. 8 PASS, 1 partiel, 2 anomalies identifiées.

## Tests validés — session 2 (re-run 2026-10-07)

### E2.15 — Code narration sans enrichissement ✓
- add_source(store.py, enrich="none") → 79 chunks (vs 52 précédemment — code a grandi)
- search_docs score 0.845 sur "database connection SQLite"
- Narration AST, metadata correcte, enrich="none" OK
- Durée: 17s
- Collection: reval-nonenrich

### E2.14 — Project scan via add_directory ✓
- add_directory("src/lore_mcp", enrich="none", include_pattern="*.py")
- 28 fichiers, 926 chunks (vs 856 — code a grandi), 22 skippés (hash match)
- search_docs score 0.875
- Durée: 64s
- Collection: reval-dir

### E2.13 — MCP stability ✓
- search_docs sur full-recipe → score 0.91
- list_indexed_sources → 21 fichiers, 1505 chunks
- list_collections → 17 collections
- get_service_status → embedder loaded
- Serveur stable après tous les builds précédents
- **Requalifié PASS** (le partiel précédent venait d'un build sur collection neuve, corrigé par E12.122)

### E2.12 — Cancel task ✓
- add_source(PPTX) → cancel_task → annulation en ~68s
- Coopératif (subprocess Docling termine avant check)
- État propre — collection non créée après annulation
- Error: "Task cancelled" correctement reportée

### E2.11 — Code narration Python ✓
- 3 modules: server.py (224), store.py (162), embedder.py (75) = 461 chunks
- (vs 367 précédemment — code a grandi)
- Scores >0.85 (embedding GPU 0.85, MCP tools 0.87)
- Enrichissement context+qa+meta fonctionnel
- Durée: 261s (123+91+47)
- Collection: reval-code-py

### E2.16 — Scan + enrichissement code ✓ (NOUVEAU)
- add_directory("src/lore_mcp", enrich="context,qa,meta", include_pattern="*.py")
- 27 fichiers, 1316 chunks enrichis, 2 skippés (hash match), 0 erreurs
- search_docs: pipeline 0.88, MCP tools 0.87
- Durée: 716s (~12 min)
- Collection: reval-code-enriched

### E2.06 — Full pipeline via add_recipe ✓ (partiel)
- add_recipe(recipe-test-redist.yaml, collection="reval-full-recipe", force=true)
- **18/21 sources**, 2437 chunks, score 0.93
- 3 vidéos YouTube en erreur (STT timeout — voir anomalie A1)
- 18 sources non-vidéo : toutes OK
- PII détecté : emails publics (FSF, UN, FAO — attendu)
- Biblio générée (build-report.json)
- Durée: 8966s (~2h30)
- Collection: reval-full-recipe

### E2.07 — Full pipeline via add_sources ✓ (partiel, NOUVEAU)
- add_sources(JSON, orig_dir, collection="reval-add-sources")
- **18/21 sources**, 2378 chunks
- 3 vidéos YouTube "File not found" (fichiers non dans orig_dir)
- Chunk counts cohérents avec E2.06 (variations VLM non-déterministes)
- Durée: 4752s (~79 min, 2× plus rapide que add_recipe — phase 1 checkpointée)
- Collection: reval-add-sources

## Tests en cours — interrompus par crash GNOME

### E2.08 — Full pipeline via add_source unaire (INTERROMPU)
- 16/21 sources terminées avec succès
- Source 17 (pexels-photo-33121483.jpeg) **FAIL** : VLM granite-vision start timeout (300s)
- Source 18 (PPTX) lancée, tâche `10270fff`, statut inconnu (crash session)
- Sources restantes : 3 vidéos YouTube (non lancées)
- Résultats partiels (sources 1-16) :

| # | Source | Chunks | Durée | Statut |
|---|--------|--------|-------|--------|
| 1 | open-source-ai-definition.html | 17 | 61s | ✓ |
| 2 | l-osi-publie...-mais-pas-trop.html | 55 | 80s | ✓ |
| 3 | fsf-is-working...applications.html | 15 | 61s | ✓ |
| 4 | 2606.03019v1.html | 126 | 89s | ✓ |
| 5 | open-weights.html | 28 | 70s | ✓ |
| 6 | OECD-LEGAL-0449.html | 2 | 57s | ✓ |
| 7 | free-sw.en.html | 56 | 75s | ✓ |
| 8 | test-markdown-sample.md | 13 | 62s | ✓ |
| 9 | test-data-sample.csv | 3 | 56s | ✓ |
| 10 | worldcup.json | 49 | 62s | ✓ |
| 11 | 623da898-en.pdf | 71 | 299s | ✓ |
| 12 | governing_ai...report_en.pdf | 495 | 474s | ✓ |
| 13 | S-GEN-UNACT-2021-PDF-E.pdf | 1289 | 993s | ✓ |
| 14 | jl42g3kh0r9f9c6kj79lr2ft7mc4.docx | 16 | 782s | ✓ |
| 15 | aout-2026.xlsx | 16 | 252s | ✓ |
| 16 | DUDH_2008.png | 71 | 341s | ✓ |
| 17 | pexels-photo-33121483.jpeg | — | 513s | FAIL |
| 18 | PPTX (Parcoursup) | — | ? | INTERROMPU |
| 19-21 | Vidéos YouTube | — | — | Non lancées |

- Collection: reval-add-source-unary
- **À reprendre** : source 17 (pexels), source 18 (PPTX), sources 19-21 (vidéos)

## Tests non lancés

| Test | Durée estimée | Description |
|------|---------------|-------------|
| E2.09 | ~10h | Full pipeline via download (18 URL sources, no orig_dir) |
| E2.10 | ~10h | Full pipeline mixte (3 local + 18 downloaded) |

## Diarization — preprocess MP3

### Test v5 (session 2, avant fix E12.134)
- Task: fea98d7e
- **FAIL** — STT timeout 600s insuffisant pour 2h audio CPU
- E12.129 fonctionne : file_count=0, placeholder détecté
- Durée: 1600s (~27 min)

### Test v6 (après fix E12.134 + E12.135)
- preprocess_source(file="/tmp/Réunion suivi école sophie 6 octobre 2026.mp3",
  enrich="speaker_id", speakers="Christine (teacher, EN), Sonia (teacher, FR),
  Sarah (parent), Romain (parent)", force=true, keep_intermediates=true)
- Task: 6c32d357
- **PARTIEL** — STT réussi (E12.134 timeout proportionnel OK), diarization échouée
- STT: 1 fichier produit, 61 lignes, transcription complète 24 min de réunion
- Diarization: pyannote n'a PAS tourné (pas de phase1-diarize.md). Cause probable :
  exception silencieuse dans _diarize_pyannote (catch all → return []) sur 2h audio CPU.
  Test isolé pyannote sur 30s confirme que la lib fonctionne (23 turns détectés)
- Enrichment speaker_id: a tourné mais sans labels speakers → pas de changement
- Problème multilingue: STT Canary auto-détecte EN (Christine parle en premier),
  tout le français transcrit en anglais
- Durée: 923s (~15 min)
- Anomalies: A3 (diarization silencieuse), A4 (diarization gros fichier), A5 (STT multilingue)

### Test v7 (après fix E12.136 + E12.137 + E12.138)
- Mêmes paramètres que v6, collection test-diarize-v7
- Task: 018a4277
- **MÊME RÉSULTAT QUE V6** — STT réussi, diarization non exécutée
- Checkpoint: phase1→stt→phase3, pas de phase diarization
- 0 occurrences SPEAKER/diariz dans la sortie
- phase3-enrich identique à phase1-parse (21191 bytes)
- E12.136/137/138 implémentés mais le code diarization (ligne 932) n'est jamais atteint
- Durée: 914s (~15 min)
- Anomalies: A6 (diarization non exécutée malgré fixes)
- **Backlog** : E12.142 — investiguer pourquoi la diarization n'est pas atteinte

### Test v8 (après fix E12.141 + E12.142)
- Mêmes paramètres, collection test-diarize-v8
- Task: adab0ed7
- **FAIL** — 23s, file_count=0. Diarization toujours skippée
- E12.141 (skip_global_stt) fonctionne : pas de phase STT dans checkpoint
- Mais E12.129 (placeholder detection) met data["text"]=None
- Diarization ligne 937 `if not data.get("text"): continue` → source skippée
  car text est None. Le per-speaker STT n'a pas besoin de texte existant
- Phase 3 enrichment tourne sur rien → 0 fichiers
- **Backlog** : E12.143 — fix incomplet, retirer le check text pour audio/video+diarize

## Anomalies identifiées

### A1. STT timeout insuffisant pour audio long en CPU → E12.134
- **Symptôme** : transcription de fichiers audio longs (>30 min) échoue en mode CPU
- **Cause** : timeout STT config = 600s. Audio de 2h → ratio CPU ~0.5-1.5× = 3600-10800s nécessaires
- **Contexte** : en session 1 (E2.06 original 21/21), les vidéos YouTube n'utilisaient
  PAS le STT — yt-dlp téléchargeait les sous-titres auto-générés et le pipeline les
  utilisait directement (E12.73). En session 2, les fichiers pré-téléchargés dans
  orig_dir n'avaient pas les sous-titres à côté → fallback STT → timeout
- **Impact** : 3 vidéos YouTube (E2.06/E2.07/E2.08) + diarization MP3
- **Backlog** : E12.134 — timeout STT proportionnel à la durée audio

### A2. add_source arrête tous les services entre chaque appel → E12.135
- **Symptôme** : add_source(pexels.jpeg) échoue "Service not ready after 300s"
- **Cause racine** : `_add_source_task()` appelle `_cleanup_services()` dans son
  `finally`, qui fait `stop_all_services()` — un hard stop de TOUS les services.
  Cela court-circuite le lazy stop du ModelRegistry. De plus, le ModelRegistry
  n'est jamais câblé (`_task_manager.start()` appelé sans `models=` param)
- **Impact** : cycle stop/start à chaque add_source unaire. Si le start_timeout
  (300s) est insuffisant pour un cold start CPU → FAIL
- **Backlog** : E12.135 — add_source ne doit pas faire de cleanup des services,
  c'est le rôle du lazy stop. Retirer `_cleanup_services()` des chemins per-task

### A3. Diarization failure silencieuse → E12.136
- **Symptôme** : diarization ne tourne pas, aucune erreur dans le rapport
- **Cause** : `_diarize_pyannote()` (diarize.py:50-51) catch toutes les exceptions
  et retourne `[]`. L'appelant (preprocess/__init__.py:948) vérifie `if turns:` et
  skip silencieusement. Aucun warning dans le rapport de préprocessing
- **Impact** : diarization échoue sans que l'utilisateur le sache
- **Backlog** : E12.136 — surfacer l'erreur dans le rapport

### A4. Diarization sur audio long CPU → E12.137
- **Symptôme** : pyannote sur 2h d'audio CPU crashe ou prend trop longtemps
- **Preuve** : test isolé sur 30s fonctionne (23 turns), mais le pipeline
  complet sur 2h ne produit aucun turn (exception catchée silencieusement)
- **Backlog** : E12.137 — chunking audio ou GPU pour diarization

### A5. STT multilingue → E12.138
- **Symptôme** : réunion bilingue EN+FR transcrite entièrement en anglais
- **Cause** : Canary-1B-v2 auto-détecte la langue sur les premières secondes.
  Christine (EN) parle en premier → tout transcrit en EN. `lang=None` dans la requête
- **Backlog** : E12.138 — support code-switching ou langue par speaker

### A6. Diarization non exécutée malgré fixes E12.136-138 → E12.142
- **Symptôme** : test v7 (après implémentation E12.136/137/138) produit le même
  résultat que v6 — pas de diarization, pas de per-speaker STT
- **Preuve** : checkpoint phase1→stt→phase3 (pas de phase diarization), 0 SPEAKER
  dans la sortie, phase3-enrich=phase1-parse
- **Cause probable** : le code diarization (ligne 932 de __init__.py) n'est jamais
  atteint dans le flux d'exécution. Bug d'intégration des fixes E12.136-138
- **Backlog** : E12.142 — investiguer le chemin de code

### A7. STT global redondant avec per-speaker STT → E12.141
- **Symptôme** : le pipeline fait STT global (~10 min CPU) puis diarization+per-speaker STT
- **Cause** : phase 1.6 (STT global) est exécutée avant phase 1.5 (diarization)
  même quand diarization_model est configuré
- **Impact** : ~10-15 min CPU gaspillées par source audio
- **Backlog** : E12.141 — skip STT global quand diarization+per-speaker STT activé

## Bugs corrigés — session 2

| ID | Description | Impact |
|----|-------------|--------|
| E12.128 | preprocess_source service lifecycle | Corrige diarization v2 fail |
| E12.129 | STT placeholder detection → error | Plus de faux positif audio |
| E12.131 | speakers param sur MCP tools | Débloque diarization |
| E12.132 | keep_intermediates param sur tous les outils | Diagnostic possible |
| E12.133 | MCP schema truncation (faux positif, sections Advanced: supprimées) | Tous params visibles |

## Bugs corrigés — session 1

| ID | Description |
|----|-------------|
| E12.101 | Download vers build_dir (pas orig_dir) |
| E12.102 | Recipe orig_dir fallback |
| E12.103 | add_recipe collection override |
| E12.104 | YouTube video ID (pas "watch") |
| E12.105 | skip_optimize chunk params |
| E12.106 | add_recipe progress reporting |
| E12.107 | URL extension fallback + dotted basenames |
| E12.108 | Sources manquantes du rapport (phase 4) |
| E12.109 | Sources poor indexées par défaut |
| E12.110 | Evaluation balanced round-robin |
| E12.111 | cancel_task coopératif |
| E12.112 | TEI restart self-contained |
| E12.113 | MCP stdout isolation |
| E12.116 | FormatRegistry configs (yaml/toml/Containerfile) |
| E12.117 | CLI build auto-scan preprocess=True |
| E12.118 | enrich="none" désactive enrichissement |
| E12.121 | Config singleton isolation (copy.copy per task) |
| E12.122 | Guard _get_db against empty .db |
| E12.123 | Preprocess→ingest handoff robuste |

## Collections créées (workspace-validation/build/)

| Collection | Sources | Chunks | Test |
|-----------|---------|--------|------|
| reval-nonenrich | 1 | 79 | E2.15 |
| reval-dir | 28 | 926 | E2.14 |
| reval-code-py | 3 | 461 | E2.11 |
| reval-code-enriched | 27 | 1316 | E2.16 |
| reval-full-recipe | 18 | 2437 | E2.06 |
| reval-add-sources | 18 | 2378 | E2.07 |
| reval-add-source-unary | 16+ | ~2373+ | E2.08 (partiel) |
| full-recipe | 21 | 1505 | E2.06 session 1 |

## Plan de reprise

1. **Créer 2 backlog items** pour les anomalies A1 (STT timeout) et A2 (VLM start timeout)
2. **Reprendre E2.08** : relancer sources 17-21 (pexels + PPTX + 3 vidéos)
3. **Lancer E2.09** : full download (18 URL sources, --allow-download)
4. **Lancer E2.10** : mixed (3 local + 18 downloaded)
5. **Optionnel** : relancer diarization avec STT GPU ou timeout augmenté
