# Diagnostic détaillé — E12.115, E12.118, E12.122

Session de test MCP, 2026-10-05/06.

## E12.115 — add_directory "File not found"

### Symptôme
`add_directory("src/lore_mcp", collection="test", enrich="none")` →
28 sources scannées, toutes "File not found".

### Fonctionne en appel direct
```python
cfg.orig_dir = str(Path("src/lore_mcp").resolve())
preprocess_sources(recipe_path, orig_dir, cfg)
# → 2/2 sources ok (server.md, store.md)
```

### Échoue via MCP
Task completed, 0 fichiers, toutes erreurs "File not found".

### Chemin d'appel
1. `add_directory` (server.py:915) scanne → `sources=[{"file": "server.py"}, ...]`
2. → `add_sources(sources=JSON, orig_dir=str(dir_path), ...)` (server.py:964-969)
3. → `_do_adds()` (server.py:781) → `prep_cfg.orig_dir = _docs_dir`
   puis `preprocess_sources(tmp.name, _docs_dir, prep_cfg)`
4. → `preprocess_sources` (preprocess/__init__.py:538) lit `config.orig_dir`
5. → `_phase1_worker` reçoit `str(_orig_dir)` via args (line 660)

### Question clé
E12.121 a ajouté `copy.copy(cfg)`. Est-ce que ce copy est fait
dans `_do_adds()` AVANT la modification de `cfg.orig_dir` ?
Si le copy précède le set, la copie n'a pas le bon `orig_dir`.

Vérifier : la séquence dans `_do_adds()` doit être :
```python
task_cfg = copy.copy(cfg)    # copie AVANT modification
task_cfg.orig_dir = _docs_dir # modification de la copie
preprocess_sources(tmp.name, _docs_dir, task_cfg)
```

Et non :
```python
cfg.orig_dir = _docs_dir     # modification du singleton
task_cfg = copy.copy(cfg)    # copie APRÈS = ok mais risque race
```

### Recipe temporaire
La recipe générée par `add_sources` n'a PAS de champ `orig_dir` :
```yaml
collection: test-code-scan
sources:
- file: server.py
- file: store.py
```
Le fix E12.121 propose "recipe autoporteur (orig_dir in recipe
YAML)". Si la recipe temporaire contenait `orig_dir`, le
subprocess le lirait indépendamment de la config.

### Test de vérification
```bash
add_directory src/lore_mcp --collection test --enrich none
# Attendu : 28 sources indexées
# Actuel : 28 "File not found"
```

---

## E12.118 — enrich="none" sans effet sur add_source

### Symptôme
`add_source("src/lore_mcp/server.py", enrich="none")` →
chunks contiennent du contenu enrichi (contexte LLM, Q&A).

### Preuve
| Collection | enrich param | server.py chunks |
|-----------|-------------|-----------------|
| test-code-py | (default) | 188 |
| test-code-nonenrich | "none" | 182 |
| Différence | | -6 (3%) |

Quasi identique. Le contenu de recherche montre des paragraphes
enrichis : "This section, titled...", Q&A générées, Summary/Keywords.

### Cause probable
Dans `add_source._do_add()`, le paramètre `enrich` n'est pas
traité pour la valeur "none". Comparer avec `add_sources._do_adds()`
(server.py:794-799) :
```python
if enrich == "none":
    prep_cfg.enrich_techniques = []
elif enrich:
    prep_cfg.enrich_techniques = enrich.split(",")
```

Vérifier si `_do_add()` dans `add_source` a le même bloc.

### Test de vérification
```bash
add_source src/lore_mcp/store.py --collection test-none --enrich none
add_source src/lore_mcp/store.py --collection test-default
# Sans enrich : ~30-50 chunks attendus (narration seule)
# Avec enrich : ~100 chunks (narration + context + qa + meta)
```

---

## E12.122 — _get_db sur .db vide

### Symptôme
`add_recipe(preprocess=false, optimize=true)` sur collection neuve →
"no such table: chunks".

### Reproduction
```python
add_recipe(recipe="tests/fixtures/recipe-test-redist.yaml",
           collection="nouvelle-collection",
           preprocess=false, optimize=true)
# → Error: no such table: chunks
```

### Cause
`open_db(path)` fait `sqlite3.connect(path)` qui crée un fichier
vide si inexistant. Mais `create_tables` n'est pas appelé dans le
chemin `preprocess=false` quand aucune donnée n'est ingérée.
L'optimize tente de lire un .db sans tables.

### Fix suggéré
Option A : `_get_db` refuse d'ouvrir un .db inexistant pour les ops
read-only (search, list, eval, optimize).
Option B : `run_build` appelle `create_tables` au début, même sans
preprocess.
Option C : `optimize` vérifie l'existence des tables avant de lancer.
