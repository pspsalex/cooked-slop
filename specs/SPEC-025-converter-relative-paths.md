---
id: SPEC-025
title: "Converter Relative Path Output"
status: draft
priority: P2
type: refactor
created: 2026-09-04
---

# Spec: Converter Relative Path Output

## Overview

The converter pipeline currently embeds **resolved absolute paths** into JSON-LD output fields (`url`, `comment`), leaking the developer's local directory structure into output files and test fixtures. This spec defines how to switch to **relative paths** throughout the pipeline.

## Problem

When converting `tests/samples/spaghetti`, the output currently contains:

```json
{
  "comment": "Imported from /home/user/projects/scripts/tests/samples/spaghetti",
  "url": "file:///home/user/projects/scripts/tests/samples/spaghetti"
}
```

This is because:
1. `convert.py` resolves the input path to an absolute path before passing to parsers
2. Parsers embed `filepath` directly into `recipe.url` and `recipe.source_file`
3. `SchemaOrgConverter.convert()` uses `recipe.source_file` to generate `comment` and `url` fields

## Expected Behavior

Output should use the path **as provided by the user** (or relative to CWD):

```json
{
  "comment": "Imported from tests/samples/spaghetti",
  "url": "file://tests/samples/spaghetti"
}
```

## Scope

### Files to audit and modify

1. **`convert.py`** — `convert_recipe_file()` resolves `filepath` to absolute; should preserve original or make relative to CWD
2. **`converter.py`** — `SchemaOrgConverter.convert()` generates `comment` from `recipe.source_file`
3. **Parsers that set `recipe.url`**:
   - `parsers/sqlite/sqlite_parser.py` — `file://{filepath}#TABLE,ID`
   - `parsers/generic_md.py` — `file://{filepath}#{line}`
   - `parsers/ricette_md.py` — `file://{filepath}#{line}`
   - `parsers/cookware.py` — `file://{filepath}#{row}`
   - `parsers/html_parser.py` — sets `recipe.url`
   - Any other parser setting `recipe.url` or `recipe.source_file`

### Test impact
- All `tests/expected/*.json` files will need regeneration after the change
- Test normalization in `test_conversion.py` can be simplified once paths are relative

## Acceptance Criteria
- [ ] No absolute paths appear in JSON-LD output when input is given as a relative path
- [ ] `file://` URLs in output use the path as provided (relative or absolute)
- [ ] `comment` fields use the path as provided
- [ ] All expected test fixtures regenerated and contain only relative paths
- [ ] Full test suite passes: `./venv/bin/python3 -m pytest tests/ -v`

## Deliverables
- Modified `convert.py`, `converter.py`, and affected parsers
- Regenerated `tests/expected/*.json`
