# Recipe Format Converter — Claude Code Instructions

## Commands

Always use the project virtualenv. Never use bare `python3` or `python`.

```bash
./venv/bin/python3 convert.py [args]
./venv/bin/python3 -m pytest tests/test_conversion.py
./venv/bin/python3 -m pytest tests/test_conversion.py -v   # verbose
```

## Project Structure

```
scripts/
├── convert.py                 # CLI entry point
├── dedup.py                   # Standalone dedup tool (MinHash LSH)
├── import_to_mealie.py        # Mealie REST importer
├── import_to_tandoor.py       # Tandoor REST importer
├── update_expected.py         # Regenerate expected test outputs
├── configs/                   # SQLite schema YAML configs
├── parsers/
│   ├── __init__.py            # Import all parsers here (triggers registration)
│   ├── base.py                # BaseRecipeParser, BaseIngredientParser
│   ├── models.py              # Recipe, Ingredient dataclasses
│   ├── registry.py            # ParserRegistry (register decorator, get_parser)
│   ├── ingredients.py         # NLP + Regex ingredient parsers
│   ├── units.py               # Unit normalization (160 entries)
│   ├── cookware.py            # Reference parser implementation
│   ├── <format>.py            # One file per format (mealmaster, mastercook, etc.)
│   ├── stubs.py               # PDF, Image, Generic CSV stubs
│   ├── mixed.py               # MixedFormatParser (delegates to sub-parsers)
│   ├── llm_parser.py          # LLM parser (not auto-registered)
│   └── sqlite/                # SQLite subsystem
│       ├── sqlite_config.py   # Schema dataclasses, YAML registry
│       └── sqlite_parser.py   # SqliteRecipeParser
└── tests/
    ├── test_conversion.py     # Parametrized regression suite
    ├── samples/               # Input files (one per format)
    └── expected/              # Expected JSON output (--no-nlp)
```

## Architecture — Parser Registry

All parsers use the Registry Pattern.

- **Registry**: `parsers/registry.py` — `ParserRegistry` class
- **Decorator**: `@ParserRegistry.register` on the class definition
  - **Critical**: the decorator only fires if the module is imported. All parsers must be imported in `parsers/__init__.py`.
- **Base class**: `parsers/base.py` — `BaseRecipeParser(ingredient_parser: BaseIngredientParser)`

### Required methods on every parser

```python
@classmethod
def format_id(cls) -> str:
    """Unique lowercase identifier (e.g. 'mealmaster', 'csv_cookware')."""

@classmethod
def aliases(cls) -> list[str]:
    """Alternate names accepted by the -f flag. Return [] if none."""

@classmethod
def priority(cls) -> int:
    """Detection order — lower = tried first. Specific parsers: 1–30. Fallbacks: 90–100."""

@classmethod
def detect(cls, filepath: str, content_sample: str) -> float:
    """Confidence score 0.0–1.0. Score >= 0.99 causes early exit in registry."""

def parse_content(self, content: str, filepath: str) -> Iterator[Recipe]:
    """Must use yield, not return. Called by parse_file() in base class."""
```

`__init__` pattern:
```python
def __init__(self, ingredient_parser: BaseIngredientParser):
    super().__init__(ingredient_parser)
    self.source_format = "Format Name"
```

Reference implementation to copy from: `parsers/cookware.py`

## Models (`parsers/models.py`)

```python
@dataclass
class Recipe:
    title: str
    categories: List[str]       # list, not a string
    yield_amount: str
    ingredients: List[Ingredient]
    instructions: List[str]     # list of paragraphs/steps, not a single string
    source_file: Optional[str]
    source_format: str
    description: Optional[str]
    url: Optional[str]
    sqlite_table: Optional[str]
    sqlite_id: Optional[str]

@dataclass
class Ingredient:
    raw: str                    # ALWAYS required — set to the original line
    quantity: Optional[str]
    unit: Optional[str]
    name: Optional[str]
    comment: Optional[str]
```

## Adding a New Parser

