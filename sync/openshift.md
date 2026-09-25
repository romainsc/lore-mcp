# Sync lore-mcp → openshift

> Dernière MàJ : 2026-09-25 (sync 41)
> Source : session lore-mcp 25 sept
> Ce fichier est maintenu par le dépôt lore-mcp.
> Il est lu par le dépôt openshift au `sync`.

## État du projet

### Statistiques

- 17 modules Python (dont preprocess/), ~120 tests
- Branche active : feat/E12-preprocessing-tool
- Release tag : v0.1.0-dev

### Backlog E12 — preprocessing (en cours)

**`Implémenté`** cette itération (24 sept) :
- E12.68 Démarrage différé du service embedding (après preprocessing)
- E12.69 Report écrit progressivement (après chaque source)
- E12.70 Cache STT séparé (.stt.json) — changement de frame strategy sans refaire la STT
- E12.67 Hash par phase câblé — changement de config → invalidation auto de phase 1
- E12.63 corrections : structure prep_base_dir/<collection>/, intermédiaires dans state dir, cascade invalidation, scan_directory audio/vidéo, extensions .md, feedback Ctrl+C
- E12.53/54/55 Stratégies frame extraction (interval, hybrid, OCR-guided) — déjà implémentées, backlog mis à jour
- E2.04 Tests checkpoint (41 tests : force, resume, cascade, per-source, per-image, state)
- E10.34 Étude RAG par type de corpus (verdict B : backends spécialisés chunking, orchestration unifiée)

**Itération précédente (22 sept)** :
- E12.44-50, E12.10, E12.33, E6.01, E5.13, E10.08, E2.03, E4.02, E5.05

**`À faire`** :
- E3.05 Tutorial GPU prerequisites
- E10.25 Per-model verify_ssl
- E10.28 Detailed eval report
- E10.31 Default models study
- E10.34 benchmarks (après étude)
- E12.52 correction libellé "video frames" vs "inline images"

### Résultats clés

**Nouveautés majeures** :

- **Audio/vidéo** (E12.48/49) : ingestion de
  fichiers audio (.opus, .mp3...) et vidéo
  (.webm, .mp4...) via service STT. Transcription
  markdown avec timestamps. Vidéo : frames
  extraites par ffmpeg (scene change) + base64
  inline. Corpus test : 1 audio + 2 vidéos (21
  sources total)
- **Pre-filtering** (E5.13) : filtrage avant KNN
  via rowid IN. Remplace le post-filter. source,
  level, license, title, author, date pré-filtrés
- **Sync déclaratif** (E6.01) : manifest = source
  de vérité. La DB est son reflet. Skip inchangés,
  re-ingest modifiés, purge absents
- **CI/CD** (E2.03) : GitHub Actions, pytest sur
  push/PR
- **pip install** (E4.02) : wheel construit et
  installable, version 0.1.0.dev1
- **Quantification** (E5.05) : étude complète.
  int8 ~99.5% recall (4×), bit ~95% (32×).
  Float32 suffit pour <50K chunks

### Contrat d'interface

Ajouts depuis sync 39 :
- `parse.video_frame_strategy` : scene/interval/ocr/hybrid
- `parse.video_frame_interval` : intervalle frames (défaut 30s)
- `parse.video_ocr_change_threshold` : seuil OCR (défaut 0.3)
- Structure sortie : `prep_base_dir/<collection>/` pour les fichiers finaux
- Intermédiaires dans `~/.local/state/lore-mcp/` par défaut
- Cache STT `.stt.json` : réutilisé entre runs
- Report progressif : écrit après chaque source
- Hash par phase : invalidation auto sur changement de config

## Retours IS captioning (2026-09-19, sync 36)

### granite-vision 507 — diagnostic précis

**Symptôme** : granite-vision retourne HTTP 507
sur DUDH (2480×3548) systématiquement dans le
pipeline lore-mcp, alors que le test IS isolé
fonctionne en 25s.

**VRAM au moment du start** : 150 MiB utilisés,
3670 MiB libres. Suffisant.

**Cause racine** : `GET /health` retourne OK
**avant** que le modèle soit prêt pour
l'inférence. Le serveur IS répond "healthy"
dès que uvicorn est up, mais le modèle est
encore en cours de chargement GPU. La première
requête d'inférence (DUDH, 70 patches) arrive
pendant le chargement → OOM.

**Preuve** (logs IS capturés par lore-mcp) :
le log se termine à "Loading weights: 100%" +
"Application startup complete" + warning
bitsandbytes. Pas de requête traitée avant le
507.

**Timing** :
- 17:43:38 : Service ready (/health OK)
- 17:43:41 : Caption failed 507 (3s après ready)

**Fixes demandés** :
1. `/health` ne doit retourner OK qu'après
   qu'une inférence de test ait réussi (pas
   juste uvicorn up)
2. Le script start doit vérifier la VRAM libre
   avant de lancer le modèle et avertir si
   marge < 1 Go (déjà mentionné sync IS E17.07)
3. Le script stop doit s'assurer que la VRAM
   GPU est libérée avant de retourner (podman
   stop est asynchrone pour la libération VRAM)

**Côté lore-mcp (corrigé, E12.31)** :
Phase 1 (Docling parse) tourne maintenant dans
un **subprocess**. À sa sortie, le contexte CUDA
PyTorch est entièrement libéré.

VRAM mesurée au moment du start granite-vision :
**22 MiB utilisés, 3798 MiB libres**. C'est la
VRAM au repos, totalement propre. Rien de plus
ne peut être libéré côté lore-mcp.

**Traces diagnostic détaillées (E12.32+34,
2026-09-19, --debug)** :

