# Grooming E12.121 — Task config isolation + collection serialization

## Problème

`prep_cfg = cfg` dans les MCP tools est une
affectation de référence — tous les threads
mutent le même objet LoreConfig singleton.
5 points de collision pour des tâches
concurrentes sur la même collection.

### Scénario reproductible

```
Thread 1: add_source("server.py", collection="code")
Thread 2: add_source("store.py", collection="code")
```

### Points de collision

| # | Ressource | Collision | Impact |
|---|-----------|-----------|--------|
| 1 | `_config` singleton | Thread 1 set `orig_dir=/a/`, Thread 2 set `orig_dir=/b/` → Thread 1 lit `/b/` | Fichiers introuvables |
| 2 | SQLite `.db` | Deux `ingest_source` concurrent sur le même fichier | `OperationalError: database is locked` |
| 3 | `prep/` directory | Deux preprocess écrivent les mêmes fichiers intermédiaires | Corruption |
| 4 | `.work/checkpoint.json` | Deux subprocess modifient le même checkpoint | État incohérent |
| 5 | Embedder service | Deux threads appellent `_get_embedder()` | **OK** — protégé par `_init_lock` |

## Fix — 2 parties

### Partie A : Config isolation (résout #1)

Chaque tâche reçoit une **copie** de la config,
pas une référence au singleton.

```python
import copy
task_cfg = copy.copy(cfg)  # shallow copy
task_cfg.orig_dir = str(orig_path)
task_cfg.build_dir = str(col_dir)
```

`copy.copy` (shallow) suffit car les champs
mutés sont des scalaires (str, bool, list).
Les listes (enrich_techniques, llm_registry)
sont remplacées en entier, pas mutées in-place.

De plus, le recipe YAML porte `orig_dir` :

```python
recipe_data = {
    "collection": col_name,
    "orig_dir": str(orig_path),
    "sources": source_list,
}
```

Le recipe est autoporteur — `preprocess_sources`
lit `recipe["orig_dir"]` comme fallback (E12.102).
La config n'a plus besoin d'être mutée pour
`orig_dir`.

### Partie B : Collection lock (résout #2, #3, #4)

Un lock par collection dans TaskManager.
Une seule tâche d'écriture par collection
à la fois.

```python
class TaskManager:
    def __init__(self):
        self._tasks = {}
        self._lock = threading.Lock()
        self.models = ModelRegistry()
        self._collection_locks: dict[str, threading.Lock] = {}
        self._coll_lock = threading.Lock()

    def _get_collection_lock(self, collection: str):
        with self._coll_lock:
            if collection not in self._collection_locks:
                self._collection_locks[collection] = threading.Lock()
            return self._collection_locks[collection]
```

Chaque tool MCP qui modifie une collection
passe `collection=col_name` au TaskManager :

```python
def start(self, name, fn, ..., collection=None):
    ...
    def _worker():
        coll_lock = None
        if collection:
            coll_lock = self._get_collection_lock(collection)
            coll_lock.acquire()
        try:
            ...
        finally:
            if coll_lock:
                coll_lock.release()
```

Les tâches sur des collections différentes
restent parallèles. Les tâches sur la même
collection sont sérialisées.

Les outils en lecture seule (`search_docs`,
`list_indexed_sources`) ne prennent pas le lock.

## Champs mutés par les tools

| Tool | Champs mutés sur cfg | Fix |
|------|---------------------|-----|
| `add_source` | `build_dir`, `output_level`, `orig_dir`, `enrich_techniques` | `copy.copy` + recipe `orig_dir` |
| `add_sources` | `build_dir`, `output_level`, `orig_dir`, `enrich_techniques` | `copy.copy` + recipe `orig_dir` |
| `add_recipe` | `build_dir`, `collection_override`, `force`, `skip_poor`, `preprocess`, `skip_optimize`, `output_level`, `enrich_techniques` | `copy.copy` |
| `add_directory` | Via `add_sources` | Idem |

## DoD

- Chaque tâche MCP utilise `copy.copy(cfg)`
- `orig_dir` dans le recipe YAML temporaire
- Collection lock dans TaskManager
- Test : 2 add_source concurrents sur la même
  collection → sérialisés, pas de crash
- Test : 2 add_source sur des collections
  différentes → parallèles
- CI green

## MVPs

### MVP1 — Config copy + recipe autoporteur

- `copy.copy(cfg)` dans add_source, add_sources,
  add_recipe
- `orig_dir` dans recipe_data temporaire
- Supprime la mutation de `cfg.orig_dir`

### MVP2 — Collection lock

- `_collection_locks` dans TaskManager
- `collection` param dans `start()`
- Sérialisation des écritures par collection

## Effort

MVP1 : petit (3 tools × 2 lignes).
MVP2 : petit (TaskManager + 3 appelants).
