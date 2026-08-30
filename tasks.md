# Project Backlog

> Pick an unchecked task (P0 first), read its linked spec if any,
> implement, verify, commit, and check it off.

## Active Tasks

### SPEC-014: Parser Auto-Discovery and Contract Hardening
- **Spec:** [SPEC-014-autodiscovery-and-contracts.md](specs/SPEC-014-autodiscovery-and-contracts.md)
- **Priority:** P0 | **Tier:** 1 | **Type:** refactor | **Impact:** All 22+ parsers
- **Verify:** `./venv/bin/python3 -m pytest tests/ -v`
- [ ] Create worktree: `git worktree add -b feat/spec-014-autodiscovery .worktrees/spec-014 main`
- [ ] Implement dynamic module iteration via `pkgutil.iter_modules` in `parsers/__init__.py`
- [ ] Add runtime contract checks (generator `parse_content`, required classmethods) in `ParserRegistry.register()`
- [ ] Replace silent `except Exception: pass` in `ParserRegistry.get_parser()` with `logger.debug`
- [ ] Replace `print(traceback.format_exc())` in `parsers/base.py` with `logger.error`
- [ ] Update `AGENTS.md` parser registration instructions
- [ ] Verify test suite passes, commit, merge to `main`, and remove worktree

### SPEC-015: Modular CLI and Conversion Architecture
- **Spec:** [SPEC-015-modular-conversion-pipeline.md](specs/SPEC-015-modular-conversion-pipeline.md)
- **Priority:** P0 | **Tier:** 1 | **Type:** refactor | **Impact:** Core CLI and JSON-LD pipeline
- **Verify:** `./venv/bin/python3 -m pytest tests/ -v`
- [ ] Create worktree: `git worktree add -b feat/spec-015-modular-cli .worktrees/spec-015 main`
- [ ] Extract `SchemaOrgConverter` into `converter.py`
- [ ] Extract `JSONStreamWriter` into `writer.py`
- [ ] Extract MinHash sharding helpers into `shard.py`
- [ ] Extract `Colors` and `print_progress_bar` into `ui.py`
- [ ] Refactor `convert.py` to import from extracted modules with backward-compatible re-exports
- [ ] Verify full test suite passes, commit, merge to `main`, and remove worktree

### SPEC-016: Comprehensive Unit Test Suite
- **Spec:** [SPEC-016-unit-test-suite.md](specs/SPEC-016-unit-test-suite.md)
- **Priority:** P1 | **Tier:** 1 | **Type:** test | **Impact:** Test coverage and developer velocity
- **Verify:** `./venv/bin/python3 -m pytest tests/unit/ -v`
- [ ] Create worktree: `git worktree add -b feat/spec-016-unit-tests .worktrees/spec-016 main`
- [ ] Create `tests/unit/__init__.py`
- [ ] Create `tests/unit/test_converter.py` testing `SchemaOrgConverter.convert()` across data shapes
- [ ] Create `tests/unit/test_writer.py` testing `JSONStreamWriter` empty/streaming/chunking
- [ ] Create `tests/unit/test_ingredient_parser.py` testing `RegexIngredientParser` fractions/ranges/comments
- [ ] Create `tests/unit/test_registry.py` testing auto-discovery, priority, and contract validation
- [ ] Verify both unit and regression suites pass, commit, merge to `main`, and remove worktree

### SPEC-017: Dynamic File Extension Registry and Directory Traversal
- **Spec:** [SPEC-017-dynamic-extension-registry.md](specs/SPEC-017-dynamic-extension-registry.md)
- **Priority:** P1 | **Tier:** 1 | **Type:** refactor | **Impact:** Directory traversal across all supported formats
- **Verify:** `./venv/bin/python3 -m pytest tests/ -v`
- [ ] Create worktree: `git worktree add -b feat/spec-017-dynamic-extensions .worktrees/spec-017 main`
- [ ] Add `supported_extensions()` classmethod to `BaseRecipeParser`
- [ ] Implement `supported_extensions()` on all parser subclasses (including `.nyc`, `.xml`, `.json`)
- [ ] Implement `ParserRegistry.supported_extensions()` aggregation
- [ ] Refactor `process_directory()` in `convert.py` to query registry
- [ ] Add `--ext` CLI option to allow custom extension filtering
- [ ] Verify directory scanning discovers all formats, commit, merge to `main`, and remove worktree

