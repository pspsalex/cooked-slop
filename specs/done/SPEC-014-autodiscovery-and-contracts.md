---
id: SPEC-014
title: "Parser Auto-Discovery and Contract Hardening"
tier: 1
type: refactor
priority: P0
status: done
impact: "Eliminates manual __init__.py registration; hardens all 22+ parsers against contract violations"
deliverables:
  - parsers/__init__.py
  - parsers/registry.py
  - parsers/base.py
  - AGENTS.md
---

# Spec: Parser Auto-Discovery and Contract Hardening

## Description

Currently, registering a parser requires a fragile triple-handshake documented in `AGENTS.md`:
1. Annotating the parser class with `@ParserRegistry.register`
2. Manually adding `from .my_parser import MyParser` to `parsers/__init__.py`
3. Adding `'MyParser'` to `__all__` in `parsers/__init__.py`

If any step is missed, the parser silently fails to register. Furthermore, Python provides no compile-time interface enforcement: parsers that return lists instead of yielding generators, or that fail to implement `format_id()` or `detect()`, fail unpredictably at runtime. Finally, `ParserRegistry.get_parser()` swallows all exceptions during detection with a bare `except Exception: pass`, hiding parser bugs, while `parsers/base.py` uses raw `print()` calls for tracebacks.

This specification implements:
1. **Dynamic auto-discovery** in `parsers/__init__.py` using `pkgutil.iter_modules` to import all parser modules automatically.
2. **Runtime contract validation** in `ParserRegistry.register()` to enforce required methods and generator behavior.
3. **Robust error logging** in `ParserRegistry.get_parser()` and `parsers/base.py`, replacing silent swallows and raw `print()` calls with structured `logger` invocations.
4. **Documentation updates** in `AGENTS.md`.

## Worktree & Branch Protocol

Following repository golden rules:
```bash
git worktree add -b feat/spec-014-autodiscovery .worktrees/spec-014 main
cd .worktrees/spec-014
```
After verification, commit, merge to `main`, and remove worktree.

---

## Detailed Specification

### 1. `parsers/__init__.py`: Dynamic Auto-Discovery

Replace the hardcoded manual imports of individual parser classes with dynamic package module iteration while preserving core public API exports.

```python
# SPDX-License-Identifier: MIT
import importlib
import pkgutil
from pathlib import Path

# Explicit core exports
from .models import Recipe, Ingredient
from .base import BaseIngredientParser, BaseRecipeParser
from .ingredients import get_ingredient_parser
from .registry import ParserRegistry

# Auto-discover and import all modules in parsers/ so @ParserRegistry.register fires
_package_dir = str(Path(__file__).parent)
for _, module_name, is_pkg in pkgutil.iter_modules([_package_dir]):
    # Skip private modules or subpackages that handle their own initialization
    if not module_name.startswith('_'):
        importlib.import_module(f'.{module_name}', __package__)

# Explicitly discover sqlite parser subpackage
try:
    importlib.import_module('.sqlite', __package__)
except ImportError:
    pass

__all__ = [
    'Recipe',
    'Ingredient',
    'BaseIngredientParser',
    'BaseRecipeParser',
    'get_ingredient_parser',
    'ParserRegistry',
]
```

### 2. `parsers/registry.py`: Contract Validation & Detection Logging

#### Contract Validation
In `ParserRegistry.register`, inspect the class before registering:
- Must subclass `BaseRecipeParser`.
- Must implement `@classmethod` `format_id(cls) -> str`.
- Must implement `@classmethod` `priority(cls) -> int`.
- Must implement `@classmethod` `detect(cls, filepath, content_sample) -> float`.
- Must implement generator `parse_content(self, content, filepath)`: verify using `inspect.isgeneratorfunction(parser_cls.parse_content)`.
- If invalid, raise `TypeError(f"Parser '{parser_cls.__name__}' violates parser contract: {reason}")`.

