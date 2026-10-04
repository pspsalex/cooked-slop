# Recipe Format Converter — Agent Instructions

## Commands

Always use the project virtualenv. Never use bare `python3` or `python`.

```bash
./venv/bin/cook [args]                                    # Installed CLI console script
./venv/bin/python3 convert.py [args]                      # Direct entrypoint
./venv/bin/python3 -m pytest tests/ -v
./venv/bin/python3 -m pytest tests/test_conversion.py -v   # regression only
./venv/bin/python3 -m pytest tests/test_detection.py -v    # detection only
```

## Project Structure

```
scripts/
├── pyproject.toml             # PEP 517/621 packaging (cook, recipe-convert, ...)
├── tasks.md                   # Single actionable backlog (all active & archived tasks)
├── convert.py                 # Primary CLI entry point & orchestrator (cook, recipe-convert)
├── requirements.txt           # All dependencies (including optional dedup deps)
├── core/                      # Core conversion pipeline package
│   ├── __init__.py            # Re-exports SchemaOrgConverter, JSONStreamWriter, ui, shard
│   ├── converter.py           # SchemaOrgConverter (JSON-LD transformation)
│   ├── writer.py              # JSONStreamWriter (streaming & chunking output writer)
│   ├── shard.py               # MinHash path bucketing and sharding
│   └── ui.py                  # Colors, progress bar, terminal UI
├── specs/                     # Feature specifications & technical design documents
│   ├── README.md              # Spec guide & frontmatter schema
│   ├── _template.md           # Template for authoring new specs
│   └── done/                  # Completed specs archive
├── configs/                   # YAML configs (<name>.<type>.yaml, with type: property)
│   ├── *.sqlite.yaml          # SQLite schema configs (auto-discovered)
│   ├── *.html.yaml            # HTML XPath layout configs (auto-discovered)
│   ├── *.llm.yaml             # LLM provider configs (llm_example.llm.yaml)
│   └── *.csv.yaml             # CSV layout configs
├── tools/                     # Standalone tools and utilities package
│   ├── __init__.py
│   ├── audit_recipes.py       # Recipe JSON audit & quality inspection
│   ├── dedup.py               # Recipe deduplication (CLI: recipe-dedup)
│   ├── import_to_mealie.py    # Mealie REST importer
│   ├── import_to_tandoor.py   # Tandoor REST importer
│   ├── update_expected.py     # Regenerate expected test outputs
│   └── extract/               # Standalone extraction scripts (vjje, breadbakers, etc.)
│       ├── __init__.py
│       ├── breadbakers.py
│       ├── prn_normalizer.py
│       ├── vjje.py
│       └── ...
├── parsers/
│   ├── __init__.py            # Imports all parsers (triggers @register); defines __all__
│   ├── base.py                # BaseRecipeParser, BaseIngredientParser, get_context_window()
│   ├── models.py              # Recipe, Ingredient dataclasses
│   ├── registry.py            # ParserRegistry (register decorator, get_parser, all_format_names)
│   ├── ingredients.py         # NLP + Regex ingredient parsers, get_ingredient_parser()
│   ├── units.py               # UNIT_MAP dict + normalize_unit() (~160 entries)
│   ├── csv_config.py          # CsvSchema, CsvConfigRegistry (YAML-driven CSV layouts)
│   ├── csv_parser.py          # ConfigurableCsvParser (cookware, 20krecipes, chefs via configs/*.csv.yaml)
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
  - Parser modules in `parsers/` are auto-discovered dynamically via `pkgutil.iter_modules`. Decorating your parser class with `@ParserRegistry.register` is all that's required.
- **Base class**: `parsers/base.py` — `BaseRecipeParser(ingredient_parser: BaseIngredientParser)`
- **Dynamic format list**: `ParserRegistry.all_format_names()` returns every registered `format_id`. The `-f` CLI flag uses this dynamically — no hardcoded choices.

### Required methods on every parser

```python
@classmethod
def format_id(cls) -> str:
    """Unique lowercase identifier (e.g. 'mealmaster', 'csv')."""

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