1. Create `parsers/yourformat.py` inheriting from `BaseRecipeParser`
2. Add `from .yourformat import YourFormatParser` to `parsers/__init__.py`
3. Add `'YourFormatParser'` to `__all__` in `parsers/__init__.py`
4. Add a sample file at `tests/samples/yourfile.ext`
5. Generate expected output (use `--no-nlp` for deterministic results):
   ```bash
   ./venv/bin/python3 convert.py tests/samples/yourfile.ext \
     -o tests/expected/yourfile.ext.json --no-nlp
   ```
6. Run tests:
   ```bash
   ./venv/bin/python3 -m pytest tests/test_conversion.py
   ```

**Why `--no-nlp`**: Forces `RegexIngredientParser` instead of the NLP parser. NLP output is non-deterministic across versions. Always use `--no-nlp` when generating expected test files.

If you change a parser's output, regenerate its expected file with the same command in step 5.

## Test Suite

- `tests/test_conversion.py` — parametrized pytest; runs `convert.py` as a subprocess for each file in `tests/samples/`
- Every sample in `tests/samples/` needs a matching file in `tests/expected/<name>.json`
- Tests normalize `datePublished`, `comment`, and `url` before comparing — those fields won't cause failures

## Key Files

```
parsers/registry.py            - ParserRegistry class, get_parser() dispatcher
parsers/base.py                - BaseRecipeParser, BaseIngredientParser
parsers/models.py              - Recipe, Ingredient dataclasses
parsers/__init__.py            - Import all parsers here to trigger registration
parsers/ingredients.py         - get_ingredient_parser(), NLP + Regex implementations
parsers/units.py               - UNIT_MAP dict + normalize_unit(), 160 unit abbreviations
parsers/cookware.py            - Clean reference parser to copy from
parsers/stubs.py               - Stub parsers: PDF, Image/OCR, Generic CSV
parsers/mixed.py               - MixedFormatParser: delegates to sub-parsers per line
parsers/llm_parser.py          - LLM-based parser (Ollama/OpenAI), manual-only
parsers/sqlite/                - SQLite parser subsystem (sqlite_config.py, sqlite_parser.py)
convert.py                     - CLI entry, SchemaOrgConverter, JSONStreamWriter
dedup.py                       - Standalone dedup tool (MinHash LSH, union-find)
import_to_mealie.py            - REST API importer for Mealie
import_to_tandoor.py           - REST API importer for Tandoor Recipes
update_expected.py             - Regenerate all tests/expected/*.json files
configs/                       - SQLite schema YAML configs for known database layouts
tests/test_conversion.py       - Regression suite
```

## Ingredient Parsing System

`parsers/ingredients.py` provides two implementations behind `BaseIngredientParser`:

- **`RegexIngredientParser`**: Extracts quantity via regex, matches unit from `UNIT_MAP`, remainder becomes name. Deterministic.
- **`NLPIngredientParser`**: Wraps `ingredient-parser-nlp` library. Falls back to regex on error. Non-deterministic across versions.

`get_ingredient_parser(use_nlp=True)` returns NLP if available, else regex. The `--no-nlp` CLI flag forces regex.

`parsers/units.py` has a 160-entry `UNIT_MAP` mapping abbreviations to canonical forms (e.g. `"T"` → `"tablespoon"`, `"t"` → `"teaspoon"`). Case-sensitive check first, then case-insensitive fallback.

## Schema.org Converter (`convert.py`)

`SchemaOrgConverter.convert(recipe: Recipe) -> dict` transforms internal `Recipe` objects to Schema.org JSON-LD:

- `@context`: `"https://schema.org"`, `@type`: `"Recipe"`
- `recipeIngredient`: `PropertyValue` objects (when structured) or plain strings
- `recipeInstructions`: `HowToStep` objects (multi-step) or single string
- `recipeYield`, `recipeCategory`, `keywords`, `datePublished`, `description`, `url`

`JSONStreamWriter` writes a JSON array in streaming fashion with optional chunking (splits at 35K recipes or 50MB).

## SQLite Parser Subsystem

`parsers/sqlite/` handles SQLite recipe databases with arbitrary schemas via YAML config files.