```python
import inspect
import logging

logger = logging.getLogger(__name__)

@classmethod
def register(cls, parser_cls: Type[BaseRecipeParser]) -> Type[BaseRecipeParser]:
    """Decorator to register a parser class with runtime contract validation."""
    if not issubclass(parser_cls, BaseRecipeParser):
        raise TypeError(f"{parser_cls.__name__} must subclass BaseRecipeParser")

    for method_name in ('format_id', 'priority', 'detect'):
        if not hasattr(parser_cls, method_name) or not callable(getattr(parser_cls, method_name)):
            raise TypeError(f"{parser_cls.__name__} must implement classmethod '{method_name}()'")

    if not inspect.isgeneratorfunction(parser_cls.parse_content):
        raise TypeError(
            f"{parser_cls.__name__}.parse_content must be a generator function (using 'yield', not 'return')"
        )

    # Avoid duplicate registrations if module is reloaded
    if parser_cls not in cls._parsers:
        cls._parsers.append(parser_cls)
        cls._parsers.sort(key=lambda p: p.priority())

    return parser_cls
```

#### Diagnostic Logging in `get_parser()`
In `get_parser()`, replace silent exception swallowing:
```python
        for p_cls in cls._parsers:
            try:
                score = p_cls.detect(filepath, sample)
                if score > best_score:
                    best_score = score
                    best_parser_cls = p_cls
                    if score >= 0.99:
                        break
            except Exception as e:
                logger.debug(
                    "Parser %s.detect() raised exception on %s: %s",
                    p_cls.__name__, filepath, e, exc_info=True
                )
```

### 3. `parsers/base.py`: Clean Up Error Handling

Replace raw `print(traceback.format_exc())` in `BaseRecipeParser.parse_file()` with:
```python
        except Exception as e:
            logger.error("Error reading %s: %s", filepath, e, exc_info=True)
            return
```

### 4. `AGENTS.md`: Update Workflow Documentation

Update sections:
- **Adding a New Parser**: Step 1 (create file in `parsers/`), Step 2 (ensure `@ParserRegistry.register` is on class). Document that `parsers/__init__.py` does not need manual edits.
- **Common Pitfalls**: Remove "Missing import in `__init__.py`" pitfall.

---

## Edge Cases

1. **Subpackages (e.g. `parsers/sqlite/`)**: `pkgutil.iter_modules` identifies `sqlite` as a package (`is_pkg=True`). Ensure `parsers/sqlite` is imported so `SqliteRecipeParser` registers.
2. **Circular Imports**: `BaseRecipeParser` and `BaseIngredientParser` must be imported before `pkgutil.iter_modules` begins dynamically importing parser modules.
3. **Idempotent Registration**: Guard against double registration if a module is explicitly imported elsewhere by checking `if parser_cls not in cls._parsers`.

---

## Acceptance Criteria

- [ ] `parsers/__init__.py` auto-discovers and imports all parser modules dynamically.
- [ ] Manual imports of individual parser classes in `parsers/__init__.py` are removed while public API symbols (`Recipe`, `Ingredient`, `BaseRecipeParser`, `ParserRegistry`, etc.) remain exported.
- [ ] `ParserRegistry.register` raises `TypeError` if a registered class does not subclass `BaseRecipeParser` or does not use `yield` in `parse_content`.
- [ ] Detection failures in `ParserRegistry.get_parser()` log debug diagnostics instead of silently passing.
- [ ] `parsers/base.py` contains no raw `print()` statements.
- [ ] `AGENTS.md` instructions updated to reflect the simplified single-step registration.
- [ ] All existing regression and detection tests pass: `./venv/bin/python3 -m pytest tests/ -v`.

---

## Verification Plan

```bash
# 1. Run all pytest tests
./venv/bin/python3 -m pytest tests/ -v

# 2. Verify all registered parsers are loaded dynamically
./venv/bin/python3 -c "from parsers import ParserRegistry; print('Registered parsers:', len(ParserRegistry._parsers)); assert len(ParserRegistry._parsers) >= 20"

# 3. Verify contract check rejects non-generator
./venv/bin/python3 -c "
from parsers import BaseRecipeParser, ParserRegistry
try:
    @ParserRegistry.register
    class BadParser(BaseRecipeParser):
        @classmethod
        def format_id(cls): return 'bad'
        @classmethod
        def priority(cls): return 50
        @classmethod
        def detect(cls, fp, c): return 0.0
        def parse_content(self, c, fp): return []
    assert False, 'Should have raised TypeError'
except TypeError:
    print('Contract validation correctly rejected non-generator parse_content')
"
```
