# Recipe Format Converter — Agent Instructions

## Commands

Always use the project virtualenv. Never use bare `python3` or `python`.

```bash
./venv/bin/python3 convert.py [args]
./venv/bin/python3 -m pytest tests/ -v
./venv/bin/python3 -m pytest tests/test_conversion.py -v   # regression only
./venv/bin/python3 -m pytest tests/test_detection.py -v    # detection only
```

## Project Structure

```
scripts/
├── convert.py                 # CLI entry point + SchemaOrgConverter + JSONStreamWriter
├── import_to_mealie.py        # Mealie REST importer
├── import_to_tandoor.py       # Tandoor REST importer
├── update_expected.py         # Regenerate expected test outputs
├── requirements.txt           # All dependencies (including optional dedup deps)
├── configs/                   # YAML configs (SQLite schemas, LLM, HTML layouts)
│   ├── *.yaml                 # SQLite schema configs (auto-discovered)
│   └── llm_example.yaml       # LLM provider config template
├── extract/                   # Standalone extraction scripts (fareshare, garvick, etc.)
├── parsers/
│   ├── __init__.py            # Imports all parsers (triggers @register); defines __all__
│   ├── base.py                # BaseRecipeParser, BaseIngredientParser, get_context_window()
│   ├── models.py              # Recipe, Ingredient dataclasses
│   ├── registry.py            # ParserRegistry (register decorator, get_parser, all_format_names)
│   ├── ingredients.py         # NLP + Regex ingredient parsers, get_ingredient_parser()
│   ├── units.py               # UNIT_MAP dict + normalize_unit() (~160 entries)
│   ├── cookware.py            # CookwareCSVParser — clean reference implementation
│   ├── mealmaster.py          # MealMasterParser (.mmf, .mm)
│   ├── mastercook.py          # MasterCookParser (.mxp, .mx2)
│   ├── compuchef.py           # CompuChefParser (.ccf)
│   ├── ricette.py             # RicetteParser (Italian text format)
│   ├── ricette_json.py        # RicetteJsonParser (Italian JSON export)
│   ├── ricette_md.py          # RicetteMdParser (Italian Markdown format)
│   ├── edna.py                # EdnaParser (custom text with dash separators)
│   ├── nyc.py                 # NYCParser (Now You're Cooking! exports)
│   ├── recipeml.py            # RecipeMLParser (XML-based RecipeML)
│   ├── microcook.py           # MicroCookParser
│   ├── twentykrecipes.py      # TwentyKRecipesParser
│   ├── vitt.py                # VittRecipesParser
│   ├── two_col.py             # TwoColParser (two-column layouts)
│   ├── generic.py             # GenericTextParser (fallback for .txt)
│   ├── generic_md.py          # GenericMdParser (Markdown recipe files)
│   ├── schemaorg.py           # SchemaOrgParser (JSON-LD re-import)
│   ├── html_config.py         # HtmlConfigRegistry, HtmlRecipeSchema (YAML-driven)
│   ├── html_parser.py         # HtmlParser (XPath-based, config-driven)
│   ├── mixed.py               # MixedFormatParser (delegates to sub-parsers per section)
│   ├── stubs.py               # PdfParser, ImageParser, CsvParser (stubs)
│   ├── llm_parser.py          # LLMRecipeParser (Ollama/OpenAI, not auto-registered)
│   └── sqlite/                # SQLite parser subsystem
│       ├── sqlite_config.py   # Schema dataclasses, YAML registry, auto-detection
│       └── sqlite_parser.py   # SqliteRecipeParser (priority 25)
└── tests/
    ├── test_conversion.py     # Parametrized regression suite
    ├── test_detection.py      # Format detection + sliding window tests
    ├── samples/               # Input files (one per format)
    └── expected/              # Expected JSON output (generated with --no-nlp)
```

## Architecture — Parser Registry