```
Lancement lore-mcp :         VRAM 22/3798 MiB
CUDA check (subprocess) :    VRAM 22/3798 MiB
Après phase 1 subprocess :   VRAM 22/3798 MiB
Avant start granite-vision : VRAM 22/3798 MiB
Image :                      2480x3548 RGBA
Après modèle chargé :        VRAM 2646/1174 MiB
Après classify (1ère req) :  VRAM 3588/232 MiB
507 sur caption (2ème req) : "GPU or VRAM shared"
Après stop :                 VRAM 22/3798 MiB
```

Côté consommateur, la VRAM est **totalement
propre** à 22 MiB (le minimum absolu) au moment
du start granite-vision. Le check CUDA se fait
dans un subprocess (zéro impact VRAM). La phase 1
Docling tourne aussi dans un subprocess.

**Le problème est dans le serveur IS** :
la 1ère requête (classify, prompt court) fait
passer la VRAM de 2646 à 3588 MiB (+942 MiB
d'activations). Ces activations ne sont pas
libérées entre les requêtes. La 2ème requête
(caption) trouve 232 MiB libres → OOM 507.

**Test après mise à jour IS (empty_cache)** :
le 507 persiste malgré l'ajout de
`torch.cuda.empty_cache()` côté IS.

Body 507 détaillé (améliorations IS visibles) :
```
Tried to allocate 74.00 MiB
GPU total: 3.73 GiB
Free: 51.94 MiB
Process uses: 3.65 GiB
PyTorch allocated: 3.45 GiB
PyTorch reserved but unallocated: 107.02 MiB
```

Le serveur a besoin de 74 MiB, 51.94 libres.
107 MiB sont "reserved but unallocated" —
`empty_cache` ne les a pas récupérés.
C'est de la **fragmentation mémoire GPU**.

PyTorch suggère `PYTORCH_CUDA_ALLOC_CONF=
expandable_segments:True` pour éviter la
fragmentation. Le fournisseur IS pourrait
ajouter cette variable d'environnement au
conteneur.

**Pattern d'appel lore-mcp** :
1. Probe health (image 1×1 pixel)
2. Classify (image 2480×3548 + prompt court)
3. Caption (image 2480×3548 + prompt long)
→ chaque appel alloue/libère des activations
  de tailles différentes → fragmentation.

### granite-docling — mésusage corrigé

granite-docling-258M n'est pas un modèle de
captioning. IBM : "only as part of the Docling
library", "not intended for general image
understanding". Retiré de `caption_models`.
Item E12.30 créé pour l'intégration via
Docling VlmPipeline en phase 1.

### molmo — fonctionne

molmo-7b captioning fonctionne sur DUDH (CPU,
~12 min). Le juge sélectionne correctement
l'OCR quand il est plus complet que le caption
Molmo.

## Demande IS — nouveaux services (sync 38)

### Bilan services IS existants

| Service | Modèle | Usage | Statut |
|---------|--------|-------|--------|
| granite-vision | granite-3.2-4b-vision | VLM captioning | ✓ opérationnel |
| molmo-7b | Molmo2-O-7B | VLM captioning | ✓ (timeout 600s nécessaire) |
| granite-8b | granite-3-2-8b-instruct | LLM enrichissement + juge | ✓ opérationnel (distant) |
| TEI nomic | nomic-embed-text-v2-moe | embedding | ✓ opérationnel |
| TEI granite | granite-embedding-311m | embedding | ✓ opérationnel |

### Service STT — retour d'expérience (E12.48)

**Modèle déployé** : Canary-1B-v2 (CC-BY-4.0,
Level 2). Faster-Whisper exclu (Level 4).

**Performance observée** : ~11 min pour 12 min
d'audio en CPU. Le démarrage conteneur ajoute
~75s. Cache STT (.stt.json) évite la
re-transcription au changement de stratégie frames.

**Projet serveur** : `faster-whisper-server`
(https://github.com/fedirz/faster-whisper-server)
— expose une API OpenAI-compatible.

**API attendue** :

```
POST /v1/audio/transcriptions
Content-Type: multipart/form-data

file: <audio file>
model: <model name>
language: fr (optional, ISO 639-1)
response_format: verbose_json
```

**Réponse attendue** :

```json
{
  "text": "transcription complète",
  "segments": [
    {"start": 0.0, "end": 5.2, "text": "segment"},
    ...
  ]
}
```

**Config lore-mcp** :

```yaml
llm:
  - name: whisper
    model: Systran/faster-whisper-large-v3
    api_url: http://127.0.0.1:8093/v1
    start: ./scripts/start-whisper-server.sh
    stop: podman stop whisper-server
    start_timeout: 120
    timeout: 600
```

**Priorité** : moyenne. Pas de consommateur
immédiat mais le câblage côté lore-mcp est prêt
(E12.48 groomé).

**GPU** : GPU recommandé pour la vitesse
(~4× realtime avec large-v3 sur GPU). CPU
possible mais lent (~0.5× realtime).

### Service futur : vidéo (E12.49)

Même service STT que E12.48. L'extraction de
frames est faite côté lore-mcp via ffmpeg (pas
un service IS). Les frames capturées sont
captionnées par le VLM existant (granite-vision
ou molmo).

Pas de nouveau service IS nécessaire pour la
vidéo — réutilise STT + VLM existants.

### Rappel demandes IS en attente (sync 36)

1. `/health` ne doit retourner OK qu'après une
   inférence de test réussie
2. Script start : vérifier VRAM libre avant
   lancement (marge < 1 Go = warning)
3. Script stop : s'assurer que VRAM GPU est
   libérée avant retour
4. `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`
   dans le conteneur (fragmentation mémoire GPU)

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