Reference implementation to copy from: `parsers/accuchef.py` (or add a `configs/<name>.csv.yaml` for CSV layouts)

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

1. Create `parsers/yourformat.py` inheriting from `BaseRecipeParser` and decorate the class with `@ParserRegistry.register`
2. Add a sample file at `tests/samples/yourfile.ext`
3. Generate expected output (use `--no-nlp` for deterministic results):
   ```bash
   ./venv/bin/python3 convert.py tests/samples/yourfile.ext \
     -o tests/expected/yourfile.ext.json --no-nlp
   ```
4. Run tests:
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
| `-v`, `--verbose` | Verbose output (`-v` for conversion/app details, `-vv` for deep NLP debug traces) |
| `-r`, `--recursive` | Process directories recursively |
| `--no-nlp` | Force regex ingredient parser (deterministic) |
| `--debug-nlp` | Explicitly enable detailed NLP ingredient parser debug logging |
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

All YAML configuration files in `configs/` adhere to a **dual identification system**:
1. **Pre-extension naming convention**: `<name>.<type>.yaml` (e.g. `cc-rec.sqlite.yaml`, `bbc.html.yaml`, `llm_example.llm.yaml`, `chefs.csv.yaml`).
2. **Top-level generic `type:` property**: `type: sqlite`, `type: html`, `type: llm`, `type: csv`.

Each SQLite schema file defines: `type: sqlite`, database filename pattern, table names, column mappings, optional junction tables (for categories, ingredients), and ingredient quantity lookup tables.

When adding a new SQLite database layout:
1. Create `configs/yourdatabase.sqlite.yaml` following the existing examples
2. The parser auto-discovers SQLite YAML files in `configs/` — no code changes needed

## HTML Parser Subsystem

`parsers/html_parser.py` + `parsers/html_config.py` handle HTML recipe pages via YAML-driven XPath extraction configs (`type: html`, named `*.html.yaml`).

- **`html_config.py`**: `HtmlConfigRegistry` and `HtmlRecipeSchema` — YAML loader for HTML layout definitions specifying XPath selectors for title, ingredients, instructions, etc.
- **`html_parser.py`**: `HtmlParser` — uses the loaded config to extract recipes from HTML files.
- Activated via `--html-config configs/path_to_config.html.yaml`.

## LLM Parser

`parsers/llm_parser.py` — `LLMRecipeParser` (priority 99, **not auto-registered**).

Sends recipe text to an LLM (Ollama or OpenAI-compatible API) and parses the structured response. Includes a built-in hallucination sanity checker.

**Not used in auto-detection.** Must be explicitly activated via `--llm-config configs/llm_example.llm.yaml`.

The YAML config specifies: `type: llm`, API endpoint, model name, prompt template, temperature, and max tokens.

## Standalone Tools (`tools/`)
 
Standalone scripts are organized under the `tools/` package with console script entry points:
 
- **`tools/dedup.py`** (`recipe-dedup`): Recipe deduplication using MinHash LSH and union-find clustering. Reads JSON-LD output, groups near-duplicates, writes deduplicated output.
- **`tools/audit_recipes.py`**: Recipe JSON inspection and anomaly detection utility.
- **`tools/import_to_mealie.py`**: Imports JSON-LD recipes into a Mealie instance via REST API.
- **`tools/import_to_tandoor.py`**: Imports JSON-LD recipes into Tandoor Recipes via REST API.
- **`tools/update_expected.py`**: Convenience script — regenerates all `tests/expected/*.json` files using `--no-nlp`.
- **`tools/extract/`**: Extraction scripts for raw archives (e.g. `vjje.py`, `breadbakers.py`, `prn_normalizer.py`, `fareshare.py`, `garvick1.py`).

Directory batch conversion is handled natively by `convert.py` (`cook` / `recipe-convert`) with parallel worker pool support (`-w` / `--workers`).

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

