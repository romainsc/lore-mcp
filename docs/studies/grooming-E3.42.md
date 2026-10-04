# Grooming E3.42 — Code narration for RAG

## Problème

Le code source brut a une faible valeur pour le
RAG documentaire :
- Pas de headings → HybridChunker coupe
  arbitrairement (milieu de fonction)
- Docstrings noyées dans la syntaxe → embedding
  mélange code + prose
- Quality gate : heading_count=0,
  structure_score=0.0, verdict=warn/poor
- Enrichissement LLM phase 3 travaille sur un
  blob → résultats génériques

## Retour d'expérience mondial (2025-2026)

### Consensus

**tree-sitter** est le standard pour le code
RAG. Principe validé : chunker aux frontières
syntaxiques (fonctions, classes) au lieu de
couper à taille fixe.

Résultats mesurés :
- cAST paper (juin 2025) : +5.5pts RepoEval
  avec StarCoder2-7B, language-agnostic
- Aider : repo map tree-sitter + PageRank
- Cursor, Windsurf, CocoIndex : tree-sitter
  standard
- CodeRAG : dependency graph pour contexte
  multi-hop

Deux familles d'approches :
1. **AST chunking** — tree-sitter produit des
   chunks = unités syntaxiques complètes.
   Consensus fort, validé par la recherche.
2. **Graph RAG** — graphe de dépendances.
   Couvert par codebase-memory MCP.

### Ce qui ne fonctionne pas

- Chunking naïf (ligne/caractère) : casse les
  fonctions, perd le contexte
- Python `ast` seul : Python-only
- Regex (`\ndef `) : fragile, faux positifs
  dans strings multi-lignes
- Narration pure (code → prose) : approche
  marginale, perte d'information

### Approche retenue : option 2 intégrée

tree-sitter parse le code, produit du markdown
structuré avec headings aux frontières
syntaxiques et **code préservé** dans des code
blocks. HybridChunker chunke aux headings =
chunking AST via le pipeline existant.

