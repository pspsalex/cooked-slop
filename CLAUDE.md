# Recipe Format Converter — Claude Code Instructions

## Commands

Always use the project virtualenv. Never use bare `python3` or `python`.

```bash
./venv/bin/python3 convert.py [args]
./venv/bin/python3 -m pytest tests/test_conversion.py
./venv/bin/python3 -m pytest tests/test_conversion.py -v   # verbose
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
parsers/registry.py        - ParserRegistry class, get_parser() dispatcher
parsers/base.py            - BaseRecipeParser, BaseIngredientParser
parsers/models.py          - Recipe, Ingredient dataclasses
parsers/__init__.py        - Import all parsers here to trigger registration
parsers/ingredients.py     - get_ingredient_parser(), NLP + Regex implementations
parsers/cookware.py        - Clean reference parser to copy from
convert.py                 - CLI entry, SchemaOrgConverter, JSONStreamWriter
tests/test_conversion.py   - Regression suite
```

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