### SPEC-018: Spec Framework Standards and Validation
- **Spec:** [SPEC-018-spec-framework-evolution.md](specs/SPEC-018-spec-framework-evolution.md)
- **Priority:** P2 | **Tier:** 0 | **Type:** review | **Impact:** All specifications and templates
- **Verify:** `./venv/bin/python3 -m pytest tests/test_specs.py -v`
- [ ] Create worktree: `git worktree add -b feat/spec-018-spec-standards .worktrees/spec-018 main`
- [ ] Add `## Detection Contract` and `## Golden Output` sections to `specs/_template.md`
- [ ] Update `specs/README.md` and `AGENTS.md` with guidelines on Golden Output and detection contracts
- [ ] Create `tests/test_specs.py` automated spec validator
- [ ] Verify all specs pass validation, commit, merge to `main`, and remove worktree

### SPEC-019: Repository Packaging and Tools Reorganization
- **Spec:** [SPEC-019-packaging-and-tools-reorg.md](specs/SPEC-019-packaging-and-tools-reorg.md)
- **Priority:** P2 | **Tier:** 1 | **Type:** refactor | **Impact:** Packaging, CLI command, and tools organization
- **Verify:** `./venv/bin/python3 -m pytest tests/ -v`
- [ ] Create worktree: `git worktree add -b feat/spec-019-packaging .worktrees/spec-019 main`
- [ ] Create `pyproject.toml` with console script `cook` (and alias `recipe-convert`), dependencies, and extras
- [ ] Move root scripts (`batch_convert.py`, `dedup.py`, `import_to_mealie.py`, `import_to_tandoor.py`, `update_expected.py`) to `tools/`
- [ ] Move `extract/` directory to `tools/extract/`
- [ ] Create backward-compatible root forwarding shims for moved tools
- [ ] Verify `pip install -e .` and console scripts work
- [ ] Verify test suite passes, commit, merge to `main`, and remove worktree


---

## Archive

<details>
<summary>Completed specs (13 items)</summary>

### SPEC-001: Batch Conversion Runner ✅
- **Spec:** [SPEC-001-batch-runner.md](specs/done/SPEC-001-batch-runner.md)
- **Priority:** P0 | **Tier:** 1 | **Type:** script | **Impact:** ~6,500 files
- [x] Create `batch_convert.py` with subprocess-based conversion pipeline
- [x] Implement `--dry-run`, `--resume`, `--dir`, `--workers` flags
- [x] Generate results CSV with file/parser/status/error columns
- [x] Handle timeouts, encoding errors, skip list
- [x] Test on full ToDo directory

### SPEC-002: cs.cmu Usenet Recipe Archive HTML Config ✅
- **Spec:** [SPEC-002-cscmu.md](specs/done/SPEC-002-cscmu.md)
- **Priority:** P0 | **Tier:** 2 | **Type:** html-config | **Impact:** ~735 files
- [x] Create `configs/cscmu.yaml` conforming to HtmlRecipeSchema
- [x] Auto-detection scores cs.cmu files >= 0.5
- [x] Conversion succeeds on sample files
- [x] Full test suite passes

### SPEC-003: Garvick.com Recipe Collection HTML Config ✅
- **Spec:** [SPEC-003-garvick.md](specs/done/SPEC-003-garvick.md)
- **Priority:** P2 | **Tier:** 2 | **Type:** html-config | **Impact:** 27 files
- [x] Create `configs/garvick.yaml`
- [x] Multi-recipe extraction from compilation pages
- [x] Test conversion on sample files

### SPEC-004: Macropolis Recipe Collection ✅
- **Spec:** [SPEC-004-macropolis.md](specs/done/SPEC-004-macropolis.md)
- **Priority:** P1 | **Tier:** 2 | **Type:** html-config
- [x] Implementation complete

### SPEC-005: McNalley Recipe Collection ✅
- **Spec:** [SPEC-005-mcnalley.md](specs/done/SPEC-005-mcnalley.md)
- **Priority:** P1 | **Tier:** 2 | **Type:** html-config
- [x] Implementation complete

### SPEC-006: Mexican Recipe Collection ✅
- **Spec:** [SPEC-006-mexican.md](specs/done/SPEC-006-mexican.md)
- **Priority:** P1 | **Tier:** 2 | **Type:** html-config
- [x] Implementation complete

### SPEC-007: TopSecret Recipe Collection ✅
- **Spec:** [SPEC-007-topsecret.md](specs/done/SPEC-007-topsecret.md)
- **Priority:** P1 | **Tier:** 2 | **Type:** html-config
- [x] Implementation complete

