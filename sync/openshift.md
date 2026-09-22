# Sync lore-mcp → openshift

> Dernière MàJ : 2026-09-22 (sync 39)
> Source : session lore-mcp 22 sept (soir)
> Ce fichier est maintenu par le dépôt lore-mcp.
> Il est lu par le dépôt openshift au `sync`.

## État du projet

### Statistiques

- 17 modules Python (dont preprocess/), 427 tests
- Branche active : feat/E12-preprocessing-tool
- Release tag : v0.1.0-dev

### Backlog E12 — preprocessing (en cours)

**`Implémenté`** cette itération (22 sept) :
- E12.44 Timeout configurable par modèle
- E12.45 Fallback photo standalone via VLM direct
- E12.47 Signatures minimales (3+5 params)
- E12.48 Audio ingestion (STT API)
- E12.49 Video ingestion (ffmpeg + STT)
- E12.50 Format detection via mimetypes
- E12.10 Pipeline steps autonomes (config)
- E12.33 Tests phase1 worker
- E6.01 Sync déclaratif DB ↔ manifest
- E5.13 Pre-filtering (rowid IN avant KNN)
- E10.08 Auto-configure embedding model from .db
- E2.03 CI/CD GitHub Actions
- E4.02 pip installable (wheel)
- E5.05 Étude quantification (int8/bit)

**Fermés/absorbés** :
- E12.46, E12.13, E10.33, E10.05 (shelved/absorbés)
- E12.24, E12.28, E7.01-03 (fermés/reportés)

**`À faire`** :
- E3.05 Tutorial GPU prerequisites
- E4.03 Docker image
- E6.07 Lint improvements
- E10.25 Per-model verify_ssl
- E10.28 Detailed eval report
- E10.31 Default models study

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

Ajouts depuis sync 38 :
- `parse.stt_model` : modèle STT du registre LLM
- `parse.video_scene_threshold` : seuil ffmpeg
  (défaut 0.3)
- Pre-filtering natif sur tous les filtres
  (source_file, level, license, title, author, date)
- Sync déclaratif : manifest pilote la DB
  (skip/update/add/purge automatique)

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

### Nouveau service demandé : STT (E12.48)

**Besoin** : transcription audio → texte pour
indexation RAG de réunions, podcasts, émissions.

**Modèle recommandé** : Faster-Whisper large-v3
(MIT, Level 1, 99+ langues, ~7.5% WER).

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