- **`sqlite_config.py`**: Dataclasses for schema definition (`SqliteConfig`, `TableMapping`, `ColumnMapping`), YAML loader, schema validator, auto-detection registry
- **`sqlite_parser.py`**: `SqliteRecipeParser` (priority 25) — reads `.sqlite`/`.db` files, matches against known YAML schemas in `configs/`, builds SQL queries dynamically

### YAML Schema Configs (`configs/`)

Each YAML file defines: database filename pattern, table names, column mappings, optional junction tables (for categories, ingredients), and ingredient quantity lookup tables.

When adding a new SQLite database layout:
1. Create `configs/yourdatabase.yaml` following the existing examples
2. The parser auto-discovers YAML files in `configs/` — no code changes needed

## LLM Parser

`parsers/llm_parser.py` — `LLMRecipeParser` (priority 99, **not auto-registered**).

Sends recipe text to an LLM (Ollama or OpenAI-compatible API) and parses the structured response. Includes a built-in hallucination sanity checker.

**Not used in auto-detection.** Must be explicitly activated via `--llm-config configs/llm_example.yaml`.

The YAML config specifies: API endpoint, model name, prompt template, temperature, and max tokens.

## Standalone Tools

These scripts are independent of the parser system:

- **`dedup.py`**: Recipe deduplication using MinHash LSH and union-find clustering. Reads JSON-LD output, groups near-duplicates, writes deduplicated output. Requires `datasketch`, `numpy`, `unidecode` (not in `requirements.txt`).
- **`import_to_mealie.py`**: Imports JSON-LD recipes into a Mealie instance via REST API.
- **`import_to_tandoor.py`**: Imports JSON-LD recipes into Tandoor Recipes via REST API.
- **`update_expected.py`**: Convenience script — regenerates all `tests/expected/*.json` files using `--no-nlp`.

## Coding Standards

- Python 3.10+ (match/case and `X | Y` unions are fine)
- Mandatory type hints on all function signatures
- Google-style docstrings on classes and non-trivial methods
- `# SPDX-License-Identifier: MIT` as line 1 of every new parser file
- Logging: `logger = logging.getLogger(__name__)` at module level — never `logging.basicConfig()` inside a parser
- No new dependencies without justification. Existing: `ingredient-parser-nlp`, `recipe-scrapers`, `pytest`, `requests`, `pyyaml`

## Common Pitfalls

- **Missing import**: `@ParserRegistry.register` is silent if the module is never imported. Both the import line and the `__all__` entry in `parsers/__init__.py` are required.
- **`return` instead of `yield`**: `parse_content` must be a generator. Using `return [...]` breaks streaming.
- **`print()` in parsers**: Use `logger.debug()` / `logger.warning()`. Never `print()` in production parser code.
- **Inflated `detect()` scores**: Generic/fallback parsers must return low scores (0.01–0.10) so specific parsers win.
- **Hardcoded path separators**: Use `Path(filepath).suffix.lower()` for extension checks.
- **NLP for expected output**: Never generate `tests/expected/` files without `--no-nlp`.

## Known Issues

These are known bugs and inconsistencies. Fix them if you encounter them, but don't break existing tests.

1. **NLP ingredient parser bug**: `parse_ingredient` is imported inside `get_ingredient_parser()` function scope (line 65 of `ingredients.py`) but referenced at module scope in `NLPIngredientParser.parse()` (line 41). Would raise `NameError` on first NLP use. Tests pass only because `--no-nlp` bypasses this path.

2. **`-f` flag choices incomplete**: `convert.py` hardcodes only 11 of 20+ `format_id` values in the argparse `choices` list. Users cannot force-select most parsers via `-f`.

3. **`test_conversion.py`**: Uses bare `python3` instead of `./venv/bin/python3`.

4. **`convert_recipe_file()` multi-recipe mode**: The "multiple recipes per file" fallback path converts but never writes output (recipes are discarded).

5. **`compuchef.py` line 88**: Production `print()` statement — should be `logger.debug()`.

6. **`nyc.py`**: Missing `# SPDX-License-Identifier: MIT` header.