### SPEC-008: Bread-Bakers Mailing List Extract Script ✅
- **Spec:** [SPEC-008-breadbakers.md](specs/done/SPEC-008-breadbakers.md)
- **Priority:** P0 | **Tier:** 3 | **Type:** script | **Impact:** ~11,538 files
- [x] Create `extract/breadbakers.py`
- [x] RFC header stripping, quotation block removal
- [x] Recipe vs non-recipe classification
- [x] Failure report generation

### SPEC-009: Mr. Boston Drinks Database Parser ✅
- **Spec:** [SPEC-009-drinksdb.md](specs/done/SPEC-009-drinksdb.md)
- **Priority:** P2 | **Tier:** 3 | **Type:** parser | **Impact:** 1 file (~992 recipes)
- [x] Parser for fixed-width column drink database format
- [x] Test sample and expected output

### SPEC-010: FromScratch Recipe Collection ✅
- **Spec:** [SPEC-010-fromscratch.md](specs/done/SPEC-010-fromscratch.md)
- **Priority:** P1 | **Tier:** 3 | **Type:** parser
- [x] Implementation complete

### SPEC-011: InfoMac Recipe Collection ✅
- **Spec:** [SPEC-011-infomac.md](specs/done/SPEC-011-infomac.md)
- **Priority:** P1 | **Tier:** 3 | **Type:** parser
- [x] Implementation complete

### SPEC-012: RCP Recipe Collection ✅
- **Spec:** [SPEC-012-rcp.md](specs/done/SPEC-012-rcp.md)
- **Priority:** P1 | **Tier:** 3 | **Type:** parser
- [x] Implementation complete

### SPEC-013: Code Review Fixes — Unpushed Commits ✅
- **Spec:** [SPEC-013-review-fixes.md](specs/done/SPEC-013-review-fixes.md)
- **Priority:** P1 | **Type:** review | **Impact:** 6 fixes across 4 files
- [x] Fix 1: Missing KeyboardInterrupt handler in convert.py
- [x] Fix 2: Non-verbose single-file mode progress indicator
- [x] Fix 3: batch_convert.py timeout parameter passthrough
- [x] Fix 4: llm_parser.py hardcoded localhost fallback URL
- [x] Fix 5: html_config.py extract magic strings to constant
- [x] Fix 6: base.py get_display_name() dead code removal

</details>

<details>
<summary>Completed tasks — original backlog (25 items)</summary>

### BUG-001: Fix NLP ingredient parser NameError ✅
- **Priority:** P0 | **Category:** Critical Bugs
- **Files:** `parsers/ingredients.py`
- [x] Move `from ingredient_parser import parse_ingredient` to module-level with try/except guard
- [x] Verify NLP parsing works without --no-nlp
- [x] Ensure --no-nlp still works and tests pass

### BUG-002: Fix convert_recipe_file() multi-recipe mode — output never written ✅
- **Priority:** P0 | **Category:** Critical Bugs
- **Files:** `convert.py`
- [x] Locate the multi-recipe fallback branch in convert_recipe_file()
- [x] Wire converted recipes into JSONStreamWriter output
- [x] Add a test sample with multiple recipes and verify output is written

### BUG-003: Fix mixed.py crash when NYCParser detected in mixed file ✅
- **Priority:** P0 | **Category:** Critical Bugs
- **Files:** `parsers/mixed.py`, `parsers/nyc.py`
- [x] Add parse_buffer() method to NYCParser
- [x] Add NYC section to tests/samples/mixed_test.txt and regenerate expected output
- [x] Run tests to verify mixed-format parsing with NYC content

### BUG-004: Replace print() statements with logger calls in parsers ✅
- **Priority:** P0 | **Category:** Critical Bugs
- **Files:** `parsers/compuchef.py`, `parsers/ricette_json.py`
- [x] Add logger to compuchef.py, replace print() with logger.debug()
- [x] Replace ricette_json.py print() with logger.warning(), remove unused import sys

### BUG-005: Fix -f flag: dynamically populate choices from ParserRegistry ✅
- **Priority:** P1 | **Category:** Critical Bugs
- **Files:** `convert.py`, `parsers/registry.py`
- [x] Add all_format_names() method to ParserRegistry
- [x] Replace hardcoded choices list with dynamic call to registry
- [x] Add aliases to parsers that are missing them

### BUG-006: Fix compuchef.py parse_buffer() return type annotation ✅
- **Priority:** P1 | **Category:** Critical Bugs
- **Files:** `parsers/compuchef.py`
- [x] Change return annotation to `tuple[Optional[Recipe], int]`

