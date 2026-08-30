---
id: SPEC-017
title: "Dynamic File Extension Registry and Directory Traversal"
tier: 1
type: refactor
priority: P1
status: active
impact: "Eliminates hardcoded extension list in convert.py and prevents missing parser extensions (e.g. .nyc, .xml, .json)"
deliverables:
  - parsers/base.py
  - parsers/registry.py
  - convert.py
---

# Spec: Dynamic File Extension Registry and Directory Traversal

## Description

Currently, `process_directory()` in `convert.py` (lines 456–476) hardcodes a static set of file extensions to search for:
```python
extensions = {
    ".mca", ".mmf", ".mm", ".mxp", ".mx2", ".mz2", ".txt",
    ".html", ".htm", ".shtml", ".pdf", ".jpg", ".png",
    ".sqlite", ".db", ".csv", ".ccf", ".md",
}
```

This creates a split source of truth: each parser knows what file types it can handle, but `convert.py` decides what files are discovered. Crucially, valid formats like `.nyc` (`NYCParser`), `.xml` (`RecipeMLParser`), and `.json` (`RicetteJsonParser`) are missing from this hardcoded set. Consequently, batch directory conversion silently skips these recipe files unless individual files are targeted.

This specification:
1. Adds `supported_extensions()` to `BaseRecipeParser` with parser-level declarations.
2. Implements `ParserRegistry.supported_extensions()` to aggregate all known extensions dynamically.
3. Refactors `convert.py` directory traversal to query the registry.
4. Adds an optional `--ext` CLI argument allowing users to filter by specific file extensions.

## Worktree & Branch Protocol

Following repository golden rules:
```bash
git worktree add -b feat/spec-017-dynamic-extensions .worktrees/spec-017 main
cd .worktrees/spec-017
```
After verification, commit, merge to `main`, and remove worktree.

---

## Detailed Specification

### 1. `parsers/base.py`: Extension Protocol

Add `supported_extensions` classmethod to `BaseRecipeParser`:

```python
@classmethod
def supported_extensions(cls) -> set[str]:
    """
    Return set of lowercased file extensions (with leading dot) handled by this parser.
    Default implementation returns an empty set.
    """
    return set()
```

### 2. Implement `supported_extensions()` Across Registered Parsers

Update each parser subclass to declare its native extensions, for example:
- `MealMasterParser`: `{'.mmf', '.mm'}`
- `MasterCookParser`: `{'.mxp', '.mx2', '.mz2'}`
- `CompuChefParser`: `{'.ccf'}`
- `NYCParser`: `{'.nyc'}`
- `RecipeMLParser`: `{'.xml'}`
- `MicroCookParser`: `{'.mca'}`
- `CookwareCSVParser`: `{'.csv'}`
- `RicetteJsonParser`: `{'.json'}`
- `SqliteRecipeParser`: `{'.sqlite', '.db'}`
- `HtmlParser`: `{'.html', '.htm', '.shtml'}`
- `GenericMdParser`: `{'.md'}`
- `GenericTextParser`: `{'.txt', '.prn', '.out'}`
- `PdfParser`: `{'.pdf'}`
- `ImageParser`: `{'.jpg', '.jpeg', '.png'}`

### 3. `parsers/registry.py`: Registry Aggregator

Add `supported_extensions` to `ParserRegistry`:

```python
@classmethod
def supported_extensions(cls) -> set[str]:
    """Aggregate all unique supported extensions across all registered parsers."""
    exts: set[str] = set()
    for parser in cls._parsers:
        exts.update(parser.supported_extensions())
    return exts
```

### 4. `convert.py`: Dynamic Discovery & CLI Extension Filter

In `parse_arguments()`:
```python
parser.add_argument(
    "--ext",
    nargs="+",
    default=None,
    help="Explicit list of file extensions to process (e.g. --ext .mmf .txt). Defaults to all registered parser extensions.",
)
```

In `process_directory()`:
```python
    if cli_extensions:
        extensions = {ext if ext.startswith(".") else f".{ext}" for ext in cli_extensions}
    else:
        extensions = ParserRegistry.supported_extensions()
        if not extensions:
            # Safe fallback if registry is empty
            extensions = {".txt", ".mmf", ".html", ".htm"}

    # Include uppercase variants
    extensions.update([e.upper() for e in extensions])
```

---

## Edge Cases

1. **Extension Case Insensitivity**: On case-sensitive filesystems (Linux), files may be named `.NYC`, `.MMF`, or `.mmf`. Ensure `.upper()` and `.lower()` variants are searched or matched.
2. **Parser Without Extensions**: Parsers that handle arbitrary text (like `MixedFormatParser` or `IdCapsParser`) should return empty sets or rely on generic fallbacks so they don't claim all filenames.
3. **Leading Dots**: Ensure consistent dot formatting (e.g. `.mmf`, not `mmf`) both from registry and when parsing `--ext` CLI flags.

---

## Acceptance Criteria

- [ ] `BaseRecipeParser.supported_extensions()` is defined on base class.
- [ ] All major parsers declare their supported file extensions (including `.nyc`, `.xml`, `.json`).
- [ ] `ParserRegistry.supported_extensions()` returns the combined unique set of all extensions.
- [ ] `convert.py` queries `ParserRegistry.supported_extensions()` instead of using a hardcoded set.
- [ ] Passing `--ext` restricts directory scanning to specified extensions.
- [ ] All 70 existing pytest tests pass: `./venv/bin/python3 -m pytest tests/ -v`.

---

## Verification Plan

```bash
# 1. Verify extensions include previously omitted formats
./venv/bin/python3 -c "
from parsers import ParserRegistry
exts = ParserRegistry.supported_extensions()
print('Supported extensions:', sorted(exts))
assert '.nyc' in exts, 'Missing .nyc'
assert '.xml' in exts, 'Missing .xml'
assert '.json' in exts, 'Missing .json'
assert '.mmf' in exts, 'Missing .mmf'
"

# 2. Run test suite
./venv/bin/python3 -m pytest tests/ -v
```
