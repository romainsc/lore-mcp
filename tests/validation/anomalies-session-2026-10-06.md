# Anomalies remontées — session validation 2026-10-06

Post-fix E12.121 (copy.copy + collection lock).
Tests lancés dans une session Claude distincte
(serveur MCP redémarré).

## E12.122 — _get_db crée un .db vide (NOUVEAU)

**Source** : E2.13 validation (MCP stability)
**Symptôme** : "no such table: chunks"
**Cause** : `_get_db` (server.py:59) fait
`open_db(db_path)` même si le fichier n'existe
pas. `sqlite3.connect` crée un fichier vide
(aucune table). Toute requête crash.
**Impact** : `search_docs`, `list_indexed_sources`
sur une collection non indexée.
**Statut** : item créé, grooming écrit
(`docs/studies/grooming-E12.122.md`).
**Action** : valider grooming → implémenter.
Fix : `_get_db` lève `FileNotFoundError` si le
`.db` n'existe pas, callers attrapent et
retournent message clair.

## E2.14 — add_directory "File not found" (28/28)

**Source** : validation E2.14 (project scan)
**Symptôme** : 28 fichiers scannés par
`add_directory`, tous "File not found" en phase 1.
**Analyse code post-fix** : la chaîne de
propagation de `orig_dir` semble correcte :
- `add_directory` → `add_sources(orig_dir=str(dir_path))`
- `_do_adds` → `_orig = str(Path(orig_dir).resolve())`
- recipe YAML contient `orig_dir: <abs_path>`
- `prep_cfg.orig_dir = _orig`
- `preprocess_sources` → `_phase1_worker(str(_orig_dir))`
- `_phase1_worker` → `_orig_dir = Path(orig_dir).resolve()`
- Vérification : `(_orig_dir / orig_name).exists()`

**Aucun bug trouvé dans le code**. Causes
possibles à investiguer :
1. Le package pip n'a pas été réinstallé après
   le commit (le code en mémoire est l'ancien)
2. Le `directory` passé par le LLM à
   `add_directory` est un chemin relatif qui
   se résout différemment selon le cwd du
   serveur MCP
3. Bug dans le decorator `@mcp.tool()` qui
   altère les arguments lors d'un appel interne
   (`add_directory` appelle `add_sources`
   directement en Python)

**Action session validation** :
1. Reproduire avec `add_directory` via MCP
2. Noter la commande exacte et le `directory`
   passé
3. Récupérer le `get_task_status(task_id)`
   complet après échec
4. Vérifier le contenu du recipe YAML temporaire
   (ajouter un log `logger.info("Recipe: %s", recipe_data)`)

## E2.15 — enrich="none" contenu enrichi visible

**Source** : validation E2.15 (code narration
sans enrichissement)
**Symptôme** : 363 chunks (vs 367 avec
enrichissement par défaut). "Contenu enrichi
visible" dans les chunks.
**Analyse code post-fix** : le code gère
correctement `enrich="none"` :
- `prep_cfg.enrich_techniques = []` (server.py:688)
- `_resolve_from_config` → `[] or None` = `None`
- Phase 3 : `if enrich and "technique" in enrich`
  → `False` (enrich is None)
- Le delta -4 chunks est cohérent (enrichissement
  LLM ajoute du texte → plus de chunks)

**Hypothèse** : le "contenu enrichi visible"
est en réalité la **narration AST** (E3.42) :
- Headings `## Function:`, `## Class:`, etc.
- Ajoutés en phase 1 (parsing structurel)
- Pas contrôlés par `enrich` — toujours actifs
- Ce n'est pas de l'enrichissement LLM

**Action session validation** :
1. Identifier le type de contenu "enrichi" :
   - "Summary: / Keywords: / Q&A:" → LLM (bug)
   - "## Function: / ## Class:" → narration AST (normal)
2. Si narration AST : requalifier E2.15 comme
   PASS (le delta -4 chunks confirme que
   l'enrichissement LLM est bien désactivé)
3. Si LLM : ajouter un log dans phase 3 pour
   tracer si les fonctions `enrich_*` sont
   appelées malgré `enrich=None`

## Résumé des actions

| Item | Priorité | Action |
|------|----------|--------|
| E12.122 | 1 | Valider grooming → implémenter |
| E2.14 | 2 | Reproduire + collecter logs |
| E2.15 | 3 | Qualifier le contenu "enrichi" |