### BUG-007: Fix generic.py yield regex — too narrow capture ✅
- **Priority:** P1 | **Category:** Critical Bugs
- **Files:** `parsers/generic.py`
- [x] Fix regex to capture full yield string (e.g., '12 servings')

### BUG-008: Fix vitt.py character removal mismatch (\\u008d vs \\u200d) ✅
- **Priority:** P1 | **Category:** Critical Bugs
- **Files:** `parsers/vitt.py`
- [x] Determine correct behavior and fix code/docstring

### QUAL-001: Add SPDX license header to nyc.py ✅
- **Priority:** P1 | **Category:** Code Quality
- [x] Add `# SPDX-License-Identifier: MIT` as line 1

### QUAL-002: Fix missing/incomplete type hints across parsers ✅
- **Priority:** P1 | **Category:** Code Quality
- [x] Fix __init__ type hints in nyc, vitt, ricette_md, ricette_json, twentykrecipes, stubs
- [x] Add return type to stubs.py _detect_delimiter()
- [x] Add type hints to recipeml.py helper functions

### QUAL-003: Remove unnecessary re-imports inside detect() methods ✅
- **Priority:** P2 | **Category:** Code Quality
- [x] Remove redundant imports from detect() in 7 parser files

### QUAL-004: Add module-level loggers to parsers missing them ✅
- **Priority:** P1 | **Category:** Code Quality
- [x] Add logger to compuchef.py, nyc.py, vitt.py, twentykrecipes.py

### QUAL-005: Add __init__.py to parsers/sqlite/ package ✅
- **Priority:** P1 | **Category:** Code Quality
- [x] Create parsers/sqlite/__init__.py with appropriate imports

### QUAL-006: Remove unused variable in twentykrecipes.py ✅
- **Priority:** P2 | **Category:** Code Quality
- [x] Remove unused 'lines' variable

### QUAL-007: Add docstrings to generic.py class and methods ✅
- **Priority:** P2 | **Category:** Code Quality
- [x] Add class-level and method docstrings

### TEST-001: Fix test_conversion.py to use venv Python ✅
- **Priority:** P1 | **Category:** Test Coverage
- [x] Change subprocess call to use sys.executable

### TEST-002: Add HTML test sample and expected output ✅
- **Priority:** P2 | **Category:** Test Coverage
- [x] Create minimal HTML file with Schema.org Recipe markup
- [x] Generate expected output with --no-nlp

### TEST-003: Add generic text parser test sample ✅
- **Priority:** P2 | **Category:** Test Coverage
- [x] Create plain-text recipe file for GenericTextParser

### TEST-004: Add generic CSV parser test sample ✅
- **Priority:** P2 | **Category:** Test Coverage
- [x] Create generic CSV recipe file

### TEST-005: Add SQLite parser test sample ✅
- **Priority:** P2 | **Category:** Test Coverage
- [x] Create minimal SQLite database with recipe data and matching YAML config

### CLI-001: Verify update_expected.py --no-nlp consistency ✅
- **Priority:** P1 | **Category:** CLI / UX
- [x] Verify update_expected.py passes --no-nlp
- [x] Verify all expected files are unchanged after regeneration

### ARCH-001: Add CI/CD workflow for automated testing ✅
- **Priority:** P1 | **Category:** Architecture
- [x] Create .github/workflows/test.yml with Python 3.10+ matrix
- [x] Install dependencies and run pytest with --no-nlp

### ARCH-002: Add dedup.py dependencies to requirements.txt ✅
- **Priority:** P2 | **Category:** Architecture
- [x] Add dedup dependencies (datasketch, numpy, unidecode)

### ARCH-003: Add nux/ to .gitignore or integrate properly ✅
- **Priority:** P2 | **Category:** Architecture
- [x] Add nux/ to .gitignore

### FEAT-001: Implement schema.org pass-through parser ✅
- **Priority:** P2 | **Category:** New Features
- [x] Create parsers/schemaorg.py with detect() and parse_content()
- [x] Register in parsers/__init__.py
- [x] Add test sample and expected output

### FEAT-002: Improve CSV/JSON format detection heuristics ✅
- **Priority:** P2 | **Category:** New Features
- [x] Audit detect() confidence scores across CSV parsers
- [x] Ensure specific parsers outscore generic CsvParser
- [x] Add column-header detection to CsvParser.detect()

### FEAT-003: Add ricette_md.py detection guard — reduce false positives ✅
- **Priority:** P2 | **Category:** New Features
- [x] Add Italian keyword heuristic checks
- [x] Lower base confidence for bare headings to ~0.15

</details>