Sources :
- [cAST: Structural Chunking via AST](https://arxiv.org/html/2506.15655v1)
- [AST Chunking for Code RAG](https://vxrl.medium.com/enhancing-llm-code-generation-with-rag-and-ast-based-chunking-5b81902ae9fc)
- [CocoIndex tree-sitter](https://cocoindexio.substack.com/p/index-codebase-with-tree-sitter-and)
- [10 Chunking Strategies](https://dev.to/klement_gunndu/10-chunking-strategies-that-make-or-break-your-rag-pipeline-4cng)
- [CodeRAG with Dependency Graph](https://medium.com/@shsax/how-i-built-coderag-with-dependency-graph-using-tree-sitter-0a71867059ae)

## Rôle de la narration dans le pipeline

La narration ne crée pas de contenu — elle
**restructure** le code pour que les étapes
suivantes du pipeline fonctionnent :

### Étape 1 : Narration (phase 1 preprocess)

Transforme le code brut en markdown structuré :
- Headings aux frontières syntaxiques
  (module, classe, fonction)
- Docstrings extraites comme texte libre
  (hors code block)
- Signatures dans les headings
- Code body préservé dans des code blocks

### Étape 2 : Chunking (HybridChunker)

HybridChunker voit les headings et produit
des chunks = unités syntaxiques complètes.
Sans narration, il couperait le code
arbitrairement à ~1024 chars.

### Étape 3 : Enrichissement LLM (optionnel)

Le pipeline d'enrichissement existant (E12.09)
travaille section par section :
- **context** : ajoute un paragraphe de
  contexte par fonction ("This function
  handles document processing by reading,
  chunking and embedding the content")
- **meta** : génère résumé + mots-clés par
  section
- **qa** : génère des questions/réponses
  ("Q: How to process a document for indexing?
  A: Call processor.process(path)")

Sans narration, l'enrichissement opère sur des
blobs de code arbitraires. Avec narration,
chaque section enrichie correspond à une
unité syntaxique.

### Étape 4 : Embedding + indexation

L'embedding capture le sens sémantique de
chaque chunk : signature + docstring + contexte
enrichi + code. La recherche vectorielle
"how to process a document" matche le chunk
`process()` grâce à la docstring et au contexte.

## Exemple concret

### Entrée : `processor.py`

```python
"""Document processing pipeline for the indexing service.

Handles PDF, HTML, and Markdown conversion with configurable
chunking and embedding strategies.
"""

import os
from pathlib import Path
from typing import Optional

from lore_mcp.embedder import Embedder
from lore_mcp.store import open_db


SUPPORTED_FORMATS = {".pdf", ".html", ".md", ".docx"}
DEFAULT_CHUNK_SIZE = 1024


class DocumentProcessor:
    """Process documents for RAG indexing.

    Supports multi-format ingestion with automatic format
    detection and configurable chunking parameters.
    """

    def __init__(self, config: dict, embedder: Embedder):
        """Initialize with config and embedding model."""
        self.config = config
        self.embedder = embedder
        self._db = None

    def process(self, path: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> dict:
        """Process a single document and return indexing results.

        Args:
            path: path to the source document
            chunk_size: maximum chunk size in characters

        Returns:
            dict with keys: source_file, chunk_count, status
        """
        content = Path(path).read_text(encoding="utf-8")
        chunks = self._chunk(content, chunk_size)
        embeddings = self.embedder.embed_batch([c["text"] for c in chunks])
        return {
            "source_file": path,
            "chunk_count": len(chunks),
            "status": "ok",
        }

    def _chunk(self, text: str, size: int) -> list[dict]:
        """Split text into chunks of approximately `size` characters."""
        return [{"text": text[:size]}]

    @property
    def db(self):
        """Lazy database connection."""
        if self._db is None:
            self._db = open_db(self.config["db_path"])
        return self._db


def validate_format(path: str) -> bool:
    """Check if a file format is supported for processing."""
    return Path(path).suffix.lower() in SUPPORTED_FORMATS


def batch_process(
    paths: list[str],
    config: dict,
    embedder: Embedder,
    parallel: bool = False,
) -> list[dict]:
    """Process multiple documents. Returns list of results.

    If parallel=True, uses thread pool for I/O-bound operations.
    """
    processor = DocumentProcessor(config, embedder)
    return [processor.process(p) for p in paths]
```

### Sortie narration : `processor.md`

```markdown
# processor

Document processing pipeline for the indexing service.

Handles PDF, HTML, and Markdown conversion with configurable
chunking and embedding strategies.

## Imports

- import os
- from pathlib import Path
- from typing import Optional
- from lore_mcp.embedder import Embedder
- from lore_mcp.store import open_db

## Constants

- `SUPPORTED_FORMATS` = {".pdf", ".html", ".md", ".docx"}
- `DEFAULT_CHUNK_SIZE` = 1024

## Class DocumentProcessor

Process documents for RAG indexing.

Supports multi-format ingestion with automatic format
detection and configurable chunking parameters.

### \_\_init\_\_(self, config: dict, embedder: Embedder)

Initialize with config and embedding model.

```python
def __init__(self, config: dict, embedder: Embedder):
    self.config = config
    self.embedder = embedder
    self._db = None
```

### process(self, path: str, chunk\_size: int = DEFAULT\_CHUNK\_SIZE) -> dict

Process a single document and return indexing results.

Args:
    path: path to the source document
    chunk_size: maximum chunk size in characters

Returns:
    dict with keys: source_file, chunk_count, status

```python
def process(self, path: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> dict:
    content = Path(path).read_text(encoding="utf-8")
    chunks = self._chunk(content, chunk_size)
    embeddings = self.embedder.embed_batch([c["text"] for c in chunks])
    return {
        "source_file": path,
        "chunk_count": len(chunks),
        "status": "ok",
    }
```

### \_chunk(self, text: str, size: int) -> list[dict]

Split text into chunks of approximately `size` characters.

```python
def _chunk(self, text: str, size: int) -> list[dict]:
    return [{"text": text[:size]}]
```

### db (property)

Lazy database connection.

```python
@property
def db(self):
    if self._db is None:
        self._db = open_db(self.config["db_path"])
    return self._db
```

## validate\_format(path: str) -> bool

Check if a file format is supported for processing.

```python
def validate_format(path: str) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_FORMATS
```

## batch\_process(paths, config, embedder, parallel) -> list[dict]

Process multiple documents. Returns list of results.

If parallel=True, uses thread pool for I/O-bound operations.

```python
def batch_process(
    paths: list[str],
    config: dict,
    embedder: Embedder,
    parallel: bool = False,
) -> list[dict]:
    processor = DocumentProcessor(config, embedder)
    return [processor.process(p) for p in paths]
```
```

### Résultat chunking HybridChunker

HybridChunker voit les headings et produit
des chunks aux frontières syntaxiques :

| # | Heading path | Contenu |
|---|-------------|---------|
| 1 | processor | Module docstring |
| 2 | processor > Imports | Liste imports |
| 3 | processor > Constants | Constantes module |
| 4 | processor > DocumentProcessor | Docstring classe |
| 5 | processor > DocumentProcessor > \_\_init\_\_ | Docstring + code |
| 6 | processor > DocumentProcessor > process | Docstring + code |
| 7 | processor > DocumentProcessor > \_chunk | Docstring + code |
| 8 | processor > DocumentProcessor > db | Docstring + code |
| 9 | processor > validate\_format | Docstring + code |
| 10 | processor > batch\_process | Docstring + code |

### Après enrichissement LLM (optionnel)

Chunk 6 (`process`) après `--enrich context,qa` :

```markdown
### process(self, path: str, chunk\_size: int) -> dict

> This method is the main entry point for document
> indexing. It reads a source file, splits it into
> chunks, computes vector embeddings, and returns
> indexing statistics.

Process a single document and return indexing results.

Args:
    path: path to the source document
    chunk_size: maximum chunk size in characters

Returns:
    dict with keys: source_file, chunk_count, status

```python
def process(self, path: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> dict:
    content = Path(path).read_text(encoding="utf-8")
    chunks = self._chunk(content, chunk_size)
    embeddings = self.embedder.embed_batch([c["text"] for c in chunks])
    return {"source_file": path, "chunk_count": len(chunks), "status": "ok"}
```

> **Q: How to index a single document?**
> Call `processor.process(path)` with optional
> `chunk_size` parameter. Returns a dict with
> source_file, chunk_count, and status.
```

### Comparaison recherche vectorielle

Query : "how to process a document for indexing"

| Approche | Chunk matché | Score | Pourquoi |
|----------|-------------|-------|----------|
| Code brut (pas de narration) | Bloc arbitraire lignes 30-60 | ~0.4 | Mélange syntaxe + prose |
| Narration seule | Chunk 6 (process) | ~0.6 | Docstring + signature |
| Narration + enrichissement | Chunk 6 enrichi | ~0.8 | Contexte LLM + Q&A |

## 3 itérations sèches

### Itération 1 — Python `ast` (aucune dépendance)

Module : `narrate.py`, fonction
`_narrate_python(text, filename)`.

Parse via `ast.parse()` (Python 3.10+ natif).
Extrait :
- Module docstring → h1 avec nom fichier
- Imports → h2 "Imports" + liste à puces
- Constantes module → h2 "Constants" + liste
- Classes → h2 "Class {name}" + docstring
- Méthodes → h3 "{name}({signature})" +
  docstring + code block
- Properties → h3 "{name} (property)" +
  docstring + code block
- Fonctions top-level → h2 "{name}({signature})"
  + docstring + code block

Langages non-Python (.js, .go, .rs, etc.) :
fallback → h1 filename + code block complet.
Le fichier est indexable mais pas structuré.

Câblage :
- `_BACKEND_MAP` dans parse.py : `.py` → `"code"`
  (+ autres extensions pour le fallback)
- `parse_to_markdown` backend `"code"` :
  passthrough (retourne le texte brut)
- `_phase1_worker` : si backend == "code",
  appeler `narrate_structured(text, "code",
  filename=src_path.name)`

### Itération 2 — tree-sitter multi-langage

Dépendance optionnelle : `tree-sitter` (MIT).
Install : `pip install lore-mcp[code]`.

`_narrate_treesitter(text, filename, language)`.
Supporter : Python, JavaScript/TypeScript,
Java, Go, Rust, C/C++, Ruby.

Cascade : tree-sitter installé → parsing AST
multi-langage. Sinon → fallback itération 1.

tree-sitter détecte la langue via l'extension.
Query les nœuds `function_definition`,
`class_definition`, `method_definition` selon
la grammaire du langage.

### Itération 3 — Enrichissement structurel

Ajouter au markdown narré :
- Type annotations complètes (return type,
  param types)
- Décorateurs (`@staticmethod`, `@property`,
  `@app.route("/api")`)
- Héritage (`class X(Base, Mixin)`)
- Statistiques module (LOC, nb fonctions,
  nb classes, complexité cyclomatique)
- Détection framework : Flask routes →
  "### GET /api/users", Django views →
  "### View: UserListView"

## detect_format

Extensions ajoutées à `_BACKEND_MAP` dans
parse.py :

```python
".py": "code",
".js": "code", ".jsx": "code",
".ts": "code", ".tsx": "code",
".java": "code",
".go": "code",
".rs": "code",
".c": "code", ".cpp": "code",
".h": "code", ".hpp": "code",
".rb": "code",
".sh": "code", ".bash": "code",
".lua": "code",
".php": "code",
```

## DoD (itération 1)

- .py : headings module/classe/fonction, code
  dans code blocks, docstrings en texte libre
- .js/.go/etc : h1 filename + code block
  complet (fallback, pas d'erreur)
- Quality gate passe (heading_count > 0,
  structure_score > 0)
- HybridChunker produit des chunks aux
  frontières syntaxiques
- Enrichissement LLM fonctionne sur la sortie
  narrée (pas de régression)
- Test : fichier Python 80 lignes → narration
  avec 8+ headings
- Test : fichier .js → fallback code block
  avec heading h1
- Test : quality gate passe sur résultat narré
- Test : round-trip narration → chunking →
  au moins 5 chunks distincts
- CI green

## Dépendances

Itération 1 : aucune (ast est stdlib).
Itération 2 : tree-sitter (MIT), optionnel.

## Effort

Itération 1 : petit (1 fonction ~80 lignes
dans narrate.py + câblage pipeline).
Itération 2 : moyen (tree-sitter + grammaires
pour 8 langages).
Itération 3 : petit (enrichissement textuel
dans la fonction existante).