All parsers use the Registry Pattern via `ParserRegistry` in `parsers/registry.py`.

- **Decorator**: `@ParserRegistry.register` on the class definition
  - **Critical**: the decorator only fires when the module is imported. All parsers **must** be imported in `parsers/__init__.py` and listed in `__all__`.
- **Base class**: `parsers/base.py` — `BaseRecipeParser(ingredient_parser: BaseIngredientParser)`
- **Dynamic format list**: `ParserRegistry.all_format_names()` returns all `format_id` + `aliases` across registered parsers. The `-f` CLI flag uses this dynamically — no hardcoded choices.

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
    title: str = ''
    categories: List[str] = field(default_factory=list)   # list, not a string
    yield_amount: str = ''
    ingredients: List[Ingredient] = field(default_factory=list)
    instructions: List[str] = field(default_factory=list)  # list of paragraphs/steps
    source_file: Optional[str] = None
    source_format: str = 'Unknown'
    sqlite_table: Optional[str] = None
    sqlite_id: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None

@dataclass
class Ingredient:
    raw: str                    # ALWAYS required — set to the original line
    quantity: Optional[str] = None
    unit: Optional[str] = None
    name: Optional[str] = None
    comment: Optional[str] = None
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
   ./venv/bin/python3 -m pytest tests/ -v
   ```

**Why `--no-nlp`**: Forces `RegexIngredientParser` instead of the NLP parser. NLP output is non-deterministic across versions. Always use `--no-nlp` when generating expected test files.

If you change a parser's output, regenerate its expected file with the same command in step 5, or run `./venv/bin/python3 update_expected.py` to regenerate all expected files.

## CLI Flags (`convert.py`)

| Flag | Description |
|------|-------------|
| `-o`, `--output` | Output file or directory path |
| `-f`, `--format` | Override auto-detection (choices populated dynamically from registry) |
| `-v`, `--verbose` | Verbose output |
| `-r`, `--recursive` | Process directories recursively |
| `--no-nlp` | Force regex ingredient parser (deterministic) |
| `--chunk` | Split large output into chunked part-files (35K recipes or 50MB) |
| `--shard` | Shard output into MinHash-bucketed subdirectories (xx/yy/file.json) |
| `--multiple-per-file` | Write multiple recipes into a single JSON file |
| `--add-date` | Include `datePublished` in output JSON |
| `--llm-config CONFIG` | Use LLM parser instead of auto-detection |
| `--html-config CONFIG` | Specify HTML XPath layout YAML config |
| `--debug-sql` | Show SQL queries at TRACE level (SQLite parser) |

## Test Suite

- **`tests/test_conversion.py`** — parametrized pytest; runs `convert.py` as a subprocess (via `sys.executable`) for each file in `tests/samples/`. Includes a `test_sharded_conversion` test for `--shard` mode.
- **`tests/test_detection.py`** — unit tests for format detection logic, sliding window detection, and multi-recipe section splitting.
- Every sample in `tests/samples/` needs a matching file in `tests/expected/<name>.json`
- Tests normalize `datePublished`, `comment`, and `url` before comparing — those fields won't cause failures

## Ingredient Parsing System

`parsers/ingredients.py` provides two implementations behind `BaseIngredientParser`:

- **`RegexIngredientParser`**: Extracts quantity via regex, matches unit from `UNIT_MAP`, remainder becomes name. Deterministic.
- **`NLPIngredientParser`**: Wraps `ingredient-parser-nlp` library. Falls back to regex on error. Non-deterministic across versions. Import is guarded with a top-level `try/except` — `HAS_NLP_PARSER` flag controls availability.

`get_ingredient_parser(use_nlp=True)` returns NLP if available, else regex. The `--no-nlp` CLI flag forces regex.

`parsers/units.py` has a ~160-entry `UNIT_MAP` mapping abbreviations to canonical forms (e.g. `"T"` → `"tablespoon"`, `"t"` → `"teaspoon"`). Case-sensitive check first, then case-insensitive fallback.

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

## HTML Parser Subsystem

`parsers/html_parser.py` + `parsers/html_config.py` handle HTML recipe pages via YAML-driven XPath extraction configs.

- **`html_config.py`**: `HtmlConfigRegistry` and `HtmlRecipeSchema` — YAML loader for HTML layout definitions specifying XPath selectors for title, ingredients, instructions, etc.
- **`html_parser.py`**: `HtmlParser` — uses the loaded config to extract recipes from HTML files.
- Activated via `--html-config path/to/config.yaml`.

## LLM Parser

`parsers/llm_parser.py` — `LLMRecipeParser` (priority 99, **not auto-registered**).

Sends recipe text to an LLM (Ollama or OpenAI-compatible API) and parses the structured response. Includes a built-in hallucination sanity checker.

**Not used in auto-detection.** Must be explicitly activated via `--llm-config configs/llm_example.yaml`.

The YAML config specifies: API endpoint, model name, prompt template, temperature, and max tokens.

## Standalone Tools

These scripts are independent of the parser system:

- **`dedup.py`**: Recipe deduplication using MinHash LSH and union-find clustering. Reads JSON-LD output, groups near-duplicates, writes deduplicated output.
- **`import_to_mealie.py`**: Imports JSON-LD recipes into a Mealie instance via REST API.
- **`import_to_tandoor.py`**: Imports JSON-LD recipes into Tandoor Recipes via REST API.
- **`update_expected.py`**: Convenience script — regenerates all `tests/expected/*.json` files using `--no-nlp`.

## Coding Standards

- Python 3.10+ (match/case and `X | Y` unions are fine)
- Mandatory type hints on all function signatures
- Google-style docstrings on classes and non-trivial methods
- `# SPDX-License-Identifier: MIT` as line 1 of every new `.py` file
- Logging: `logger = logging.getLogger(__name__)` at module level — never `logging.basicConfig()` inside a parser
- No `print()` in parser code — use `logger.debug()` / `logger.warning()`
- No new dependencies without justification

### Dependencies (`requirements.txt`)

Core: `ingredient-parser-nlp`, `recipe-scrapers`, `pytest`, `requests`, `pyyaml`
Optional (dedup): `datasketch`, `numpy`, `unidecode`

## Common Pitfalls

- **Missing import in `__init__.py`**: `@ParserRegistry.register` is silent if the module is never imported. Both the import line and the `__all__` entry in `parsers/__init__.py` are required.
- **`return` instead of `yield`**: `parse_content` must be a generator. Using `return [...]` breaks streaming.
- **`print()` in parsers**: Use `logger.debug()` / `logger.warning()`. Never `print()` in production parser code.
- **Inflated `detect()` scores**: Generic/fallback parsers must return low scores (0.01–0.10) so specific parsers win. Score >= 0.99 triggers early exit.
- **Hardcoded path separators**: Use `Path(filepath).suffix.lower()` for extension checks.
- **NLP for expected output**: Never generate `tests/expected/` files without `--no-nlp`.
- **Bare `python3`**: Always use `./venv/bin/python3` or `sys.executable` (in test code). Never bare `python3`.

## Working on Tasks (`tasks.json`)

When the user asks to "work on a task" or "work on tasks.json":

1. **Pick a random task** from the `"not done"` tasks in `tasks.json` (prefer higher priority: P0 > P1 > P2)
2. **Implement** the fix/feature following all subtasks
3. **Code review** — review the changes for correctness, style, edge cases, and regressions
4. **Fix any issues** found during review
5. **Run tests** — `./venv/bin/python3 -m pytest tests/ -v`
6. **Commit** — stage changed files and commit with a conventional-commit message (`fix:`, `feat:`, `refactor:`, etc.)
7. **Update `tasks.json`** — mark the task and all its subtasks as `"done"`
