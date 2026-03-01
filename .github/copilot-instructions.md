# GitHub Copilot Instructions

## Project Implementation Guidelines

This is a modular recipe format converter (Python 3.10+) that converts 20+ recipe formats to Schema.org JSON-LD.

### Parser Registry Pattern

All parsers use `@ParserRegistry.register` decorator and inherit from `BaseRecipeParser` (`parsers/base.py`).

**Required methods on every parser:**
- `format_id(cls) -> str` — unique lowercase ID
- `aliases(cls) -> list[str]` — alternate `-f` flag names; `[]` if none
- `priority(cls) -> int` — lower = tried first; specific parsers 1–30, fallbacks 90–100
- `detect(cls, filepath: str, content_sample: str) -> float` — confidence 0.0–1.0
- `parse_content(self, content: str, filepath: str) -> Iterator[Recipe]` — must `yield`, not `return`

**Registration requires two things in `parsers/__init__.py`:**
1. Import line: `from .yourformat import YourFormatParser`
2. Entry in `__all__`: `'YourFormatParser'`

The decorator is silent if the module is never imported — the parser won't register without the import.

Reference implementation to copy from: `parsers/cookware.py`

### Models (`parsers/models.py`)

```python
Recipe: title, categories: List[str], yield_amount, ingredients: List[Ingredient],
        instructions: List[str], source_file, source_format, description, url,
        sqlite_table, sqlite_id

Ingredient: raw (always required), quantity, unit, name, comment
```

`raw` must always be set. `instructions` and `categories` are lists, not strings.

### Testing

```bash
# Run tests
./venv/bin/python3 -m pytest tests/test_conversion.py

# Generate expected output for a new parser sample
./venv/bin/python3 convert.py tests/samples/YOURFILE \
  -o tests/expected/YOURFILE.json --no-nlp

# Regenerate all expected outputs
./venv/bin/python3 update_expected.py
```

`--no-nlp` is required for expected output generation — NLP parsing is non-deterministic.

Always use `./venv/bin/python3`. Never use bare `python3`.

### Common Mistakes to Avoid

- Using `return` instead of `yield` in `parse_content` — breaks streaming
- Forgetting the `parsers/__init__.py` import — parser silently never registers
- Using `print()` in parsers — use `logger = logging.getLogger(__name__)`
- Generating expected test files without `--no-nlp`
- Adding `# SPDX-License-Identifier: MIT` is required as line 1 of new parser files

---

## Core Guidelines

**Do not create explainer documents or other documentation unless specifically asked to.**

## Documentation Policy

- ❌ DO NOT create README files, guide files, or explanatory markdown documents
- ❌ DO NOT create tutorial files or how-to guides
- ❌ DO NOT create SUMMARY files or overview documents
- ❌ DO NOT create ARCHITECTURE files or design documents
- ❌ DO NOT create CHECKLIST files or verification documents
- ✅ DO create documentation only when the user explicitly requests it

## Implementation Guidelines

When working on code:
1. Modify and implement the code as requested
2. Focus on solving the problem, not explaining it
3. Make changes directly to files using appropriate tools
4. Only output explanations if asked

## Communication

- Be concise in responses
- Don't add lengthy explanations unless requested
- Let the code speak for itself
- Ask clarifying questions if the request is ambiguous, but don't invent details

## Exception Cases

The only exceptions to the no-documentation rule are:
- User explicitly asks for documentation (e.g., "create a guide for...")
- Documentation is part of the codebase's required structure (e.g., setup instructions in existing README)
- Comments in code itself (which are often helpful)

---

**Remember**: Code first, documentation only when asked.
