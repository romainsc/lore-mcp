# Grooming E12.114 — Unified format registry

## Problème

Le mapping extension → backend est éparpillé
dans 3 dictionnaires hardcodés :

| Dictionnaire | Fichier | Rôle |
|-------------|---------|------|
| `_BACKEND_MAP` | parse.py | ext → backend (32 entrées) |
| `_MIME_TO_BACKEND` | parse.py | mime → backend (11 entrées) |
| `_TS_CANDIDATES` | narrate.py | ext → tree-sitter module (17 entrées) |

Conséquences :
- Ajouter un format = modifier le code source
- Désynchronisation entre les listes
- Pas de visibilité utilisateur sur les formats
  supportés
- Pas de personnalisation

## Backends

Un backend est un chemin de traitement dans le
pipeline. Chaque backend prend un fichier en
entrée et produit du markdown en sortie.

| Backend | Entrée | Traitement | Sortie | Dépendance |
|---------|--------|-----------|--------|-----------|
| `markdown` | `.md` | Passthrough (lecture directe) | Le texte tel quel | Aucune (stdlib) |
| `html` | `.html`, `.htm` | trafilatura extrait le contenu, ignore nav/footer/ads | Markdown clean | trafilatura (optionnel) |
| `docling` | `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.epub`, images | Docling parse le document structuré (OCR, tables, headings) | Markdown structuré + JSON intermédiaire pour captioning | docling (optionnel) |
| `markitdown` | `.csv`, `.json`, `.xml` | markitdown convertit en texte/tables markdown | Tables markdown ou texte brut | markitdown (optionnel) |
| `code` | `.py`, `.js`, `.ts`, `.java`, `.go`, `.c`, etc. | Passthrough puis narration AST (headings aux frontières syntaxiques, code préservé dans code blocks) | Markdown avec headings classe/fonction | ast (stdlib) ou tree-sitter (optionnel) |
| `audio` | `.mp3`, `.wav`, `.flac`, etc. | STT via API OpenAI-compatible | Markdown avec timestamps | ffmpeg + API STT |
| `video` | `.mp4`, `.webm`, `.mkv`, etc. | STT + extraction de frames | Markdown avec transcription + frames base64 | ffmpeg + API STT |

**Chaque backend a une dépendance optionnelle.**
Si la dépendance n'est pas installée, le format
n'est pas disponible. Exception : `markdown` et
`code` (mode Python ast) fonctionnent sans
dépendance externe.

## API du FormatRegistry

### `detect(filename: str) -> str`

**Rôle** : déterminer quel backend utiliser pour
traiter un fichier.

**Algorithme** (3 niveaux, premier qui matche) :

1. **Content-based** (puremagic) : si le fichier
   existe sur disque, lire les magic bytes et
   résoudre le MIME type → chercher dans le
   mapping MIME → backend. Permet de détecter
   un `.html` renommé en `.txt` ou un fichier
   sans extension.

2. **Extension** : chercher l'extension dans le
   mapping ext → backend. Couvre les formats
   texte que puremagic ne distingue pas (.md,
   .csv, .py — tous `text/plain` pour puremagic).

3. **MIME via mimetypes** (stdlib) : pour
   audio/video, `mimetypes.guess_type()` donne
   le type générique.

**Retour** : le nom du backend (`"markdown"`,
`"html"`, `"docling"`, `"markitdown"`, `"code"`,
`"audio"`, `"video"`).

**Erreur** : `FormatNotSupported` si aucun
mapping ne correspond.

### `is_supported(filename: str) -> bool`

**Rôle** : déterminer si un fichier peut être
traité par le pipeline, sans l'ouvrir.

**Algorithme** :
1. Extension dans le mapping ext → backend ?
   → `True`
2. MIME via mimetypes → audio ou video ?
   → `True`
3. → `False`

**Différence avec `detect()`** :
- `is_supported` est rapide (pas d'I/O disque,
  pas de puremagic) — utilisé par `scan_directory`
  pour filtrer des milliers de fichiers
- `detect` est précis (lit le contenu) — utilisé
  au moment du parsing effectif

**Cas d'usage** :
- `scan_directory` : filtrer les fichiers à
  inclure dans un recipe auto-généré
- `expand_directory_entries` : filtrer les
  fichiers dans un répertoire déclaré dans
  un recipe

### `has_structural_parser(ext: str) -> bool`

**Rôle** : déterminer si un fichier code aura
une narration structurelle (headings par
classe/fonction) ou un fallback (h1 + code block
unique).

**Algorithme** :
1. `.py` → `True` (ast stdlib, toujours
   disponible)
2. Extension dans le mapping tree-sitter détecté
   dynamiquement → `True`
3. → `False`

**Cas d'usage** :
- `scan_directory` : émettre un warning si un
  fichier code est trouvé mais n'a pas de
  parser structurel (tree-sitter non installé
  pour ce langage)
- `narrate.py:_narrate_code` : choisir entre
  tree-sitter parsing et fallback code block
- `get_config()` : informer l'utilisateur des
  langages avec/sans parser

