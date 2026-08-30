---
id: SPEC-019
title: "Repository Packaging and Tools Reorganization"
tier: 1
type: refactor
priority: P2
status: done
impact: "Adds pyproject.toml with console script entry points; consolidates standalone tools and extract scripts into tools/"
deliverables:
  - pyproject.toml
  - tools/__init__.py
  - tools/batch_convert.py
  - tools/dedup.py
  - tools/import_to_mealie.py
  - tools/import_to_tandoor.py
  - tools/update_expected.py
  - tools/extract/
  - AGENTS.md
---

# Spec: Repository Packaging and Tools Reorganization

## Description

Currently, standalone operational scripts (`batch_convert.py`, `dedup.py`, `import_to_mealie.py`, `import_to_tandoor.py`, `update_expected.py`) and the `extract/` folder sit at the root level alongside core conversion files. Additionally, the repository relies on a bare `requirements.txt` without a `pyproject.toml`. This prevents installing the project in editable mode (`pip install -e .`), lacks dependency groups (core vs. dedup vs. dev), and forces users to invoke scripts via paths rather than clean CLI commands.

This specification:
1. Creates a standard `pyproject.toml` with:
   - CLI console scripts: primary short CLI command `cook` alongside `recipe-convert`
   - Dependencies with optional extras (`[project.optional-dependencies] dedup = ...`, `dev = ...`)
   - Tool configurations (pytest)
2. Reorganizes standalone tools and extraction scripts into a dedicated `tools/` package:
   - `tools/batch_convert.py`
   - `tools/dedup.py`
   - `tools/import_to_mealie.py`
   - `tools/import_to_tandoor.py`
   - `tools/update_expected.py`
   - `tools/extract/` (relocated from `extract/`)
3. Provides thin root forwarding shims to preserve 100% backward compatibility for existing command paths.
4. Updates documentation and tests to reflect the new structure.

## Worktree & Branch Protocol

Following repository golden rules:
```bash
git worktree add -b feat/spec-019-packaging .worktrees/spec-019 main
cd .worktrees/spec-019
```
After verification, commit, merge to `main`, and remove worktree.

---

## Detailed Specification

### 1. `pyproject.toml`

Create `pyproject.toml` following PEP 517/621:

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "cooked-slop"
version = "0.2.0"
description = "Universal recipe format converter to Schema.org JSON-LD"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
dependencies = [
    "ingredient-parser-nlp>=0.1.0",
    "recipe-scrapers>=14.0.0",
    "pyyaml>=6.0",
    "requests>=2.28.0",
]

[project.optional-dependencies]
dedup = [
    "datasketch>=1.6.0",
    "numpy>=1.24.0",
    "unidecode>=1.3.0",
]
dev = [
    "pytest>=8.0.0",
]

[project.scripts]
cook = "convert:main"
recipe-convert = "convert:main"
recipe-batch = "tools.batch_convert:main"
recipe-dedup = "tools.dedup:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

### 2. Tools Consolidation in `tools/`

Create `tools/__init__.py` and relocate root utilities:

```
scripts/
├── tools/
│   ├── __init__.py
│   ├── batch_convert.py
│   ├── dedup.py
│   ├── import_to_mealie.py
│   ├── import_to_tandoor.py
│   ├── update_expected.py
│   └── extract/
│       ├── __init__.py
│       └── breadbakers.py
```

### 3. Backwards Compatibility Shims at Root

To avoid breaking any existing CI scripts, documentation, or user terminal history, create forwarding shims at the original file locations:

```python
# batch_convert.py (root forwarding shim)
#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compatibility shim for tools.batch_convert."""
from tools.batch_convert import main

if __name__ == "__main__":
    main()
```
Repeat for `dedup.py`, `import_to_mealie.py`, `import_to_tandoor.py`, and `update_expected.py`.

### 4. Update Test and Documentation References

- In `tests/test_batch_convert.py`, update imports or paths to refer to `tools.batch_convert` while ensuring the root shim continues to work.
- In `tests/test_breadbakers_extract.py`, update imports to `tools.extract.breadbakers`.
- Update `AGENTS.md` project structure tree and tool descriptions.

---

## Edge Cases

1. **Subprocess Invocations in `test_batch_convert.py`**: Batch conversion tests invoke `convert.py` and `batch_convert.py` via subprocess. Ensure both root shims and new package locations work.
2. **Relative Imports inside `tools/extract/`**: Ensure scripts inside `tools/extract/` properly resolve imports whether run directly or imported as a module.
3. **Editable Installation**: Verify `./venv/bin/pip install -e .` succeeds in the project virtualenv.

---

## Acceptance Criteria

- [x] `pyproject.toml` is created with dependencies, optional extras, and CLI entry points (`cook`, `recipe-convert`).
- [x] `./venv/bin/pip install -e .` installs cleanly into the project virtual environment.
- [x] Standalone scripts and `extract/` directory moved into `tools/`.
- [x] Backwards-compatible root shims exist for all moved scripts.
- [x] `AGENTS.md` updated with new directory layout and CLI command examples.
- [x] All tests pass: `./venv/bin/python3 -m pytest tests/ -v`.

---

## Verification Plan

```bash
# 1. Test editable installation
./venv/bin/pip install -e .

# 2. Test installed console scripts
./venv/bin/cook --help
./venv/bin/recipe-convert --help

# 3. Test backward compatibility of root shims
./venv/bin/python3 batch_convert.py --help
./venv/bin/python3 dedup.py --help

# 4. Run entire test suite
./venv/bin/python3 -m pytest tests/ -v
```