- **`return` instead of `yield`**: `parse_content` must be a generator. Using `return [...]` breaks streaming.
- **`print()` in parsers**: Use `logger.debug()` / `logger.warning()`. Never `print()` in production parser code.
- **Inflated `detect()` scores**: Generic/fallback parsers must return low scores (0.01–0.10) so specific parsers win. Score >= 0.99 triggers early exit.
- **Hardcoded path separators**: Use `Path(filepath).suffix.lower()` for extension checks.
- **NLP for expected output**: Never generate `tests/expected/` files without `--no-nlp`.
- **Bare `python3`**: Always use `./venv/bin/python3` or `sys.executable` (in test code). Never bare `python3`.

## Spec-Driven Development Workflow (`tasks.md` & `specs/`)

This repository uses a spec-driven development architecture:
- **`tasks.md`** is the single actionable backlog for bug fixes, code quality, and feature development.
- **`specs/`** houses detailed design specifications (`SPEC-NNN-<slug>.md`) backing non-trivial tasks with raw samples and mapping rules.
- **`specs/done/`** contains completed specifications.

### Golden Rule: Isolated Git Worktrees for Every Work Unit

**Every single task and spec MUST be developed inside a dedicated git worktree, verified, committed, and merged back to `main`.** Never edit or commit directly on `main` for non-trivial tasks.

#### Standard Worktree Lifecycle:
```bash
# 1. Create a clean worktree and feature branch off main
git worktree add -b feat/<task-id>-<slug> .worktrees/<task-id> main

# 2. Change into the worktree directory
cd .worktrees/<task-id>

# 3. Implement subtasks sequentially and verify deterministically
./venv/bin/python3 -m pytest tests/ -v

# 4. Commit using conventional commits
git add <changed-files>
git commit -m "feat(<scope>): descriptive commit message"

# 5. Return to main repository and merge cleanly
cd /path/to/repo
git merge --ff-only feat/<task-id>-<slug>

# 6. Clean up worktree and feature branch
git worktree remove .worktrees/<task-id>
git branch -d feat/<task-id>-<slug>
```

### Working on an Existing Task

When the user asks to "work on a task", "work on next task", or "work on tasks.md":

1. **Pick an unchecked task** from `## Active Tasks` in `tasks.md` (prioritize P0 > P1 > P2).
2. **Consult the linked spec**: If the task references a spec in `specs/`, read the specification file for full architectural context, sample inputs, edge cases, and acceptance criteria.
3. **Spawn isolated worktree**: Create a new worktree following the Golden Rule above (`git worktree add -b feat/<task-id>-<slug> .worktrees/<task-id> main`).
4. **Implement atomic subtasks**: Work through the subtask checklist sequentially inside the worktree.
5. **Code review**: Self-review changes for correctness, project coding standards, error handling, and regressions.
6. **Deterministic verification**: Run the exact verification command listed under the task's `**Verify:**` field (e.g. `./venv/bin/python3 -m pytest tests/ -v`).
7. **Commit & Merge**: Stage changed files, the linked spec (if modified), and `tasks.md`. Commit with a conventional-commit message (`fix:`, `feat:`, `refactor:`, `test:`, `docs:`), merge to `main`, and clean up the worktree.
8. **Update task status**:
   - Check off completed subtasks in `tasks.md` (`- [x]`).
   - When all subtasks for a task are complete, move the task to `## Archive` in `tasks.md`.
   - If the task was backed by a spec, update the spec's frontmatter to `status: done` and move it to `specs/done/`.

### Adding a New Spec & Task

When adding new parsers, HTML configurations, or major components:

1. **Create the spec**: Copy `specs/_template.md` to `specs/SPEC-NNN-<slug>.md` (use next available 3-digit ID).
2. **Define frontmatter & requirements**: Provide YAML frontmatter, raw input samples, field mapping rules, edge cases, and concrete acceptance criteria.
3. **Add task to `tasks.md`**: Under `## Active Tasks`, add a new entry referencing the spec, with priority, impact, verification command, and atomic checkboxes derived from acceptance criteria.