### `get_treesitter(ext: str) -> tuple[str, str] | None`

**Rôle** : retourner le module tree-sitter et
le nom de langage pour une extension donnée.

**Retour** : `("tree_sitter_python", "python")`
ou `None` si non disponible.

**Cas d'usage** : `_narrate_treesitter()` pour
instancier le parser du bon langage.

### `apply_config(overrides: dict)`

**Rôle** : appliquer les overrides de config.yaml.

**Comportement** :
- Ajoute ou modifie un mapping ext → backend
- Valide que le backend est connu (un des 7)
- Extension vide (`""`) = supprimer le mapping

**Erreur** : `ValueError` si backend inconnu.

### `list_formats() -> dict`

**Rôle** : retourner tous les formats supportés
avec leur état.

**Retour** :
```python
{
    ".pdf": {"backend": "docling", "available": True},
    ".go": {"backend": "code", "available": True,
            "structural_parser": False},
    ".py": {"backend": "code", "available": True,
            "structural_parser": True,
            "parser": "ast (stdlib)"},
    ".js": {"backend": "code", "available": True,
            "structural_parser": True,
            "parser": "tree-sitter-javascript"},
}
```

**Cas d'usage** : `get_config()` MCP tool,
diagnostic.

## config.yaml

```yaml
parse:
  # Existing fields...
  ocr_engine: tesseract
  ocr_lang: [fra, eng]

  # New: format overrides (advanced)
  formats:
    .proto: markitdown   # add protobuf support
    .txt: markdown       # treat .txt as markdown
    .rst: markdown       # reStructuredText as md
    .lua: ""             # disable .lua support
```

Validation au chargement :
- Backend doit être un des 7 connus
- Extension vide = suppression du mapping
- Warning si l'override remplace un défaut
  existant

## Migration

### Avant → Après

| Avant | Après |
|-------|-------|
| `parse.py:_BACKEND_MAP` | `FormatRegistry._ext_map` (défauts) |
| `parse.py:_MIME_TO_BACKEND` | `FormatRegistry._mime_map` (défauts) |
| `narrate.py:_TS_CANDIDATES` | `FormatRegistry._ts_map` (détecté) |
| `parse.py:detect_format(f)` | `get_format_registry().detect(f)` |
| `recipe.py:_is_supported(f)` | `get_format_registry().is_supported(f)` |
| `narrate.py:code_language_available(e)` | `get_format_registry().has_structural_parser(e)` |
| `narrate.py:_detect_ts_languages()` | `get_format_registry()._ts_map` |

`detect_format()` dans parse.py est conservé
comme façade pour ne pas casser les imports
existants. Il délègue au registry.

### Fichiers modifiés

| Fichier | Changement |
|---------|-----------|
| `format_registry.py` (nouveau) | Classe FormatRegistry |
| `parse.py` | Supprimer `_BACKEND_MAP`, `_MIME_TO_BACKEND`. `detect_format` → façade |
| `narrate.py` | Supprimer `_TS_CANDIDATES`, `_detect_ts_languages`, `code_language_available`. Importer depuis registry |
| `recipe.py` | Supprimer `_is_supported`. Importer depuis registry |
| `config.py` | Ajouter `format_overrides: dict` |
| `server.py` | `get_config()` inclut formats |

## Comportement explicite vs implicite

| Contexte | Format supporté | Code sans parser | Format inconnu |
|----------|:---:|:---:|:---:|
| **Explicite** (recipe `file:`) | Parse | Parse (fallback code block) | **Erreur** dans rapport |
| **Implicite** (scan répertoire) | Parse | Parse + **warning** (tree-sitter manquant) | **Ignoré** silencieusement |
| **Config override** | Parse | Parse | **Erreur** si backend invalide |

## 3 itérations sèches

### Itération 1 — FormatRegistry classe

- `src/lore_mcp/format_registry.py`
- Défauts intégrés + détection tree-sitter
- API : `detect()`, `is_supported()`,
  `has_structural_parser()`, `get_treesitter()`,
  `list_formats()`
- Singleton `get_format_registry()`
- Migrer les 6 fichiers
- Supprimer les 3 dictionnaires
- `detect_format()` conservé comme façade

### Itération 2 — Config overrides

- `parse.formats` dans config.yaml
- `format_overrides` dans LoreConfig
- `apply_config()` avec validation
- `get_config()` expose les formats

### Itération 3 — Explicite vs implicite

- Erreur pour fichiers explicites non supportés
- Warning pour fichiers implicites sans parser
- Utilise `orig_was_explicit` existant dans
  `_phase1_worker`

## DoD (itération 1)

- FormatRegistry unique source de vérité
- 3 dictionnaires hardcodés supprimés
- Tous les consommateurs migrés
- `detect_format()` conservé comme façade
- Tests existants passent
- Nouveaux tests pour le registry
- CI green

## Dépendances

Aucune.

## Effort

Itération 1 : moyen (refactoring 6 fichiers,
~200 lignes). Itération 2 : petit. Itération 3 :
petit.
