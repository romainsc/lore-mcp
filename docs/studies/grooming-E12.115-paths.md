# Grooming E12.115 — Path management overhaul

## Constat

Le design E12.90 (validé, implémenté) définit :
- **2 paramètres seulement** : `--orig-dir`
  (read-only sources) + `--build-dir` (tout
  le reste)
- `--docs-base-dir` supprimé
- `--prep-dir` supprimé (= `build-dir/prep/`)
- `--output-dir` supprimé (= `build-dir/`)

Le code actuel ne respecte pas ce design :
- `docs_base_dir` encore paramètre de
  `preprocess_sources()` et `_phase1_worker()`
- `preprocess_orig_dir` et `preprocess_prep_dir`
  encore dans LoreConfig (défaut `"."`)
- Branch legacy (old model) et branch E12.90
  (new model) coexistent dans server.py
- 12 occurrences de `or "."` comme sentinel
- 5/7 points d'entrée ne résolvent pas les
  chemins en absolu

## Audit exhaustif (2026-10-06)

### Anti-patterns (5 systémiques)

1. **`or "."` comme sentinel** — 12 occurrences
   dans server.py. `"."` est un chemin valide,
   pas une valeur nulle. Résolution dépendante
   du cwd.

2. **Triple source de vérité pour orig_dir** :
   `config.orig_dir`, `config.preprocess_orig_dir`,
   paramètre `docs_base_dir`. Priorité confuse
   (L545 : `config.orig_dir or preprocess_orig_dir`).

3. **`.resolve()` manquant** — 5/7 points
   d'entrée passent des chemins potentiellement
   relatifs (add_sources, add_recipe, CLI build,
   CLI preprocess, CLI enrich).

4. **Résolution relative incohérente** —
   branch `build_dir` utilise `Path.cwd()`,
   branch legacy utilise `base` (docs_base_dir).
   Même chemin relatif → résultat différent.

5. **Bug dormant legacy** — build.py L112 :
   `Path(docs_dir) / "." / Path(docs_dir).name`
   avec `preprocess_prep_dir="."` → chemin
   dupliqué.

### Fichiers propres

recipe.py, ingest.py, lint.py, collections.py,
store.py, embedder.py, checkpoint.py — aucun
anti-pattern.

## Design cible (E12.90 respecté)

### LoreConfig — 2 chemins seulement

```python
@dataclass
class LoreConfig:
    # Directories (2 only, per E12.90)
    orig_dir: str = ""     # read-only sources
    build_dir: str = ""    # everything else
    # No more: preprocess_orig_dir,
    # preprocess_prep_dir, work_dir,
    # intermediates_dir
```

Derived paths (properties, not fields) :
- `prep_dir` = `build_dir / "prep"`
- `work_dir` = `build_dir / ".work"`
- `db_path` = `build_dir / "{collection}.db"`

### preprocess_sources — 2 params + config

```python
def preprocess_sources(
    recipe_path: str,
    config,
) -> list[dict]:
```

Supprimer `docs_base_dir` paramètre. Tout
depuis `config.orig_dir` et `config.build_dir`.

### _phase1_worker — 3 params fixes

```python
def _phase1_worker(
    recipe_path, orig_dir, work_dir,
    report_path, output_level, ...
):
```

- `orig_dir` : le vrai chemin résolu (plus
  `docs_base_dir` + `"."`)
- `work_dir` : répertoire intermédiaires
  (`build_dir/.work/`)
- Plus de `docs_base_dir` ni de sentinel `"."`

### Points d'entrée — resolve systématique

```python
# Pattern unique pour tous les tools MCP et CLI
orig = Path(user_input).resolve() if user_input else None
cfg.orig_dir = str(orig) if orig else ""
cfg.build_dir = str(Path(build_input).resolve()) if build_input else ""
```

## Plan d'implémentation

### MVP1 — Supprimer les fields legacy

- Supprimer de LoreConfig :
  `preprocess_orig_dir`, `preprocess_prep_dir`
- Remplacer toutes les refs par `orig_dir` et
  properties dérivées de `build_dir`
- Supprimer le branch legacy dans
  `preprocess_sources` (branch `else` L605-622)
- Supprimer le branch legacy dans build.py
  (L108, L112)
- Adapter les CLI qui set `preprocess_orig_dir`

Fichiers touchés : config.py, server.py,
preprocess/__init__.py, build.py

### MVP2 — Supprimer docs_base_dir

- `preprocess_sources` : supprimer le paramètre
  `docs_base_dir`, lire `config.orig_dir`
- `_phase1_worker` : supprimer le paramètre
  `orig_dir` sentinel, passer `config.orig_dir`
  comme `orig_dir` (1er arg utilisable)
- Adapter tous les appelants (server.py ×3,
  build.py ×1)

### MVP3 — Résoudre systématiquement

- Chaque tool MCP : `Path(input).resolve()`
- Chaque CLI : `Path(args.orig_dir).resolve()`
- Plus de `or "."` — chaîne vide pour "pas de
  valeur"
- Supprimer les 12 occurrences de `or "."`

### MVP4 — Adapter les tests

- `_phase1_worker` change de signature →
  adapter test_preprocess.py
- `preprocess_sources` change de signature →
  adapter test_preprocess.py, test_build_preprocess.py
- Vérifier que les tests passent des chemins
  absolus (tmp_path est déjà absolu)

## DoD

- LoreConfig : `orig_dir` + `build_dir`
  seulement (2 fields chemins)
- `preprocess_orig_dir`, `preprocess_prep_dir`
  supprimés
- `docs_base_dir` paramètre supprimé
- `_phase1_worker` : pas de sentinel `"."`
- 0 occurrence de `or "."` dans le code
- Tous les points d'entrée : `Path.resolve()`
- Design E12.90 respecté intégralement
- Tests adaptés
- CI green (5/5 jobs)

## Règle : pathlib exclusif

Toute construction de chemin DOIT utiliser
`pathlib.Path`. Interdit :
- `os.path.join`, `os.path.dirname`, etc.
- Concaténation string de chemins (`a + "/" + b`)
- `f"{dir}/{file}"` pour des chemins fichier

Seule exception : construction d'URLs
(pas des chemins fichier).

Pattern imposé :
```python
path = Path(user_input).resolve()  # absolu
child = path / "subdir" / "file.txt"  # operator
```

## Note : Docling dans le pipeline

Audit confirmé — tous les choix d'utilisation
de Docling sont groomés et assumés :
- OCR documents : via Docling (E12.43)
- OCR frames vidéo : Tesseract direct (E12.55)
- Enrichissement : LLM direct, pas Docling (E12.08)
- Chunking : Docling HybridChunker pour tout (E12.99)
- Parsing : Docling natif (E12.30)
- Captioning : Docling natif (E12.42)

Pas de changement nécessaire.

## Risques

- Gros refactoring (server.py, preprocess,
  build.py, config.py, tests) — risque de
  régression
- Le branch legacy dans `preprocess_sources`
  est utilisé par les CLI preprocess et enrich
  — vérifier que la suppression ne casse pas
- `docs_base_dir` est le 2e arg de
  `preprocess_sources` — tous les appelants
  doivent être adaptés

## Effort

MVP1 : moyen (grep+replace + supprimer branch)
MVP2 : moyen (changer signatures + appelants)
MVP3 : petit (resolve aux entrées)
MVP4 : moyen (adapter ~10 tests)
Total : ~2h d'implémentation + tests
