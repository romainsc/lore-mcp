# Trace E2.14 — add_directory "File not found"

Date: 2026-10-06
Commande: `add_directory(directory="src/lore_mcp", collection="trace-dir", enrich="none", include_pattern="*.py")`
Task: 48453219
CWD: /home/rchanter/EspacePrivé/lore-mcp

## Résultat
- file_count: 0, chunk_count: 0
- 28/28 erreurs "File not found"
- Elapsed: 47s

## Preprocess : OK (28/28)
Le preprocess-report.json montre 28 sources OK.
Les fichiers prep/ existent (19 .md dans workspace-validation/build/trace-dir/prep/).
Le phase1-report.json montre src_path correct (/home/.../src/lore_mcp/server.py).

## Bug identifié : recipe temporaire stale

### Recipe YAML temporaire (/tmp/lore-adds-*.yaml)
```yaml
collection: test-code-scan   # ← MAUVAIS : ancien run, pas "trace-dir"
level: ''
sources:
- file: __init__.py
  path: __init__.py
...
```

**Pas d'orig_dir dans la recipe.**

### Analyse
1. Le preprocess réussit car `prep_cfg.orig_dir` est correctement set (E12.121 copy.copy fonctionne)
2. Les fichiers prep sont écrits dans `workspace-validation/build/trace-dir/prep/`
3. Mais la recipe-prep (post-preprocess) a `collection: test-code-scan`
4. L'ingest utilise la recipe-prep pour trouver les fichiers
5. L'ingest cherche dans `workspace-validation/build/test-code-scan/prep/` qui n'existe pas
6. → Tous les fichiers "File not found"

### Cause racine
Le recipe temporaire dans `/tmp/` n'est pas re-créé à chaque appel — il reste d'un run précédent. OU le `collection` dans la recipe est écrit par `add_sources._do_adds()` avec la mauvaise valeur.

### Vérification code
`add_sources` (server.py) fait :
```python
recipe_data = {"collection": col_name, "sources": source_list}
```
`col_name = collection or cfg.default_collection`

Si E12.121 copy.copy fonctionne, `cfg.default_collection` devrait être "trace-dir" (passé en paramètre).
Mais `collection` est passé à `add_sources` par `add_directory` → vérifier si le paramètre est bien transmis.

### Fichiers de trace
- Recipe temporaire : /tmp/lore-adds-*.yaml (voir contenu ci-dessus)
- Preprocess report : workspace-validation/build/trace-dir/preprocess-report.json (28 ok)
- Phase1 report : workspace-validation/build/trace-dir/.work/phase1-report.json (28 ok, src_path correct)
- Prep dir : workspace-validation/build/trace-dir/prep/ (19 fichiers .md)

## Trace E2.15 — enrich="none" requalifié PASS

### Test
```
add_source(file="src/lore_mcp/store.py", collection="trace-nonenrich", enrich="none")
```
Result: 52 chunks (vs 100 avec enrich default = -48%)

### Contenu sans enrich
```
Open a SQLite database and load the sqlite-vec extension.
def open_db(path: str) -> sqlite3.Connection:
    ...
```
Narration AST pure, pas de contenu LLM.

### Contenu avec enrich (E2.11 test-code-py)
```
This section, titled "open_db(path: str) -> sqlite3.Connection",
is a part of a comprehensive guide on utilizing SQLite databases...
```
Contexte LLM, Q&A, Summary/Keywords.

### Conclusion
enrich="none" fonctionne correctement pour add_source.
Le test E2.15 précédent comparait les mauvaises collections.
**E2.15 → PASS**
