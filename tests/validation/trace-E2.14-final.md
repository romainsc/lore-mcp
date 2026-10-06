# Trace E2.14 — add_directory FINAL (post E12.123)

Date: 2026-10-06
Commande: `add_directory(directory="src/lore_mcp", collection="test-dir-final", enrich="none", include_pattern="*.py")`
Task: 250e1dbe

## Résultat: PASS
- file_count: 27 (28 scannés, _version.py trop petit)
- chunk_count: 856
- errors: 0
- Elapsed: 99s

## Search test
- Query: "search_docs function semantic search"
- Score: 0.9177
- Source: server.md
- Contenu: narration AST (docstring + code, pas de LLM)

## Fix validé
E12.123 (preprocess→ingest handoff) corrige le bug.
Recipe prep contient les paths .md et orig_dir.
L'ingest trouve les fichiers préprocessés dans prep/.

## Comparaison avec traces précédentes
| Run | Date | Résultat | Cause échec |
|-----|------|----------|-------------|
| 1 | 10-05 | 0/28 File not found | E12.121 config singleton |
| 2 | 10-06 matin | 0/28 File not found | Recipe stale + wrong collection |
| 3 | 10-06 après E12.123 | 27/28 ✓ | Fix handoff OK |
